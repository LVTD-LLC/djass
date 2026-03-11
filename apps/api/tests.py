import json

import pytest
from django.contrib.auth import get_user_model
from ninja.errors import AuthenticationError, HttpError, ValidationError

from apps.api.views import (
    ERROR_TAXONOMY,
    _error,
    on_authentication_error,
    on_http_error,
    on_validation_error,
)
from apps.core.choices import ProfileStates
from apps.core.models import Project, ProjectStatus

User = get_user_model()


@pytest.fixture(autouse=True)
def disable_state_transition_tasks(monkeypatch):
    monkeypatch.setattr("apps.core.models.async_task", lambda *args, **kwargs: None)


def _auth_headers(api_key: str):
    return {"HTTP_X_API_KEY": api_key}


def _create_subscribed_user(username: str):
    user = User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="password123",
    )
    profile = user.profile
    profile.state = ProfileStates.SUBSCRIBED
    profile.save(update_fields=["state"])
    return user, profile


@pytest.mark.django_db
def test_v1_projects_requires_authentication(client):
    response = client.get("/api/v1/projects")

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "auth_required",
            "category": "auth",
            "message": "Unauthorized",
            "retryable": False,
            "details": {},
        }
    }


@pytest.mark.django_db
def test_v1_projects_pagination_and_filtering(client):
    user, profile = _create_subscribed_user("owner")

    Project.objects.create(
        user=user,
        name="Queued Project",
        slug="queued_project",
        input_payload={"project_name": "Queued Project"},
        status=ProjectStatus.QUEUED,
    )
    ready_project = Project.objects.create(
        user=user,
        name="Ready Project",
        slug="ready_project",
        input_payload={"project_name": "Ready Project"},
        status=ProjectStatus.READY,
    )

    response = client.get(
        "/api/v1/projects?status=ready&limit=1&offset=0",
        **_auth_headers(profile.key),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["limit"] == 1
    assert payload["offset"] == 0
    assert payload["has_next"] is False
    assert payload["filters"] == {"status": "ready"}
    assert len(payload["projects"]) == 1
    assert payload["projects"][0]["id"] == ready_project.id


def test_authentication_error_handler_returns_api_error_schema(rf, monkeypatch):
    monkeypatch.setattr("apps.api.views.log_project_api_action", lambda *args, **kwargs: None)
    response = on_authentication_error(rf.get("/api/v1/projects"), AuthenticationError())

    assert response.status_code == 401
    assert json.loads(response.content) == {
        "error": {
            "code": "auth_required",
            "category": "auth",
            "message": "Unauthorized",
            "retryable": False,
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
            "category": "validation",
            "message": "Request validation failed.",
            "retryable": False,
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
            "category": "internal",
            "message": "Boom",
            "retryable": False,
            "details": {},
        }
    }


def test_error_taxonomy_entries_include_required_properties():
    for code, taxonomy in ERROR_TAXONOMY.items():
        assert set(taxonomy.keys()) == {"category", "retryable"}, code
        assert isinstance(taxonomy["category"], str) and taxonomy["category"], code
        assert isinstance(taxonomy["retryable"], bool), code

        status, payload = _error(400, code, "message")
        assert status == 400
        assert set(payload["error"].keys()) == {
            "code",
            "category",
            "message",
            "retryable",
            "details",
        }
