import json

import pytest
from ninja.errors import AuthenticationError, HttpError, ValidationError

from apps.api.views import on_authentication_error, on_http_error, on_validation_error
from apps.core.models import Project, ProjectArtifact, ProjectStatus


@pytest.fixture(autouse=True)
def disable_state_transition_tasks(monkeypatch):
    monkeypatch.setattr("apps.core.models.async_task", lambda *args, **kwargs: None)


@pytest.mark.django_db
def test_projects_api_requires_authentication(client):
    response = client.get("/api/projects")
    assert response.status_code == 401


@pytest.mark.django_db
def test_projects_api_returns_only_authenticated_user_projects(client, django_user_model):
    user = django_user_model.objects.create_user(
        username="owner",
        email="owner@example.com",
        password="password123",
    )
    other_user = django_user_model.objects.create_user(
        username="other",
        email="other@example.com",
        password="password123",
    )

    user_project = Project.objects.create(
        user=user,
        name="Owner Project",
        slug="owner_project",
        input_payload={"project_name": "Owner Project"},
        status=ProjectStatus.READY,
    )
    ProjectArtifact.objects.create(
        project=user_project,
        zip_file="generated-projects/owner-project.zip",
        size_bytes=1024,
        sha256="a" * 64,
    )
    Project.objects.create(
        user=other_user,
        name="Other Project",
        slug="other_project",
        input_payload={"project_name": "Other Project"},
        status=ProjectStatus.FAILED,
        error_message="other error",
    )

    client.force_login(user)
    response = client.get("/api/projects")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["name"] == "Owner Project"
    assert payload[0]["status"] == ProjectStatus.READY
    assert payload[0]["artifact"]["zip_file"] == "generated-projects/owner-project.zip"


@pytest.mark.django_db
def test_projects_api_returns_null_artifact_when_not_generated(client, django_user_model):
    user = django_user_model.objects.create_user(
        username="noartifact",
        email="noartifact@example.com",
        password="password123",
    )
    Project.objects.create(
        user=user,
        name="Queued Project",
        slug="queued_project",
        input_payload={"project_name": "Queued Project"},
        status=ProjectStatus.QUEUED,
    )

    client.force_login(user)
    response = client.get("/api/projects")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["name"] == "Queued Project"
    assert payload[0]["artifact"] is None


def test_v1_projects_unauthorized_returns_deterministic_api_error(client):
    response = client.get("/api/v1/projects")

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "auth_required",
            "message": "Unauthorized",
            "details": {},
        }
    }


def test_authentication_error_handler_returns_api_error_schema(rf):
    response = on_authentication_error(rf.get("/api/v1/projects"), AuthenticationError())

    assert response.status_code == 401
    assert json.loads(response.content) == {
        "error": {
            "code": "auth_required",
            "message": "Unauthorized",
            "details": {},
        }
    }


def test_validation_error_handler_returns_api_error_schema(rf):
    response = on_validation_error(
        rf.post("/api/v1/projects"),
        ValidationError(
            [
                {
                    "loc": ["body", "project_slug"],
                    "msg": "Field required",
                    "type": "missing",
                }
            ]
        ),
    )

    assert response.status_code == 422
    assert json.loads(response.content) == {
        "error": {
            "code": "validation_error",
            "message": "Request validation failed.",
            "details": {
                "violations": [
                    {
                        "loc": ["body", "project_slug"],
                        "msg": "Field required",
                        "type": "missing",
                    }
                ]
            },
        }
    }


def test_http_error_handler_returns_api_error_schema(rf):
    response = on_http_error(rf.get("/api/user/settings"), HttpError(500, "Boom"))

    assert response.status_code == 500
    assert json.loads(response.content) == {
        "error": {
            "code": "http_error",
            "message": "Boom",
            "details": {},
        }
    }
