import pytest

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
