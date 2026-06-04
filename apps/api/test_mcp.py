import pytest
from django.contrib.auth import get_user_model

from apps.api.models import ProjectAPIKey
from apps.core.choices import ProfileStates
from apps.core.models import Project, ProjectStatus

User = get_user_model()


@pytest.fixture(autouse=True)
def _disable_async_task_side_effects(monkeypatch):
    monkeypatch.setattr("apps.api.mcp.async_task", lambda *args, **kwargs: "task-id")
    monkeypatch.setattr("apps.core.models.async_task", lambda *args, **kwargs: "task-id")


def _create_subscribed_user(username="mcpuser"):
    user = User.objects.create_user(
        username=username, email=f"{username}@example.com", password="password123"
    )
    profile = user.profile
    profile.state = ProfileStates.SUBSCRIBED
    profile.save(update_fields=["state"])
    return user, profile


def _rpc(method, params=None, request_id=1):
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}


@pytest.mark.django_db
def test_mcp_lists_tools_and_generation_options_without_auth(client):
    listing = client.post("/api/mcp", data=_rpc("tools/list"), content_type="application/json")

    assert listing.status_code == 200
    tools = listing.json()["result"]["tools"]
    names = {tool["name"] for tool in tools}
    assert "djass_generation_options" in names
    assert "djass_create_project" in names

    options = client.post(
        "/api/mcp",
        data=_rpc("tools/call", {"name": "djass_generation_options", "arguments": {}}),
        content_type="application/json",
    )

    assert options.status_code == 200
    body = options.json()
    text = body["result"]["content"][0]["text"]
    assert "use_sentry" in text
    assert "Always call djass_generation_options" not in text
    assert "Call djass_generation_options first" in text


@pytest.mark.django_db
def test_mcp_create_project_requires_auth(client):
    response = client.post(
        "/api/mcp",
        data=_rpc(
            "tools/call",
            {
                "name": "djass_create_project",
                "arguments": {"project_name": "No Auth", "project_slug": "no_auth"},
            },
        ),
        content_type="application/json",
    )

    assert response.status_code == 401
    assert response.json()["error"]["message"].startswith("Authentication required")


@pytest.mark.django_db
def test_mcp_create_project_happy_path(client):
    user, profile = _create_subscribed_user()

    response = client.post(
        "/api/mcp",
        data=_rpc(
            "tools/call",
            {
                "name": "djass_create_project",
                "arguments": {
                    "project_name": "MCP Project",
                    "project_slug": "MCP Project",
                    "project_description": "Created through MCP",
                    "use_sentry": "n",
                },
            },
        ),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {profile.key}",
    )

    assert response.status_code == 200
    payload = response.json()["result"]["content"][0]["text"]
    assert "mcp_project" in payload

    project = Project.objects.get(user=user, slug="mcp_project")
    assert project.status == ProjectStatus.QUEUED
    assert project.input_payload["author_email"] == user.email
    assert project.input_payload["use_sentry"] == "n"


@pytest.mark.django_db
def test_mcp_list_projects_rejects_malformed_pagination(client):
    _, profile = _create_subscribed_user("pagination")

    response = client.post(
        "/api/mcp",
        data=_rpc(
            "tools/call",
            {"name": "djass_list_projects", "arguments": {"limit": "many"}},
        ),
        content_type="application/json",
        HTTP_X_API_KEY=profile.key,
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["data"]["code"] == "validation_error"
    assert body["error"]["data"]["field"] == "limit"


@pytest.mark.django_db
def test_mcp_get_project_status_rejects_malformed_project_id(client):
    _, profile = _create_subscribed_user("badstatus")

    response = client.post(
        "/api/mcp",
        data=_rpc(
            "tools/call",
            {"name": "djass_get_project_status", "arguments": {"project_id": "abc"}},
        ),
        content_type="application/json",
        HTTP_X_API_KEY=profile.key,
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["data"]["code"] == "validation_error"
    assert body["error"]["data"]["field"] == "project_id"


@pytest.mark.django_db
def test_mcp_respects_scoped_api_key_permissions(client):
    _, profile = _create_subscribed_user("scoped")
    key = ProjectAPIKey.objects.create(profile=profile, name="read only", scopes=["projects:read"])

    response = client.post(
        "/api/mcp",
        data=_rpc(
            "tools/call",
            {
                "name": "djass_create_project",
                "arguments": {"project_name": "Denied", "project_slug": "denied"},
            },
        ),
        content_type="application/json",
        HTTP_X_API_KEY=key.key,
    )

    assert response.status_code == 403
    assert response.json()["error"]["data"]["code"] == "insufficient_scope"


@pytest.mark.django_db
def test_mcp_prompt_endpoint_contains_current_options(client):
    response = client.get("/api/mcp/prompt")

    assert response.status_code == 200
    body = response.json()
    assert "MCP endpoint" in body["prompt"]
    assert "use_logfire" in {field["name"] for field in body["options"]["fields"]}
