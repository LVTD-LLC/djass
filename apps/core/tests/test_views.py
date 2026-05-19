import pytest
from allauth.account.models import EmailAddress
from django.test import override_settings
from django.urls import reverse

from apps.core.choices import ProfileStates
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

    def test_home_shows_generation_locked_state(self, auth_client):
        response = auth_client.get(reverse("home"))
        assert response.status_code == 200
        assert "Generation locked" in response.content.decode()

    def test_home_shows_generation_unlocked_state(self, auth_client, user):
        profile = user.profile
        profile.state = ProfileStates.SUBSCRIBED
        profile.save(update_fields=["state"])

        response = auth_client.get(reverse("home"))
        assert response.status_code == 200
        assert "Generation unlocked" in response.content.decode()


@pytest.mark.django_db
class TestProjectCreateView:
    def test_project_create_view_shows_locked_state(self, auth_client):
        response = auth_client.get(reverse("project_new"))
        assert response.status_code == 200
        assert "Generation is locked" in response.content.decode()

    def test_project_create_view_shows_unlocked_state(self, auth_client, user):
        profile = user.profile
        profile.state = ProfileStates.SUBSCRIBED
        profile.save(update_fields=["state"])

        response = auth_client.get(reverse("project_new"))
        assert response.status_code == 200
        assert "Generation is unlocked" in response.content.decode()

    def test_project_create_view_renders_current_generator_options(self, auth_client):
        response = auth_client.get(reverse("project_new"))

        assert response.status_code == 200
        content = response.content.decode()
        assert "Use Chatwoot" in content
        assert 'name="use_chatwoot"' in content
        assert "Use MCP" in content
        assert 'name="use_mcp"' in content


@pytest.mark.django_db
def test_settings_upgrade_copy(auth_client, user):
    EmailAddress.objects.create(user=user, email=user.email, verified=False, primary=True)
    response = auth_client.get(reverse("settings"))
    assert response.status_code == 200

    content = response.content.decode()
    assert "$999 one-time" in content
    assert "unlimited generations" in content.lower()
    assert "forever updates" in content.lower()


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
