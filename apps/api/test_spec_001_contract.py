import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage

from apps.api.models import ProjectAPIAuditLog, ProjectAPIKey
from apps.api.schemas import ProjectCreateIn
from apps.core.choices import ProfileStates
from apps.core.generator_options import COOKIECUTTER_FIELD_DEFAULTS, MODULE_FLAG_KEYS
from apps.core.models import Project, ProjectArtifact, ProjectStatus

User = get_user_model()


@pytest.fixture(autouse=True)
def _disable_async_task_side_effects(monkeypatch):
    monkeypatch.setattr("apps.core.models.async_task", lambda *args, **kwargs: None)
    monkeypatch.setattr("apps.api.views.async_task", lambda *args, **kwargs: None)


CREATE_PAYLOAD = {
    "project_name": "Spec One API",
    "project_slug": "spec_one_api",
    "caprover_app_name": "spec-one-api",
    "project_description": "Contract test payload",
    "repo_url": "https://github.com/example/spec-one-api",
    "author_name": "Spec Bot",
    "author_email": "spec@example.com",
    "author_url": "https://example.com",
    "project_main_color": "green",
    "use_posthog": "y",
    "use_chatwoot": "n",
    "use_s3": "y",
    "use_stripe": "y",
    "use_sentry": "y",
    "generate_blog": "y",
    "generate_docs": "y",
    "use_mjml": "y",
    "use_keyboard_shortcuts": "y",
    "use_ai": "y",
    "use_healthchecks": "y",
    "use_apprise": "n",
    "use_mcp": "n",
    "use_ci": "y",
    "use_digitalocean": "n",
}


def _create_user(username: str, email: str, subscribed: bool):
    user = User.objects.create_user(username=username, email=email, password="password123")
    if user.is_superuser or user.is_staff:
        user.is_superuser = False
        user.is_staff = False
        user.save(update_fields=["is_superuser", "is_staff"])

    profile = user.profile
    profile.state = ProfileStates.SUBSCRIBED if subscribed else ProfileStates.STRANGER
    profile.save(update_fields=["state"])
    return user, profile


def _auth_headers(api_key: str):
    return {"HTTP_X_API_KEY": api_key}


def test_create_project_schema_exposes_current_generator_flags():
    schema_fields = ProjectCreateIn.model_fields

    assert ProjectCreateIn.model_config["extra"] == "allow"
    assert set(MODULE_FLAG_KEYS).issubset(schema_fields.keys())
    for field_name in MODULE_FLAG_KEYS:
        assert schema_fields[field_name].default == COOKIECUTTER_FIELD_DEFAULTS[field_name]


def test_project_options_endpoint_contract(client):
    response = client.get("/api/v1/project-options")

    assert response.status_code == 200
    body = response.json()
    assert body["defaults"]["use_chatwoot"] == "n"
    assert body["defaults"]["use_apprise"] == "n"
    assert body["defaults"]["use_mcp"] == "n"
    assert body["defaults"]["use_digitalocean"] == "n"
    assert "use_logfire" not in body["defaults"]

    groups = {group["key"]: group for group in body["groups"]}
    assert {option["key"] for option in groups["monitoring"]["options"]} >= {
        "use_posthog",
        "use_sentry",
        "use_healthchecks",
        "use_apprise",
    }
    assert "use_logfire" not in {
        option["key"] for option in groups["monitoring"]["options"]
    }
    assert {option["key"] for option in groups["cx"]["options"]} >= {
        "use_chatwoot",
        "use_mjml",
    }
    assert {option["key"] for option in groups["ux"]["options"]} >= {
        "use_keyboard_shortcuts",
    }
    assert {option["key"] for option in groups["ai"]["options"]} >= {"use_ai", "use_mcp"}
    assert {option["key"] for option in groups["delivery"]["options"]} >= {
        "use_ci",
        "use_digitalocean",
    }
    posthog_option = next(
        option for option in groups["monitoring"]["options"] if option["key"] == "use_posthog"
    )
    assert "standard Python logging" in posthog_option["description"]


@pytest.mark.django_db
class TestSpec001Contract:
    def test_auth_required_for_core_endpoints(self, client):
        assert client.get("/api/v1/projects").status_code == 401
        assert (
            client.post(
                "/api/v1/projects",
                data=CREATE_PAYLOAD,
                content_type="application/json",
            ).status_code
            == 401
        )
        assert client.get("/api/v1/projects/1").status_code == 401
        assert client.get("/api/v1/projects/1/status").status_code == 401
        assert client.get("/api/v1/projects/1/download").status_code == 401

    def test_create_project_contract_happy_path(self, client, monkeypatch):
        _, profile = _create_user("specuser", "specuser@example.com", subscribed=True)
        calls = []

        def fake_async_task(*args, **kwargs):
            calls.append((args, kwargs))
            return "task-id"

        monkeypatch.setattr("apps.api.views.async_task", fake_async_task)

        response = client.post(
            "/api/v1/projects",
            data=CREATE_PAYLOAD,
            content_type="application/json",
            **_auth_headers(profile.key),
        )

        assert response.status_code == 201
        body = response.json()
        assert set(body.keys()) == {"project"}
        project = body["project"]
        assert project["name"] == CREATE_PAYLOAD["project_name"]
        assert project["slug"] == CREATE_PAYLOAD["project_slug"]
        assert project["status"] == ProjectStatus.QUEUED
        assert project["artifact_ready"] is False
        assert isinstance(project["input_payload"], dict)
        assert project["input_payload"]["project_name"] == CREATE_PAYLOAD["project_name"]
        assert project["input_payload"]["use_chatwoot"] == "n"
        assert project["input_payload"]["use_apprise"] == "n"
        assert project["input_payload"]["use_mcp"] == "n"

        created = Project.objects.get(id=project["id"])
        assert created.user_id == profile.user_id

        generate_call = next(
            call for call in calls if call[0][0] == "apps.core.tasks.generate_project_artifact"
        )
        assert generate_call[1]["project_id"] == created.id

        tracking_call = next(call for call in calls if call[0][0] == "apps.core.tasks.track_event")
        assert tracking_call[1]["profile_id"] == profile.id
        assert tracking_call[1]["event_name"] == "project_created"
        assert tracking_call[1]["properties"] == {
            "project_id": created.id,
            "project_name": created.name,
            "project_slug": created.slug,
            "funnel_step": "project_created",
            "entrypoint": "api",
        }

    def test_create_project_requires_paid_access(self, client):
        _, profile = _create_user("unpaid", "unpaid@example.com", subscribed=False)

        response = client.post(
            "/api/v1/projects",
            data=CREATE_PAYLOAD,
            content_type="application/json",
            **_auth_headers(profile.key),
        )

        assert response.status_code == 402
        body = response.json()
        assert body["error"]["code"] == "subscription_required"
        assert body["error"]["details"]["upgrade_url"] == "/pricing"

    def test_create_project_validation_errors(self, client, monkeypatch):
        _, subscribed_profile = _create_user("subbed", "subbed@example.com", subscribed=True)
        calls = []

        def fake_async_task(*args, **kwargs):
            calls.append((args, kwargs))
            return "task-id"

        monkeypatch.setattr("apps.api.views.async_task", fake_async_task)
        invalid_payload = {**CREATE_PAYLOAD, "project_slug": "!!!"}
        invalid = client.post(
            "/api/v1/projects",
            data=invalid_payload,
            content_type="application/json",
            **_auth_headers(subscribed_profile.key),
        )
        assert invalid.status_code == 400
        invalid_body = invalid.json()
        assert invalid_body["error"]["code"] == "invalid_project_slug"
        assert invalid_body["error"]["category"] == "validation"
        assert invalid_body["error"]["retryable"] is False
        assert invalid_body["error"]["details"]["field"] == "project_slug"

        assert len(calls) == 1
        tracking_call = calls[0]
        assert tracking_call[0][0] == "apps.core.tasks.track_event"
        assert tracking_call[1]["event_name"] == "project_create_failed"
        assert tracking_call[1]["properties"]["reason"] == "invalid_project_slug"
        assert tracking_call[1]["properties"]["entrypoint"] == "api"

    def test_create_project_rejects_unknown_generator_options(self, client):
        _, profile = _create_user("unknown", "unknown@example.com", subscribed=True)

        response = client.post(
            "/api/v1/projects",
            data={**CREATE_PAYLOAD, "use_future_feature": "y"},
            content_type="application/json",
            **_auth_headers(profile.key),
        )

        assert response.status_code == 400
        body = response.json()
        assert body["error"]["code"] == "invalid_generator_option"
        assert body["error"]["category"] == "validation"
        assert body["error"]["details"]["unknown"] == ["use_future_feature"]

    def test_list_get_and_status_contract(self, client):
        user, profile = _create_user("owner", "owner@example.com", subscribed=True)
        other_user, _ = _create_user("other", "other@example.com", subscribed=True)

        owner_project = Project.objects.create(
            user=user,
            name="Owner Project",
            slug="owner_project",
            input_payload={"project_name": "Owner Project"},
            status=ProjectStatus.GENERATING,
        )
        Project.objects.create(
            user=other_user,
            name="Other Project",
            slug="other_project",
            input_payload={"project_name": "Other Project"},
            status=ProjectStatus.READY,
        )

        listing = client.get("/api/v1/projects", **_auth_headers(profile.key))
        assert listing.status_code == 200
        list_body = listing.json()
        assert list_body["total"] == 1
        assert list_body["limit"] == 20
        assert list_body["offset"] == 0
        assert list_body["has_next"] is False
        assert list_body["filters"] == {}
        assert len(list_body["projects"]) == 1
        assert list_body["projects"][0]["id"] == owner_project.id

        project_get = client.get(
            f"/api/v1/projects/{owner_project.id}",
            **_auth_headers(profile.key),
        )
        assert project_get.status_code == 200
        get_body = project_get.json()
        assert get_body["id"] == owner_project.id
        assert get_body["status"] == ProjectStatus.GENERATING

        status_get = client.get(
            f"/api/v1/projects/{owner_project.id}/status",
            **_auth_headers(profile.key),
        )
        assert status_get.status_code == 200
        status_body = status_get.json()
        assert set(status_body.keys()) == {
            "id",
            "status",
            "error_message",
            "artifact_ready",
            "started_at",
            "finished_at",
            "updated_at",
        }
        assert status_body["id"] == owner_project.id
        assert status_body["status"] == ProjectStatus.GENERATING

        missing = client.get("/api/v1/projects/999999", **_auth_headers(profile.key))
        assert missing.status_code == 404
        missing_body = missing.json()
        assert missing_body["error"]["code"] == "project_not_found"
        assert missing_body["error"]["category"] == "validation"

    def test_list_projects_supports_status_filter_and_pagination(self, client):
        user, profile = _create_user("pager", "pager@example.com", subscribed=True)
        Project.objects.create(
            user=user,
            name="Queued Project",
            slug="queued_project",
            input_payload={"project_name": "Queued Project"},
            status=ProjectStatus.QUEUED,
        )
        first_ready = Project.objects.create(
            user=user,
            name="First Ready",
            slug="first_ready",
            input_payload={"project_name": "First Ready"},
            status=ProjectStatus.READY,
        )
        Project.objects.create(
            user=user,
            name="Second Ready",
            slug="second_ready",
            input_payload={"project_name": "Second Ready"},
            status=ProjectStatus.READY,
        )

        response = client.get(
            "/api/v1/projects?status=ready&limit=1&offset=1",
            **_auth_headers(profile.key),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 2
        assert body["limit"] == 1
        assert body["offset"] == 1
        assert body["has_next"] is False
        assert body["filters"] == {"status": "ready"}
        assert len(body["projects"]) == 1
        assert body["projects"][0]["id"] == first_ready.id

    def test_create_project_quota_error(self, client, monkeypatch, settings):
        _, profile = _create_user("quota", "quota@example.com", subscribed=True)
        settings.PROJECT_API_MAX_PROJECTS_PER_USER = 1
        monkeypatch.setattr("apps.api.views.async_task", lambda *args, **kwargs: "task-id")

        Project.objects.create(
            user=profile.user,
            name="Existing",
            slug="existing",
            input_payload={"project_name": "Existing"},
            status=ProjectStatus.READY,
        )

        response = client.post(
            "/api/v1/projects",
            data=CREATE_PAYLOAD,
            content_type="application/json",
            **_auth_headers(profile.key),
        )

        assert response.status_code == 429
        body = response.json()
        assert body["error"]["code"] == "quota_exceeded"
        assert body["error"]["category"] == "quota"
        assert body["error"]["retryable"] is False
        assert body["error"]["details"]["quota"] == 1

    def test_create_project_retryable_error(self, client, monkeypatch):
        _, profile = _create_user("retry", "retry@example.com", subscribed=True)

        def raise_oserror(*args, **kwargs):
            raise OSError("queue unavailable")

        monkeypatch.setattr("apps.api.views.async_task", raise_oserror)

        response = client.post(
            "/api/v1/projects",
            data=CREATE_PAYLOAD,
            content_type="application/json",
            **_auth_headers(profile.key),
        )

        assert response.status_code == 503
        body = response.json()
        assert body["error"]["code"] == "retryable_error"
        assert body["error"]["category"] == "retryable"
        assert body["error"]["retryable"] is True

    def test_scoped_key_enforces_create_scope_and_logs_denial(self, client, monkeypatch):
        _, profile = _create_user("readkey", "readkey@example.com", subscribed=True)
        calls = []

        def fake_async_task(*args, **kwargs):
            calls.append((args, kwargs))
            return "task-id"

        monkeypatch.setattr("apps.api.views.async_task", fake_async_task)

        scoped_key = ProjectAPIKey.objects.create(
            profile=profile,
            name="Read only",
            scopes=["projects:read"],
        )

        response = client.post(
            "/api/v1/projects",
            data=CREATE_PAYLOAD,
            content_type="application/json",
            **_auth_headers(scoped_key.key),
        )

        assert response.status_code == 403
        body = response.json()
        assert body["error"]["code"] == "insufficient_scope"
        assert body["error"]["category"] == "auth"

        assert len(calls) == 1
        auth_failed_call = calls[0]
        assert auth_failed_call[0][0] == "apps.core.tasks.track_event"
        assert auth_failed_call[1]["event_name"] == "user_auth_failed"
        assert auth_failed_call[1]["properties"]["reason"] == "insufficient_scope"
        assert auth_failed_call[1]["properties"]["funnel_step"] == "auth_failed"

        audit = ProjectAPIAuditLog.objects.latest("created_at")
        assert audit.action == ProjectAPIAuditLog.ACTION_CREATE
        assert audit.status_code == 403
        assert audit.api_key_id == scoped_key.id
        assert audit.key_type == "scoped"
        assert audit.metadata["required_scope"] == "projects:create"

    def test_scoped_key_read_access_and_audit_log(self, client):
        user, profile = _create_user("reader", "reader@example.com", subscribed=True)
        project = Project.objects.create(
            user=user,
            name="Reader Project",
            slug="reader_project",
            input_payload={"project_name": "Reader Project"},
            status=ProjectStatus.READY,
        )
        scoped_key = ProjectAPIKey.objects.create(
            profile=profile,
            name="Reader key",
            scopes=["projects:read"],
        )

        response = client.get("/api/v1/projects", **_auth_headers(scoped_key.key))

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["projects"][0]["id"] == project.id

        audit = ProjectAPIAuditLog.objects.latest("created_at")
        assert audit.action == ProjectAPIAuditLog.ACTION_LIST
        assert audit.status_code == 200
        assert audit.api_key_id == scoped_key.id
        assert audit.metadata["count"] == 1

    def test_invalid_key_auth_attempt_is_audited(self, client):
        response = client.get("/api/v1/projects", **_auth_headers("invalid-key"))

        assert response.status_code == 401
        audit = ProjectAPIAuditLog.objects.latest("created_at")
        assert audit.action == ProjectAPIAuditLog.ACTION_LIST
        assert audit.status_code == 401
        assert audit.metadata["api_key_present"] is True

    def test_download_project_artifact_contract(self, client, tmp_path, settings, monkeypatch):
        settings.MEDIA_ROOT = tmp_path
        monkeypatch.setattr(
            ProjectArtifact.zip_file.field, "storage", FileSystemStorage(location=tmp_path)
        )
        user, profile = _create_user("download", "download@example.com", subscribed=True)
        project = Project.objects.create(
            user=user,
            name="Download Project",
            slug="download_project",
            input_payload={"project_name": "Download Project"},
            status=ProjectStatus.READY,
        )
        artifact = ProjectArtifact.objects.create(
            project=project,
            size_bytes=8,
            sha256="abc123",
        )
        artifact.zip_file.save("download_project.zip", ContentFile(b"PK\x03\x04test"), save=True)

        response = client.get(
            f"/api/v1/projects/{project.id}/download",
            **_auth_headers(profile.key),
        )

        assert response.status_code == 200
        assert response["Content-Type"] == "application/zip"
        assert response["Content-Disposition"].startswith('attachment; filename="download_project-')
        assert b"".join(response.streaming_content) == b"PK\x03\x04test"

        audit = ProjectAPIAuditLog.objects.latest("created_at")
        assert audit.action == ProjectAPIAuditLog.ACTION_DOWNLOAD
        assert audit.status_code == 200
        assert audit.project_id == project.id
        assert audit.metadata == {"size_bytes": 8, "sha256": "abc123"}

    def test_download_project_artifact_not_ready(self, client):
        user, profile = _create_user("notready", "notready@example.com", subscribed=True)
        project = Project.objects.create(
            user=user,
            name="Queued Project",
            slug="queued_project",
            input_payload={"project_name": "Queued Project"},
            status=ProjectStatus.GENERATING,
        )

        response = client.get(
            f"/api/v1/projects/{project.id}/download",
            **_auth_headers(profile.key),
        )

        assert response.status_code == 409
        body = response.json()
        assert body["error"]["code"] == "artifact_not_ready"
        assert body["error"]["category"] == "retryable"
        assert body["error"]["retryable"] is True
        assert body["error"]["details"]["status"] == ProjectStatus.GENERATING

    def test_scoped_key_download_requires_read_scope(self, client, tmp_path, settings, monkeypatch):
        settings.MEDIA_ROOT = tmp_path
        monkeypatch.setattr(
            ProjectArtifact.zip_file.field, "storage", FileSystemStorage(location=tmp_path)
        )
        user, profile = _create_user("downloadscope", "downloadscope@example.com", subscribed=True)
        project = Project.objects.create(
            user=user,
            name="Download Scope",
            slug="download_scope",
            input_payload={"project_name": "Download Scope"},
            status=ProjectStatus.READY,
        )
        artifact = ProjectArtifact.objects.create(project=project, size_bytes=8, sha256="abc123")
        artifact.zip_file.save("download_scope.zip", ContentFile(b"PK\x03\x04test"), save=True)
        scoped_key = ProjectAPIKey.objects.create(
            profile=profile,
            name="Create only",
            scopes=["projects:create"],
        )

        response = client.get(
            f"/api/v1/projects/{project.id}/download",
            **_auth_headers(scoped_key.key),
        )

        assert response.status_code == 403
        body = response.json()
        assert body["error"]["code"] == "insufficient_scope"
        assert body["error"]["details"]["required_scope"] == "projects:read"
