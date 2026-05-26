import pytest
from django.contrib.messages import get_messages
from django.urls import reverse

from apps.core.choices import ProfileStates
from apps.core.generator_options import (
    GeneratorField,
    GeneratorOptionCatalog,
    GeneratorOptionCategory,
)
from apps.core.models import Profile, Project, ProjectArtifact, ProjectStatus
from apps.core.views import _build_project_payload_sections


def _valid_project_post_data(**overrides):
    data = {
        "name": "My project card",
        "project_name": "My SaaS",
        "project_slug": "my_saas",
        "caprover_app_name": "my-saas",
        "repo_url": "https://github.com/gregagi/my-saas",
        "project_description": "test",
        "author_name": "Rasul",
        "author_email": "rasul@example.com",
        "author_url": "",
        "project_main_color": "green",
        "use_posthog": "y",
        "use_chatwoot": "n",
        "use_s3": "y",
        "use_stripe": "y",
        "use_sentry": "y",
        "generate_blog": "y",
        "generate_docs": "y",
        "use_mjml": "y",
        "use_ai": "y",
        "use_logfire": "y",
        "use_healthchecks": "y",
        "use_apprise": "n",
        "use_mcp": "n",
        "use_ci": "y",
        "use_digitalocean": "n",
    }
    data.update(overrides)
    return data


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
                "caprover_app_name": "my-saas",
                "repo_url": "https://github.com/gregagi/my-saas",
                "project_description": "test",
                "author_name": "Rasul",
                "author_email": "rasul@example.com",
                "author_url": "",
                "project_main_color": "green",
                "use_posthog": "y",
                "use_chatwoot": "n",
                "use_s3": "y",
                "use_stripe": "y",
                "use_sentry": "y",
                "generate_blog": "y",
                "generate_docs": "y",
                "use_mjml": "y",
                "use_ai": "y",
                "use_logfire": "y",
                "use_healthchecks": "y",
                "use_apprise": "n",
                "use_mcp": "n",
                "use_ci": "y",
                "use_digitalocean": "n",
            },
            follow=True,
        )

        assert response.status_code == 200
        project = Project.objects.get(user=response.wsgi_request.user)
        assert project.status == ProjectStatus.QUEUED
        assert project.input_payload["use_chatwoot"] == "n"
        assert project.input_payload["use_apprise"] == "n"
        assert project.input_payload["use_mcp"] == "n"
        generation_call = next(
            call for call in calls if call[0][0] == "apps.core.tasks.generate_project_artifact"
        )
        tracking_call = next(call for call in calls if call[0][0] == "apps.core.tasks.track_event")
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
                "caprover_app_name": "my-saas",
                "repo_url": "https://github.com/gregagi/my-saas",
                "project_description": "test",
                "author_name": "Rasul",
                "author_email": "rasul@example.com",
                "author_url": "",
                "project_main_color": "green",
                "use_posthog": "y",
                "use_chatwoot": "n",
                "use_s3": "y",
                "use_stripe": "y",
                "use_sentry": "y",
                "generate_blog": "y",
                "generate_docs": "y",
                "use_mjml": "y",
                "use_ai": "y",
                "use_logfire": "y",
                "use_healthchecks": "y",
                "use_apprise": "n",
                "use_mcp": "n",
                "use_ci": "y",
                "use_digitalocean": "n",
            },
        )

        assert response.status_code == 302
        assert response.url == reverse("home")
        project = Project.objects.get(user=response.wsgi_request.user)
        generation_call = next(
            call for call in calls if call[0][0] == "apps.core.tasks.generate_project_artifact"
        )
        tracking_call = next(call for call in calls if call[0][0] == "apps.core.tasks.track_event")
        assert generation_call[1]["project_id"] == project.id
        assert tracking_call[1]["event_name"] == "project_created"
        assert tracking_call[1]["properties"]["entrypoint"] == "ui"

    def test_create_project_requires_active_access_when_payments_enabled(
        self,
        auth_client,
        monkeypatch,
        settings,
        user,
    ):
        calls = []

        def fake_async_task(*args, **kwargs):
            calls.append((args, kwargs))
            return "task-id"

        settings.PAYMENTS_ENABLED = True
        user.profile.state = ProfileStates.STRANGER
        user.profile.save(update_fields=["state"])
        user.profile.state_transitions.all().delete()
        monkeypatch.setattr("apps.core.views.async_task", fake_async_task)

        response = auth_client.post(reverse("project_create"), _valid_project_post_data())

        assert response.status_code == 302
        assert response.url == reverse("free_access")
        assert Project.objects.filter(user=user).count() == 0
        tracking_call = calls[0]
        assert tracking_call[0][0] == "apps.core.tasks.track_event"
        assert tracking_call[1]["event_name"] == "project_create_failed"
        assert tracking_call[1]["properties"]["reason"] == "subscription_required"
        assert tracking_call[1]["properties"]["entrypoint"] == "ui"

    def test_create_project_enforces_project_quota(
        self,
        auth_client,
        monkeypatch,
        settings,
        user,
    ):
        calls = []

        def fake_async_task(*args, **kwargs):
            calls.append((args, kwargs))
            return "task-id"

        settings.PROJECT_API_MAX_PROJECTS_PER_USER = 1
        monkeypatch.setattr("apps.core.views.async_task", fake_async_task)
        Project.objects.create(
            user=user,
            name="Existing Project",
            slug="existing_project",
            input_payload={"project_name": "Existing Project"},
            status=ProjectStatus.READY,
        )

        response = auth_client.post(reverse("project_create"), _valid_project_post_data())

        assert response.status_code == 302
        assert response.url == reverse("project_new")
        assert Project.objects.filter(user=user).count() == 1
        assert all(call[0][0] != "apps.core.tasks.generate_project_artifact" for call in calls)
        assert len(calls) == 1
        tracking_call = calls[0]
        assert tracking_call[0][0] == "apps.core.tasks.track_event"
        assert tracking_call[1]["event_name"] == "project_create_failed"
        assert tracking_call[1]["properties"]["reason"] == "quota_exceeded"
        assert tracking_call[1]["properties"]["quota"] == 1
        assert tracking_call[1]["properties"]["entrypoint"] == "ui"

    def test_create_project_denies_missing_profile_with_clear_message(
        self,
        auth_client,
        user,
    ):
        Profile.objects.filter(user=user).delete()
        user._state.fields_cache.pop("profile", None)

        response = auth_client.post(
            reverse("project_create"),
            _valid_project_post_data(),
            follow=True,
        )

        assert response.status_code == 200
        assert Project.objects.filter(user=user).count() == 0
        messages = [message.message for message in get_messages(response.wsgi_request)]
        expected_message = (
            "We couldn't find an account profile for your signed-in user. "
            "Please contact support before creating projects."
        )
        assert expected_message in messages
        assert "Project generation is available for signed-in accounts." not in messages

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
                "use_s3": "y",
                "use_stripe": "y",
                "use_sentry": "y",
                "generate_blog": "y",
                "generate_docs": "y",
                "use_mjml": "y",
                "use_ai": "y",
                "use_logfire": "y",
                "use_healthchecks": "y",
                "use_apprise": "n",
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
        project = Project.objects.create(
            user=user,
            name="History Project",
            slug="history_project",
            input_payload={"project_name": "History Project"},
            status=ProjectStatus.GENERATING,
        )

        response = auth_client.get(reverse("home"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "History Project" in content
        assert reverse("project_detail", args=[project.id]) in content

    def test_project_detail_shows_stored_generator_options(self, auth_client, user):
        input_payload = _valid_project_post_data(
            project_name="History Project",
            project_slug="history_project",
            repo_url="https://github.com/example/history-project",
            use_chatwoot="n",
            use_mcp="y",
            retired_option="legacy-value",
        )
        input_payload.pop("name")
        project = Project.objects.create(
            user=user,
            name="History Project",
            slug="history_project",
            input_payload=input_payload,
            status=ProjectStatus.READY,
        )

        response = auth_client.get(reverse("project_detail", args=[project.id]))

        assert response.status_code == 200
        content = response.content.decode()
        assert "History Project" in content
        assert "Generator options" in content
        assert "Project settings" in content
        assert "https://github.com/example/history-project" in content
        assert "Use Chatwoot" in content
        assert "Use MCP" in content
        assert "Legacy options" in content
        assert "retired_option" in content
        assert "legacy-value" in content

    def test_project_detail_denies_other_users_project(self, auth_client, django_user_model):
        other_user = django_user_model.objects.create_user(
            username="project-owner",
            email="project-owner@example.com",
            password="password123",
        )
        project = Project.objects.create(
            user=other_user,
            name="Private Project",
            slug="private_project",
            input_payload=_valid_project_post_data(project_name="Private Project"),
            status=ProjectStatus.READY,
        )

        response = auth_client.get(reverse("project_detail", args=[project.id]))

        assert response.status_code == 404

    def test_project_detail_falls_back_for_unknown_catalog_category(self, monkeypatch):
        catalog = GeneratorOptionCatalog(
            fields=(
                GeneratorField("project_name", "My Project", "Project Name"),
                GeneratorField("use_new_vendor", "n", "Use New Vendor", "future", True),
            ),
            categories=(GeneratorOptionCategory("monitoring", "Monitoring"),),
        )
        monkeypatch.setattr("apps.core.views.get_generator_option_catalog", lambda: catalog)

        sections = _build_project_payload_sections(
            {"project_name": "History Project", "use_new_vendor": "y"}
        )

        other_section = next(section for section in sections if section["key"] == "other")
        assert other_section["label"] == "Other"
        assert other_section["options"] == [
            {
                "key": "use_new_vendor",
                "label": "Use New Vendor",
                "display_value": "Yes",
                "pill_class": "dj-pill dj-pill-success",
            }
        ]
