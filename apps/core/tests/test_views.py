import pytest
from allauth.account.internal.flows.email_verification_by_code import (
    EMAIL_VERIFICATION_CODE_SESSION_KEY,
)
from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.messages import get_messages
from django.test import override_settings
from django.urls import reverse

from apps.core.choices import ProfileStates
from apps.core.models import Profile, Project, ProjectStatus
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

    def test_home_shows_generation_locked_by_default(self, auth_client):
        response = auth_client.get(reverse("home"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Generation locked" in content
        assert "Unlock for $10" in content

    def test_home_shows_generation_unlocked_for_paid_user(self, auth_client, user):
        user.profile.state = ProfileStates.SUBSCRIBED
        user.profile.save(update_fields=["state"])

        response = auth_client.get(reverse("home"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Create project" in content
        assert "Generation locked" not in content

    def test_authenticated_app_header_uses_account_menu(self, auth_client):
        response = auth_client.get(reverse("home"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Open account menu" in content
        assert "Skill page" not in content
        assert 'href="/uses"' not in content
        assert (
            'href="/projects/new" class="dj-button dj-button-secondary">Create</a>' not in content
        )

    def test_home_shows_short_copyable_agent_prompt(self, auth_client, user):
        user.profile.state = ProfileStates.SUBSCRIBED
        user.profile.save(update_fields=["state"])

        response = auth_client.get(reverse("home"))

        assert response.status_code == 200
        content = response.content.decode()
        assert "Agent project generator prompt" not in content
        assert "Three ways to generate a repo" in content
        assert "Copy the prompt below" not in content
        assert "Copy this short prompt" not in content
        assert "Copy prompt" in content
        assert "Copy SKILL.md" not in content
        assert "Skill page" not in content
        assert f'href="{reverse("agent_skill")}"' not in content
        assert reverse("agent_skill") in content
        assert "/skill.md" in content
        assert "OpenAPI docs" in content
        assert "MCP docs" in content
        assert "This prompt includes your Djass API key" in content
        assert "Share it only with agents and workspaces you trust" in content
        assert f"{settings.SITE_URL.rstrip('/')}{reverse('agent_skill')}" in content
        assert "https://djass.dev/api/v1" in content
        assert "http://testserver/api/v1" not in content
        assert user.profile.key in content
        assert 'id="djass-agent-prompt"' in content
        assert (
            'class="dj-input mt-3 h-64 w-full resize-y p-4 font-mono text-xs leading-5"'
            not in content
        )
        assert "---BEGIN SKILL.md---" not in content
        assert "## API Fallback Workflow" not in content

    def test_home_omits_agent_prompt_when_profile_is_missing(self, auth_client, user):
        Profile.objects.filter(user=user).delete()
        user._state.fields_cache.pop("profile", None)

        response = auth_client.get(reverse("home"))

        assert response.status_code == 200
        content = response.content.decode()
        assert "Agent project generator prompt" not in content
        assert "Copy prompt" not in content
        assert "Generation locked" in content

    @override_settings(
        CHATWOOT_BASE_URL="https://chatwoot.cap.gregagi.com",
        CHATWOOT_WEBSITE_TOKEN="testtoken",
    )
    def test_home_renders_chatwoot_widget_when_configured(self, auth_client):
        response = auth_client.get(reverse("home"))

        assert response.status_code == 200
        content = response.content.decode()
        assert 'var BASE_URL = "https://chatwoot.cap.gregagi.com";' in content
        assert 'websiteToken: "testtoken"' in content
        assert 'BASE_URL + "/packs/js/sdk.js"' in content
        assert 'data-controller="feedback"' not in content

    @override_settings(CHATWOOT_BASE_URL="", CHATWOOT_WEBSITE_TOKEN="")
    def test_home_omits_chatwoot_widget_without_config(self, auth_client):
        response = auth_client.get(reverse("home"))

        assert response.status_code == 200
        assert "window.chatwootSDK.run" not in response.content.decode()


@pytest.mark.django_db
class TestAgentSkillView:
    def test_agent_skill_endpoint_serves_plain_markdown(self, client, user):
        response = client.get(reverse("agent_skill"))

        assert response.status_code == 200
        assert response.headers["Content-Type"].startswith("text/markdown")
        content = response.content.decode()
        assert "# Djass Project Generator" in content
        assert "<html" not in content
        assert "## Preferred MCP Workflow" in content
        assert "## API Fallback Workflow" in content
        assert "GET {DJASS_BASE_URL}/project-options" in content
        assert user.profile.key not in content

    def test_legacy_agent_skill_url_redirects_to_markdown(self, client):
        response = client.get("/agent-skill")

        assert response.status_code == 301
        assert response.url == reverse("agent_skill")


@pytest.mark.django_db
class TestProjectCreateView:
    def test_project_create_view_shows_locked_state_by_default(self, auth_client):
        response = auth_client.get(reverse("project_new"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Generation is locked" in content
        assert "currently $10" in content

    def test_project_create_view_shows_unlocked_state_for_paid_user(self, auth_client, user):
        user.profile.state = ProfileStates.SUBSCRIBED
        user.profile.save(update_fields=["state"])

        response = auth_client.get(reverse("project_new"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Generation is available" in content
        assert "Generation is locked" not in content

    def test_project_create_view_renders_current_generator_options(self, auth_client, user):
        user.profile.state = ProfileStates.SUBSCRIBED
        user.profile.save(update_fields=["state"])

        response = auth_client.get(reverse("project_new"))

        assert response.status_code == 200
        content = response.content.decode()
        assert "Monitoring" in content
        assert "CX" in content
        assert "AI" in content
        assert "Use Chatwoot" in content
        assert 'name="use_chatwoot"' in content
        assert "Use Apprise" in content
        assert 'name="use_apprise"' in content
        assert "Use MCP" in content
        assert 'name="use_mcp"' in content
        assert "Backend logs use standard Python logging" in content

    def test_project_create_view_shows_project_limit_state(self, auth_client, settings, user):
        user.profile.state = ProfileStates.SUBSCRIBED
        user.profile.save(update_fields=["state"])
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
    assert "Generation is locked" in content
    assert "current launch tier is $10" in content


@pytest.mark.django_db
def test_settings_shows_copyable_agent_api_key(auth_client, user):
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)

    response = auth_client.get(reverse("settings"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Agent API key" in content
    assert "Copy key" in content
    assert "Show key" in content
    assert "X-API-Key" in content
    assert "Authorization: Bearer" in content
    assert 'type="password"' in content
    assert "X-API-Key: &lt;your-api-key&gt;" in content
    assert "Authorization: Bearer &lt;your-api-key&gt;" in content
    assert f'value="{user.profile.key}"' in content


@pytest.mark.django_db
@override_settings(ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED=False)
def test_resend_confirmation_sets_success_message_for_link_flow(
    auth_client,
    monkeypatch,
    user,
):
    EmailAddress.objects.create(user=user, email=user.email, verified=False, primary=True)
    monkeypatch.setattr(
        "apps.core.views.send_verification_email_to_address",
        lambda *args, **kwargs: True,
    )

    response = auth_client.post(reverse("resend_confirmation"), follow=True)

    assert response.status_code == 200
    messages = [message.message for message in get_messages(response.wsgi_request)]
    assert "Confirmation email sent. Please check your inbox." in messages


@pytest.mark.django_db
@override_settings(ACCOUNT_RATE_LIMITS=False)
def test_resend_confirmation_redirects_to_pending_code_process(
    auth_client,
    monkeypatch,
    user,
):
    EmailAddress.objects.create(user=user, email=user.email, verified=False, primary=True)
    sent_confirmations = []

    def fake_send_confirmation_mail(self, request, emailconfirmation, signup):
        sent_confirmations.append((emailconfirmation.email_address.email, signup))

    monkeypatch.setattr(
        "djass.adapters.CustomAccountAdapter.send_confirmation_mail",
        fake_send_confirmation_mail,
    )

    response = auth_client.post(reverse("resend_confirmation"), follow=True)

    assert response.status_code == 200
    assert response.redirect_chain == [(reverse("account_email_verification_sent"), 302)]
    assert "Enter email verification code" in response.content.decode()
    assert sent_confirmations == [(user.email, False)]
    assert auth_client.session[EMAIL_VERIFICATION_CODE_SESSION_KEY]["email"] == user.email


@override_settings(STRIPE_PRICE_IDS={"one-time": "price_one_time"})
def test_get_price_id_for_plan_one_time():
    assert get_price_id_for_plan("one-time") == "price_one_time"
    assert get_price_id_for_plan("ONE-TIME") == "price_one_time"
    assert get_price_id_for_plan("monthly") is None
    assert get_price_id_for_plan("unknown") is None
