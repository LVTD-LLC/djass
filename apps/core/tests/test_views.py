import pytest
from allauth.account.models import EmailAddress
from django.test import override_settings
from django.urls import reverse

from apps.core.models import Project, ProjectStatus
from apps.core.views import get_price_id_for_plan


@pytest.mark.django_db
class TestHomeView:
    def test_home_view_status_code(self, auth_client):
        url = reverse("home")
        response = auth_client.get(url)
        assert response.status_code == 200

    def test_home_view_uses_correct_template(self, auth_client):
        url = reverse("home")
        response = auth_client.get(url)
        assert "pages/home.html" in [t.name for t in response.templates]

    def test_home_shows_generation_unlocked_by_default(self, auth_client):
        response = auth_client.get(reverse("home"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Generation available" in content
        assert "Generation locked" not in content


@pytest.mark.django_db
class TestProjectCreateView:
    def test_project_create_view_shows_unlocked_state_by_default(self, auth_client):
        response = auth_client.get(reverse("project_new"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Generation is available" in content
        assert "Generation is locked" not in content

    def test_project_create_view_renders_current_generator_options(self, auth_client):
        response = auth_client.get(reverse("project_new"))

        assert response.status_code == 200
        content = response.content.decode()
        assert "Monitoring" in content
        assert "CX" in content
        assert "AI" in content
        assert "Use Chatwoot" in content
        assert 'name="use_chatwoot"' in content
        assert "Use MCP" in content
        assert 'name="use_mcp"' in content

    def test_project_create_view_shows_project_limit_state(self, auth_client, settings, user):
        settings.PROJECT_API_MAX_PROJECTS_PER_USER = 1
        Project.objects.create(
            user=user,
            name="Existing Project",
            slug="existing_project",
            input_payload={"project_name": "Existing Project"},
            status=ProjectStatus.READY,
        )

        response = auth_client.get(reverse("project_new"))

        assert response.status_code == 200
        content = response.content.decode()
        assert "This account has reached the current project limit." in content
        assert "Generation is available" not in content
        assert "disabled" in content


@pytest.mark.django_db
def test_settings_omits_upgrade_copy(auth_client, user):
    EmailAddress.objects.create(user=user, email=user.email, verified=False, primary=True)
    response = auth_client.get(reverse("settings"))
    assert response.status_code == 200

    content = response.content.decode()
    assert "Upgrade Your Account" not in content
    assert "$999" not in content
    assert "premium" not in content.lower()


@pytest.mark.django_db
def test_settings_shows_copyable_agent_api_key(auth_client, user):
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)

    response = auth_client.get(reverse("settings"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Agent API key" in content
    assert "Copy key" in content
    assert "X-API-Key" in content
    assert "Authorization: Bearer" in content
    assert f'value="{user.profile.key}"' in content


@override_settings(STRIPE_PRICE_IDS={"one-time": "price_one_time"})
def test_get_price_id_for_plan_one_time():
    assert get_price_id_for_plan("one-time") == "price_one_time"
    assert get_price_id_for_plan("ONE-TIME") == "price_one_time"
    assert get_price_id_for_plan("monthly") is None
    assert get_price_id_for_plan("unknown") is None
