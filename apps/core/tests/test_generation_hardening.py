import io
import json
import zipfile
from pathlib import Path

import pytest

from apps.core.models import Project, ProjectStatus
from apps.core.tasks import (
    COOKIECUTTER_FIELD_DEFAULTS,
    MANIFEST_FILE_NAME,
    METADATA_FILE_NAME,
    MODULE_FLAG_KEYS,
    generate_project_artifact,
)


@pytest.fixture(autouse=True)
def test_environment_isolated(monkeypatch, settings, tmp_path):
    monkeypatch.setattr("apps.core.models.async_task", lambda *args, **kwargs: None)

    media_root = tmp_path / "media"
    media_root.mkdir(parents=True, exist_ok=True)
    settings.MEDIA_ROOT = str(media_root)
    settings.STORAGES["default"] = {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": str(media_root)},
    }


@pytest.fixture
def fake_cookiecutter(monkeypatch):
    def _fake_cookiecutter(template_path, no_input, output_dir, extra_context):
        project_dir = Path(output_dir) / extra_context["project_slug"]
        project_dir.mkdir(parents=True, exist_ok=True)

        (project_dir / "README.md").write_text(
            f"# {extra_context['project_name']}\n", encoding="utf-8"
        )
        (project_dir / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")

        if extra_context.get("generate_blog") == "y":
            (project_dir / "apps" / "blog").mkdir(parents=True, exist_ok=True)
            (project_dir / "apps" / "blog" / "enabled.txt").write_text(
                "enabled\n", encoding="utf-8"
            )

        if extra_context.get("generate_docs") == "y":
            (project_dir / "apps" / "docs").mkdir(parents=True, exist_ok=True)
            (project_dir / "apps" / "docs" / "enabled.txt").write_text(
                "enabled\n", encoding="utf-8"
            )

        return str(project_dir)

    monkeypatch.setattr("apps.core.tasks.cookiecutter", _fake_cookiecutter)


def _build_payload(**overrides):
    payload = dict(COOKIECUTTER_FIELD_DEFAULTS)
    payload.update(overrides)
    return payload


def _create_project(user, payload):
    return Project.objects.create(
        user=user,
        name=payload["project_name"],
        slug=payload["project_slug"],
        input_payload=payload,
        status=ProjectStatus.QUEUED,
    )


def _read_artifact_zip(project):
    project.refresh_from_db()
    project.artifact.zip_file.open("rb")
    raw = project.artifact.zip_file.read()
    with zipfile.ZipFile(io.BytesIO(raw), "r") as zf:
        names = sorted(zf.namelist())
        manifest = json.loads(zf.read(MANIFEST_FILE_NAME).decode("utf-8"))
        metadata = json.loads(zf.read(METADATA_FILE_NAME).decode("utf-8"))
    return names, manifest, metadata


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payload",
    [
        _build_payload(project_name="Agency Alpha", project_slug="agency_alpha"),
        _build_payload(
            project_name="Lean Build",
            project_slug="lean_build",
            use_posthog="n",
            use_chatwoot="n",
            use_s3="n",
            use_stripe="n",
            use_sentry="n",
            generate_blog="n",
            generate_docs="n",
            use_mjml="n",
            use_keyboard_shortcuts="n",
            use_ai="n",
            use_healthchecks="n",
            use_apprise="n",
            use_mcp="n",
            use_ci="n",
        ),
        _build_payload(
            project_name="Mixed Build",
            project_slug="mixed_build",
            generate_blog="n",
            generate_docs="y",
            use_ai="n",
            use_ci="y",
        ),
    ],
)
def test_generation_writes_standardized_metadata_and_manifest(user, fake_cookiecutter, payload):
    project = _create_project(user, payload)

    result = generate_project_artifact(project.id)

    assert result == "Project artifact generated"
    project.refresh_from_db()
    assert project.status == ProjectStatus.READY
    assert project.error_message == ""

    names, manifest, metadata = _read_artifact_zip(project)

    assert METADATA_FILE_NAME in names
    assert MANIFEST_FILE_NAME in names
    assert manifest["manifest_version"] == "1.0"
    assert manifest["project"]["id"] == project.id
    assert manifest["project"]["slug"] == project.slug
    assert manifest["metadata_file"] == METADATA_FILE_NAME
    assert manifest["module_flags"]

    assert metadata["metadata_version"] == "1.0"
    assert metadata["project_id"] == project.id
    assert metadata["project_slug"] == project.slug
    assert set(metadata["module_flags"].keys()) == set(MODULE_FLAG_KEYS)


@pytest.mark.django_db
def test_repeated_generation_is_structurally_stable(user, fake_cookiecutter):
    payload = _build_payload(project_name="Stable Build", project_slug="stable_build", use_ai="n")
    project = _create_project(user, payload)

    generate_project_artifact(project.id)
    names_first, manifest_first, metadata_first = _read_artifact_zip(project)

    project.status = ProjectStatus.QUEUED
    project.save(update_fields=["status", "updated_at"])

    generate_project_artifact(project.id)
    names_second, manifest_second, metadata_second = _read_artifact_zip(project)

    assert names_first == names_second
    assert manifest_first["input_payload"] == manifest_second["input_payload"]
    assert manifest_first["module_flags"] == manifest_second["module_flags"]
    assert metadata_first["module_flags"] == metadata_second["module_flags"]


@pytest.mark.django_db
def test_generation_failure_has_actionable_diagnostics(user, monkeypatch):
    def _explode(*args, **kwargs):
        raise RuntimeError("missing required key: project_slug")

    class _FailedProcess:
        returncode = 2
        stderr = "missing required key: project_slug"

    monkeypatch.setattr("apps.core.tasks.cookiecutter", _explode)
    monkeypatch.setattr("apps.core.tasks.subprocess.run", lambda *args, **kwargs: _FailedProcess())

    payload = _build_payload(project_name="Broken Build", project_slug="broken_build")
    project = _create_project(user, payload)

    with pytest.raises(RuntimeError):
        generate_project_artifact(project.id)

    project.refresh_from_db()
    assert project.status == ProjectStatus.FAILED
    assert "Project generation failed" in project.error_message
    assert "RuntimeError" in project.error_message
    assert "missing required key: project_slug" in project.error_message
