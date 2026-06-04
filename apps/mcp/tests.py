import io
import json
import zipfile
from pathlib import Path

import pytest
from django.core.files.storage import FileSystemStorage
from django.utils import timezone
from mcp.server.fastmcp.exceptions import ToolError

from apps.api.models import ProjectAPIKey
from apps.core.choices import ProfileStates
from apps.core.generator_options import COOKIECUTTER_FIELD_DEFAULTS, MODULE_FLAG_KEYS
from apps.core.models import Project, ProjectArtifact, ProjectStatus
from apps.mcp.services import (
    MCPServiceError,
    export_project_artifact,
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
    assert "groups" in options
    posthog_option = next(
        option
        for group in options["groups"]
        for option in group["options"]
        if option["key"] == "use_posthog"
    )
    assert "standard Python logging" in posthog_option["description"]


def test_mcp_tools_expose_current_generator_fields_and_defaults():
    from inspect import signature

    from apps.mcp import server
    from apps.mcp.server import _payload_from_args, create_project

    create_parameters = signature(create_project).parameters
    assert not hasattr(server, "generate_project")
    for field_name in COOKIECUTTER_FIELD_DEFAULTS:
        if field_name.startswith("_"):
            continue
        assert field_name in create_parameters

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
        use_keyboard_shortcuts="y",
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
        use_keyboard_shortcuts="y",
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


def _set_hosted_auth(user, scopes=None):
    from mcp.server.auth.middleware.auth_context import auth_context_var
    from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
    from mcp.server.auth.provider import AccessToken

    access_token = AccessToken(
        token="test-token",
        client_id=str(user.id),
        scopes=scopes or ["projects:create", "projects:read"],
    )
    return auth_context_var.set(AuthenticatedUser(access_token))


@pytest.mark.django_db
def test_hosted_fastmcp_exposes_djass_tools():
    from apps.mcp.hosted import hosted_mcp

    names = {tool.name for tool in hosted_mcp._tool_manager.list_tools()}

    assert "djass_generation_options" in names
    assert "djass_create_project" in names
    assert "djass_list_projects" in names
    assert "djass_get_project_status" in names
    assert "djass_get_project_download" in names


@pytest.mark.django_db(transaction=True)
def test_hosted_fastmcp_token_verifier_accepts_legacy_and_scoped_keys(django_user_model):
    import asyncio

    from apps.mcp.hosted import DjassAPITokenVerifier

    user = django_user_model.objects.create_user(
        username="hosted-verifier",
        email="hosted-verifier@example.local",
        password="password123",
    )
    scoped_key = ProjectAPIKey.objects.create(
        profile=user.profile,
        name="read only",
        scopes=["projects:read"],
    )
    verifier = DjassAPITokenVerifier()

    legacy = asyncio.run(verifier.verify_token(user.profile.key))
    scoped = asyncio.run(verifier.verify_token(scoped_key.key))

    assert legacy.client_id == str(user.id)
    assert set(legacy.scopes) == {"projects:create", "projects:read"}
    assert scoped.client_id == str(user.id)
    assert scoped.scopes == ["projects:read"]
    assert asyncio.run(verifier.verify_token("bad-key")) is None


@pytest.mark.django_db
def test_hosted_fastmcp_create_project_uses_authenticated_profile(django_user_model, monkeypatch):
    from mcp.server.auth.middleware.auth_context import auth_context_var

    from apps.mcp.hosted import djass_create_project

    monkeypatch.setattr("apps.mcp.services.async_task", lambda *args, **kwargs: "task-id")
    user = django_user_model.objects.create_user(
        username="hosted-mcp",
        email="hosted-mcp@example.local",
        password="password123",
    )
    user.profile.state = ProfileStates.SUBSCRIBED
    user.profile.save(update_fields=["state"])
    token = _set_hosted_auth(user)
    try:
        result = djass_create_project(
            project_name="Hosted MCP Project",
            project_slug="Hosted MCP Project",
            project_description="Created through hosted FastMCP",
            use_mcp="y",
        )
    finally:
        auth_context_var.reset(token)

    assert "hosted_mcp_project" in json.dumps(result)
    project = Project.objects.get(user=user, slug="hosted_mcp_project")
    assert project.status == ProjectStatus.QUEUED
    assert project.input_payload["author_email"] == user.email
    assert project.input_payload["use_mcp"] == "y"


@pytest.mark.django_db
def test_hosted_fastmcp_respects_scoped_api_key_permissions(django_user_model):
    from mcp.server.auth.middleware.auth_context import auth_context_var
    from mcp.server.fastmcp.exceptions import ToolError

    from apps.mcp.hosted import djass_create_project

    user = django_user_model.objects.create_user(
        username="hosted-scoped",
        email="hosted-scoped@example.local",
        password="password123",
    )
    token = _set_hosted_auth(user, scopes=["projects:read"])
    try:
        with pytest.raises(ToolError, match="projects:create"):
            djass_create_project(project_name="Denied", project_slug="denied")
    finally:
        auth_context_var.reset(token)


@pytest.mark.django_db
def test_hosted_fastmcp_download_tool_returns_authenticated_zip_url(django_user_model):
    from mcp.server.auth.middleware.auth_context import auth_context_var

    from apps.mcp.hosted import djass_get_project_download

    user = django_user_model.objects.create_user(
        username="hosted-download",
        email="hosted-download@example.local",
        password="password123",
    )
    user.profile.state = ProfileStates.SUBSCRIBED
    user.profile.save(update_fields=["state"])
    project = Project.objects.create(
        user=user,
        name="Ready Project",
        slug="ready_project",
        input_payload={"project_name": "Ready Project", "project_slug": "ready_project"},
        status=ProjectStatus.READY,
    )
    artifact = ProjectArtifact.objects.create(
        project=project,
        size_bytes=7,
        sha256="abc123",
    )
    artifact.zip_file.save("ready_project.zip", io.BytesIO(b"zipdata"), save=True)
    token = _set_hosted_auth(user)
    try:
        result = djass_get_project_download(project.id)
    finally:
        auth_context_var.reset(token)

    text = json.dumps(result)
    assert f"/mcp/projects/{project.id}/download" in text
    assert "abc123" in text


@pytest.mark.django_db
def test_mcp_download_and_prompt_django_endpoints(client, django_user_model):
    user = django_user_model.objects.create_user(
        username="hosted-direct-download",
        email="hosted-direct-download@example.local",
        password="password123",
    )
    user.profile.state = ProfileStates.SUBSCRIBED
    user.profile.save(update_fields=["state"])
    project = Project.objects.create(
        user=user,
        name="Ready Project",
        slug="ready_project",
        input_payload={"project_name": "Ready Project", "project_slug": "ready_project"},
        status=ProjectStatus.READY,
    )
    artifact = ProjectArtifact.objects.create(project=project, size_bytes=7, sha256="abc123")
    artifact.zip_file.save("ready_project.zip", io.BytesIO(b"zipdata"), save=True)

    prompt = client.get("/mcp/prompt")
    download = client.get(
        f"/mcp/projects/{project.id}/download",
        HTTP_AUTHORIZATION=f"Bearer {user.profile.key}",
    )

    assert prompt.status_code == 200
    assert "FastMCP endpoint" in prompt.json()["prompt"]
    assert "use_mcp" in json.dumps(prompt.json()["options"])
    assert download.status_code == 200
    assert download["Content-Disposition"].startswith("attachment;")


@pytest.mark.django_db(transaction=True)
def test_mcp_routes_are_reachable_through_deployed_asgi_app(
    django_user_model,
    settings,
):
    import asyncio

    import httpx

    user = django_user_model.objects.create_user(
        username="hosted-asgi-download",
        email="hosted-asgi-download@example.local",
        password="password123",
    )
    user.profile.state = ProfileStates.SUBSCRIBED
    user.profile.save(update_fields=["state"])
    project = Project.objects.create(
        user=user,
        name="Ready ASGI Project",
        slug="ready_asgi_project",
        input_payload={"project_name": "Ready ASGI Project", "project_slug": "ready_asgi_project"},
        status=ProjectStatus.READY,
    )
    artifact = ProjectArtifact.objects.create(project=project, size_bytes=7, sha256="abc123")
    artifact.zip_file.save("ready_asgi_project.zip", io.BytesIO(b"zipdata"), save=True)
    settings.ALLOWED_HOSTS = ["localhost"]

    async def request_asgi_routes():
        from djass.asgi import application

        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as client:
            mcp = await client.post("/mcp")
            prompt = await client.get("/mcp/prompt")
            download = await client.get(
                f"/mcp/projects/{project.id}/download",
                headers={"Authorization": f"Bearer {user.profile.key}"},
            )
        return mcp, prompt, download

    mcp, prompt, download = asyncio.run(request_asgi_routes())

    assert mcp.status_code == 401
    assert mcp.json()["error"] == "invalid_token"
    assert prompt.status_code == 200
    assert "FastMCP endpoint" in prompt.json()["prompt"]
    assert download.status_code == 200
    assert download.content == b"zipdata"


@pytest.mark.django_db(transaction=True)
def test_hosted_fastmcp_streamable_http_lists_tools_with_api_key(
    django_user_model,
    settings,
):
    import asyncio

    import httpx
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    user = django_user_model.objects.create_user(
        username="hosted-streamable-http",
        email="hosted-streamable-http@example.local",
        password="password123",
    )
    settings.ALLOWED_HOSTS = ["localhost"]

    async def list_tool_names() -> set[str]:
        from apps.mcp.hosted import hosted_mcp
        from djass.asgi import application

        async with hosted_mcp.session_manager.run():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=application),
                base_url="http://localhost",
                headers={"Authorization": f"Bearer {user.profile.key}"},
                follow_redirects=True,
            ) as http_client:
                async with streamable_http_client(
                    "http://localhost/mcp",
                    http_client=http_client,
                ) as (read_stream, write_stream, _get_session_id):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        tools = await session.list_tools()
                        return {tool.name for tool in tools.tools}

    tool_names = asyncio.run(list_tool_names())

    assert "djass_generation_options" in tool_names
    assert "djass_create_project" in tool_names
    assert "djass_get_project_download" in tool_names
