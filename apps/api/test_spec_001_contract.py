import pytest
from django.contrib.auth import get_user_model

from apps.api.models import ProjectAPIAuditLog, ProjectAPIKey
from apps.core.choices import ProfileStates
from apps.core.models import Project, ProjectStatus

User = get_user_model()


@pytest.fixture(autouse=True)
def _disable_async_task_side_effects(monkeypatch):
    monkeypatch.setattr("apps.core.models.async_task", lambda *args, **kwargs: None)
    monkeypatch.setattr("apps.api.views.async_task", lambda *args, **kwargs: None)


CREATE_PAYLOAD = {
    "project_name": "Spec One API",
    "project_slug": "spec_one_api",
    "project_description": "Contract test payload",
    "repo_url": "https://github.com/example/spec-one-api",
    "author_name": "Spec Bot",
    "author_email": "spec@example.com",
    "author_url": "https://example.com",
    "project_main_color": "green",
    "use_posthog": "y",
    "use_buttondown": "y",
    "use_s3": "y",
    "use_stripe": "y",
    "use_sentry": "y",
    "generate_blog": "y",
    "generate_docs": "y",
    "use_mjml": "y",
    "use_ai": "y",
    "use_logfire": "y",
    "use_healthchecks": "y",
    "use_ci": "y",
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

    def test_create_project_contract_happy_path(self, client, monkeypatch):
        _, profile = _create_user("specuser", "specuser@example.com", subscribed=True)
        called = {}

        def fake_async_task(*args, **kwargs):
            called["args"] = args
            called["kwargs"] = kwargs
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

        created = Project.objects.get(id=project["id"])
        assert created.user_id == profile.user_id
        assert called["args"][0] == "apps.core.tasks.generate_project_artifact"
        assert called["kwargs"]["project_id"] == created.id

    def test_create_project_validation_errors(self, client, monkeypatch):
        _, subscribed_profile = _create_user("subbed", "subbed@example.com", subscribed=True)
        monkeypatch.setattr("apps.api.views.async_task", lambda *args, **kwargs: "task-id")
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
        monkeypatch.setattr("apps.api.views.async_task", lambda *args, **kwargs: "task-id")

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
