import io
import json
import zipfile
from pathlib import Path

import pytest
from django.core.files.storage import FileSystemStorage
from django.utils import timezone
from mcp.server.fastmcp.exceptions import ToolError

from apps.core.choices import ProfileStates
from apps.core.generator_options import COOKIECUTTER_FIELD_DEFAULTS, MODULE_FLAG_KEYS
from apps.core.models import Project, ProjectArtifact, ProjectStatus
from apps.mcp.services import (
    MCPServiceError,
    export_project_artifact,
    generate_project_now,
    get_generator_options,
    list_projects,
    queue_project_generation,
)


@pytest.fixture(autouse=True)
def isolate_mcp_tests(monkeypatch, settings, tmp_path):
    monkeypatch.setattr("apps.core.models.async_task", lambda *args, **kwargs: None)
    monkeypatch.setattr("apps.core.signals.async_task", lambda *args, **kwargs: None)

    media_root = tmp_path / "media"
    media_root.mkdir(parents=True, exist_ok=True)
    settings.MEDIA_ROOT = str(media_root)
    monkeypatch.setattr(
        ProjectArtifact.zip_file.field,
        "storage",
        FileSystemStorage(location=media_root),
    )


@pytest.fixture
def fake_cookiecutter(monkeypatch):
    def _fake_cookiecutter(template_path, no_input, output_dir, extra_context):
        project_dir = Path(output_dir) / extra_context["project_slug"]
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "README.md").write_text(
            f"# {extra_context['project_name']}\n", encoding="utf-8"
        )
        (project_dir / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
        return str(project_dir)

    monkeypatch.setattr("apps.core.tasks.cookiecutter", _fake_cookiecutter)


def _payload(**overrides):
    payload = {
        "project_name": "MCP CRM",
        "project_slug": "mcp_crm",
        "project_description": "Generated through MCP",
        "author_name": "Agent",
        "author_email": "agent@example.local",
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_generate_project_now_creates_artifact_and_exports(fake_cookiecutter, tmp_path):
    output_dir = tmp_path / "export"

    result = generate_project_now(
        _payload(project_slug="mcp crm"),
        user_email="agent@example.local",
        output_dir=str(output_dir),
        extract=True,
    )

    project = Project.objects.get(id=result["project"]["id"])
    assert project.user.email == "agent@example.local"
    assert project.user.profile.state == ProfileStates.SUBSCRIBED
    assert project.slug == "mcp_crm"
    assert project.status == ProjectStatus.READY
    assert project.artifact.sha256

    assert result["generated"] is True
    assert Path(result["export"]["zip_path"]).exists()
    assert Path(result["export"]["extract_path"], "README.md").read_text() == "# MCP CRM\n"


@pytest.mark.django_db
def test_generate_project_now_wraps_generation_failure(monkeypatch):
    def _explode(*args, **kwargs):
        raise RuntimeError("missing required key: project_slug")

    class _FailedProcess:
        returncode = 2
        stderr = "missing required key: project_slug"

    monkeypatch.setattr("apps.core.tasks.cookiecutter", _explode)
    monkeypatch.setattr("apps.core.tasks.subprocess.run", lambda *args, **kwargs: _FailedProcess())

    with pytest.raises(MCPServiceError) as exc_info:
        generate_project_now(
            _payload(project_slug="broken_generation"),
            user_email="failure@example.local",
        )

    error = exc_info.value
    assert error.code == "generation_failed"
    assert "Project generation failed" in error.message
    assert error.details["project_id"]
    assert error.details["status"] == ProjectStatus.FAILED
    assert "missing required key: project_slug" in error.details["error_message"]


@pytest.mark.django_db
def test_queue_project_generation_uses_django_q(monkeypatch):
    calls = []

    def fake_async_task(*args, **kwargs):
        calls.append((args, kwargs))
        return "task-id"

    monkeypatch.setattr("apps.mcp.services.async_task", fake_async_task)

    result = queue_project_generation(_payload(), user_email="queue@example.local")

    project = Project.objects.get(id=result["project"]["id"])
    assert project.status == ProjectStatus.QUEUED
    assert result["queued"] is True
    assert calls == [
        (
            ("apps.core.tasks.generate_project_artifact",),
            {"project_id": project.id, "group": "Generate Project"},
        )
    ]


@pytest.mark.django_db
def test_explicit_user_email_does_not_fall_back_to_derived_username(django_user_model, monkeypatch):
    existing = django_user_model.objects.create_user(
        username="alice",
        email="existing-alice@example.local",
        password="password123",
    )
    existing.profile.state = ProfileStates.STRANGER
    existing.profile.save(update_fields=["state"])
    monkeypatch.setattr("apps.mcp.services.async_task", lambda *args, **kwargs: "task-id")

    result = queue_project_generation(
        _payload(project_slug="identity_check"),
        user_email="alice@example.local",
    )

    project = Project.objects.get(id=result["project"]["id"])
    existing.refresh_from_db()
    assert project.user.email == "alice@example.local"
    assert project.user_id != existing.id
    assert existing.profile.state == ProfileStates.STRANGER


@pytest.mark.django_db
def test_list_projects_can_scope_by_user_and_status(django_user_model):
    first_user = django_user_model.objects.create_user(
        username="first",
        email="first@example.local",
        password="password123",
    )
    second_user = django_user_model.objects.create_user(
        username="second",
        email="second@example.local",
        password="password123",
    )
    ready = Project.objects.create(
        user=first_user,
        name="Ready",
        slug="ready",
        input_payload={"project_name": "Ready"},
        status=ProjectStatus.READY,
    )
    Project.objects.create(
        user=first_user,
        name="Queued",
        slug="queued",
        input_payload={"project_name": "Queued"},
        status=ProjectStatus.QUEUED,
    )
    Project.objects.create(
        user=second_user,
        name="Other",
        slug="other",
        input_payload={"project_name": "Other"},
        status=ProjectStatus.READY,
    )

    result = list_projects(user_email="first@example.local", status=ProjectStatus.READY)

    assert result["total"] == 1
    assert result["projects"][0]["id"] == ready.id
    assert result["filters"] == {"status": ProjectStatus.READY}


@pytest.mark.django_db
def test_list_projects_orders_stably_for_pagination(django_user_model):
    user = django_user_model.objects.create_user(
        username="pager",
        email="pager@example.local",
        password="password123",
    )
    first = Project.objects.create(
        user=user,
        name="First",
        slug="first",
        input_payload={"project_name": "First"},
        status=ProjectStatus.READY,
    )
    second = Project.objects.create(
        user=user,
        name="Second",
        slug="second",
        input_payload={"project_name": "Second"},
        status=ProjectStatus.READY,
    )
    same_timestamp = timezone.now()
    Project.objects.filter(id__in=[first.id, second.id]).update(created_at=same_timestamp)

    first_page = list_projects(user_email="pager@example.local", limit=1, offset=0)
    second_page = list_projects(user_email="pager@example.local", limit=1, offset=1)

    assert first_page["projects"][0]["id"] == first.id
    assert second_page["projects"][0]["id"] == second.id


@pytest.mark.django_db
def test_export_project_artifact_extracts_safely(tmp_path, django_user_model):
    user = django_user_model.objects.create_user(
        username="export",
        email="export@example.local",
        password="password123",
    )
    project = Project.objects.create(
        user=user,
        name="Export",
        slug="export",
        input_payload={"project_name": "Export"},
        status=ProjectStatus.READY,
    )

    raw_zip = io.BytesIO()
    with zipfile.ZipFile(raw_zip, "w") as zip_file:
        zip_file.writestr("README.md", "# Export\n")
    artifact = ProjectArtifact.objects.create(project=project, size_bytes=len(raw_zip.getvalue()))
    artifact.zip_file.save("export.zip", io.BytesIO(raw_zip.getvalue()), save=True)

    result = export_project_artifact(project.id, output_dir=str(tmp_path / "out"), extract=True)

    assert Path(result["zip_path"]).exists()
    assert Path(result["extract_path"], "README.md").read_text() == "# Export\n"


@pytest.mark.django_db
def test_project_resources_scope_to_default_mcp_user(monkeypatch, django_user_model):
    monkeypatch.setenv("DJASS_MCP_USER_EMAIL", "owner@example.local")
    owner = django_user_model.objects.create_user(
        username="resource-owner",
        email="owner@example.local",
        password="password123",
    )
    other = django_user_model.objects.create_user(
        username="resource-other",
        email="other@example.local",
        password="password123",
    )
    owner_project = Project.objects.create(
        user=owner,
        name="Owner Resource",
        slug="owner_resource",
        input_payload={"project_name": "Owner Resource"},
        status=ProjectStatus.READY,
    )
    other_project = Project.objects.create(
        user=other,
        name="Other Resource",
        slug="other_resource",
        input_payload={"project_name": "Other Resource"},
        status=ProjectStatus.READY,
    )

    raw_zip = io.BytesIO()
    with zipfile.ZipFile(raw_zip, "w") as zip_file:
        zip_file.writestr("README.md", "# Owner Resource\n")
    artifact = ProjectArtifact.objects.create(
        project=owner_project,
        size_bytes=len(raw_zip.getvalue()),
    )
    artifact.zip_file.save("owner_resource.zip", io.BytesIO(raw_zip.getvalue()), save=True)

    from apps.mcp.server import project_artifact_resource, project_resource

    assert json.loads(project_resource(str(owner_project.id)))["id"] == owner_project.id
    assert project_artifact_resource(str(owner_project.id)).startswith(b"PK")
    with pytest.raises(ToolError):
        project_resource(str(other_project.id))


@pytest.mark.django_db
def test_invalid_payload_reports_field_errors():
    with pytest.raises(MCPServiceError) as exc_info:
        queue_project_generation(_payload(project_slug="!!!"), user_email="invalid@example.local")

    assert exc_info.value.code == "validation_error"
    assert "project_slug" in json.dumps(exc_info.value.details)


def test_generator_options_exposes_defaults_and_flags(settings):
    settings.COOKIECUTTER_TEMPLATE_PATH = "https://example.test/template.git"

    options = get_generator_options()

    assert options["template_path"] == "https://example.test/template.git"
    assert options["defaults"]["project_name"] == "My Awesome Project"
    assert "use_stripe" in options["module_flags"]


def test_mcp_tools_expose_current_generator_fields_and_defaults():
    from inspect import signature

    from apps.mcp.server import _payload_from_args, create_project, generate_project

    create_parameters = signature(create_project).parameters
    generate_parameters = signature(generate_project).parameters
    for field_name in COOKIECUTTER_FIELD_DEFAULTS:
        if field_name.startswith("_"):
            continue
        assert field_name in create_parameters
        assert field_name in generate_parameters

    expected_mcp_defaults = {
        "caprover_app_name": "",
        "project_description": "",
        "repo_url": "",
        "author_name": "",
        "author_email": "",
        "author_url": "",
        "project_main_color": COOKIECUTTER_FIELD_DEFAULTS["project_main_color"],
        **{field_name: COOKIECUTTER_FIELD_DEFAULTS[field_name] for field_name in MODULE_FLAG_KEYS},
    }
    for field_name, expected_default in expected_mcp_defaults.items():
        assert create_parameters[field_name].default == expected_default
        assert generate_parameters[field_name].default == expected_default

    payload = _payload_from_args(
        project_name="Support CRM",
        project_slug="support_crm",
        caprover_app_name="support-crm",
        project_description="",
        repo_url="",
        author_name="",
        author_email="",
        author_url="",
        project_main_color="green",
        use_posthog="y",
        use_chatwoot="y",
        use_s3="y",
        use_stripe="y",
        use_sentry="y",
        generate_blog="y",
        generate_docs="y",
        use_mjml="y",
        use_ai="y",
        use_logfire="y",
        use_healthchecks="y",
        use_apprise="n",
        use_mcp="y",
        use_ci="y",
        use_digitalocean="n",
        extra_context=None,
    )
    assert payload["use_chatwoot"] == "y"
    assert payload["use_apprise"] == "n"
    assert payload["use_mcp"] == "y"
    assert payload["use_digitalocean"] == "n"

    defaulted_payload = _payload_from_args(
        project_name="Support CRM",
        project_slug="support_crm",
        caprover_app_name="",
        project_description="",
        repo_url="",
        author_name="",
        author_email="",
        author_url="",
        project_main_color="green",
        use_posthog="y",
        use_chatwoot="y",
        use_s3="y",
        use_stripe="y",
        use_sentry="y",
        generate_blog="y",
        generate_docs="y",
        use_mjml="y",
        use_ai="y",
        use_logfire="y",
        use_healthchecks="y",
        use_apprise="n",
        use_mcp="y",
        use_ci="y",
        use_digitalocean="n",
        extra_context=None,
    )
    assert (
        defaulted_payload["caprover_app_name"] == COOKIECUTTER_FIELD_DEFAULTS["caprover_app_name"]
    )
