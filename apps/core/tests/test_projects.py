import pytest
from django.urls import reverse

from apps.core.models import Project, ProjectArtifact, ProjectStatus


@pytest.mark.django_db
class TestProjectFlow:
    def test_create_project_queues_job(self, auth_client, monkeypatch, user):
        calls = []

        def fake_async_task(*args, **kwargs):
            calls.append((args, kwargs))
            return "task-id"

        monkeypatch.setattr("apps.core.views.async_task", fake_async_task)

        response = auth_client.post(
            reverse("project_create"),
            {
                "name": "My project card",
                "project_name": "My SaaS",
                "project_slug": "my_saas",
                "repo_url": "https://github.com/gregagi/my-saas",
                "project_description": "test",
                "author_name": "Rasul",
                "author_email": "rasul@example.com",
                "author_url": "",
                "project_main_color": "green",
                "use_posthog": "y",
                "use_chatwoot": "n",
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
                "use_mcp": "n",
                "use_ci": "y",
            },
            follow=True,
        )

        assert response.status_code == 200
        project = Project.objects.get(user=response.wsgi_request.user)
        assert project.status == ProjectStatus.QUEUED
        assert project.input_payload["use_chatwoot"] == "n"
        assert project.input_payload["use_mcp"] == "n"
        generation_call = next(
            call for call in calls if call[0][0] == "apps.core.tasks.generate_project_artifact"
        )
        tracking_call = next(
            call for call in calls if call[0][0] == "apps.core.tasks.track_event"
        )
        assert generation_call[1]["project_id"] == project.id
        assert tracking_call[1]["event_name"] == "project_created"
        assert tracking_call[1]["profile_id"] == user.profile.id
        assert tracking_call[1]["properties"]["project_id"] == project.id
        assert tracking_call[1]["properties"]["entrypoint"] == "ui"

    def test_create_project_is_available_to_signed_in_users(self, auth_client, monkeypatch):
        calls = []

        def fake_async_task(*args, **kwargs):
            calls.append((args, kwargs))
            return "task-id"

        monkeypatch.setattr("apps.core.views.async_task", fake_async_task)

        response = auth_client.post(
            reverse("project_create"),
            {
                "name": "My project card",
                "project_name": "My SaaS",
                "project_slug": "my_saas",
                "repo_url": "https://github.com/gregagi/my-saas",
                "project_description": "test",
                "author_name": "Rasul",
                "author_email": "rasul@example.com",
                "author_url": "",
                "project_main_color": "green",
                "use_posthog": "y",
                "use_chatwoot": "n",
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
                "use_mcp": "n",
                "use_ci": "y",
            },
        )

        assert response.status_code == 302
        assert response.url == reverse("home")
        project = Project.objects.get(user=response.wsgi_request.user)
        generation_call = next(
            call for call in calls if call[0][0] == "apps.core.tasks.generate_project_artifact"
        )
        tracking_call = next(
            call for call in calls if call[0][0] == "apps.core.tasks.track_event"
        )
        assert generation_call[1]["project_id"] == project.id
        assert tracking_call[1]["event_name"] == "project_created"
        assert tracking_call[1]["properties"]["entrypoint"] == "ui"

    def test_create_project_validation_failure_queues_tracking_event(
        self,
        auth_client,
        monkeypatch,
        user,
    ):
        calls = []

        def fake_async_task(*args, **kwargs):
            calls.append((args, kwargs))
            return "task-id"

        monkeypatch.setattr("apps.core.views.async_task", fake_async_task)

        response = auth_client.post(
            reverse("project_create"),
            {
                "project_name": "My SaaS",
                "project_slug": "",
                "repo_url": "https://github.com/gregagi/my-saas",
                "project_description": "test",
                "author_name": "Rasul",
                "author_email": "rasul@example.com",
                "author_url": "",
                "project_main_color": "green",
                "use_posthog": "y",
                "use_chatwoot": "n",
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
                "use_mcp": "n",
                "use_ci": "y",
            },
        )

        assert response.status_code == 302
        assert response.url == reverse("project_new")
        assert Project.objects.filter(user=user).count() == 0
        assert len(calls) == 1
        tracking_call = calls[0]
        assert tracking_call[0][0] == "apps.core.tasks.track_event"
        assert tracking_call[1]["event_name"] == "project_create_failed"
        assert tracking_call[1]["properties"]["reason"] == "validation_error"
        assert "project_slug" in tracking_call[1]["properties"]["validation_fields"]
        assert tracking_call[1]["properties"]["funnel_step"] == "project_create_failed"
        assert tracking_call[1]["properties"]["entrypoint"] == "ui"

    def test_retry_project_is_available_to_signed_in_users(self, auth_client, user, monkeypatch):
        calls = []

        def fake_async_task(*args, **kwargs):
            calls.append((args, kwargs))
            return "task-id"

        monkeypatch.setattr("apps.core.views.async_task", fake_async_task)
        project = Project.objects.create(
            user=user,
            name="Retry Project",
            slug="retry_project",
            input_payload={"project_name": "Retry Project"},
            status=ProjectStatus.FAILED,
            error_message="boom",
        )

        response = auth_client.post(reverse("project_retry", args=[project.id]))

        assert response.status_code == 302
        assert response.url == reverse("home")
        project.refresh_from_db()
        assert project.status == ProjectStatus.QUEUED
        generation_call = next(
            call for call in calls if call[0][0] == "apps.core.tasks.generate_project_artifact"
        )
        assert generation_call[1]["project_id"] == project.id

    def test_download_denies_other_user(self, auth_client, django_user_model):
        other_user = django_user_model.objects.create_user(
            username="other",
            email="other@example.com",
            password="password123",
        )
        project = Project.objects.create(
            user=other_user,
            name="Other Project",
            slug="other_project",
            input_payload={"project_name": "Other"},
            status=ProjectStatus.READY,
        )
        ProjectArtifact.objects.create(project=project, zip_file="generated-projects/test.zip")

        response = auth_client.get(reverse("project_download", args=[project.id]))
        assert response.status_code == 404

    def test_home_lists_projects(self, auth_client, user):
        Project.objects.create(
            user=user,
            name="History Project",
            slug="history_project",
            input_payload={"project_name": "History Project"},
            status=ProjectStatus.GENERATING,
        )

        response = auth_client.get(reverse("home"))
        assert response.status_code == 200
        assert "History Project" in response.content.decode()
