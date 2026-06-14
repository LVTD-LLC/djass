import pytest
from allauth.account.models import EmailAddress
from django.contrib.messages import get_messages
from django.test import RequestFactory, override_settings
from django.urls import reverse

from apps.core.choices import ProfileStates
from apps.pages.views import SignupTrackingMixin

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(django_user_model):
    user = django_user_model.objects.create_user(
        username="testuser",
        email="testuser@example.com",
        password="password123",
    )
    EmailAddress.objects.create(
        user=user,
        email=user.email,
        primary=True,
        verified=True,
    )
    return user


@pytest.fixture
def auth_client(client, user):
    client.force_login(user)
    return client


@pytest.fixture(autouse=True)
def disable_async_task_side_effects(monkeypatch, settings):
    settings.STORAGES["staticfiles"]["BACKEND"] = (
        "django.contrib.staticfiles.storage.StaticFilesStorage"
    )
    settings.ACCOUNT_RATE_LIMITS = False
    monkeypatch.setattr("apps.core.models.async_task", lambda *args, **kwargs: None)
    monkeypatch.setattr("apps.core.signals.async_task", lambda *args, **kwargs: None)
    monkeypatch.setattr("apps.pages.views.async_task", lambda *args, **kwargs: None)


def test_pricing_page_shows_crossed_out_lifetime_price(client):
    response = client.get(reverse("pricing"))
    assert response.status_code == 200

    content = response.content.decode()
    assert "$10" in content
    assert "$100" in content
    assert "$200" in content
    assert "$999" in content
    assert "Launch pricing" in content
    assert "Paid members only can generate projects" in content


@override_settings(
    CHATWOOT_BASE_URL="https://chatwoot.cap.gregagi.com",
    CHATWOOT_WEBSITE_TOKEN="testtoken",
)
def test_landing_base_renders_chatwoot_widget_when_configured(client):
    response = client.get(reverse("landing"))

    assert response.status_code == 200
    content = response.content.decode()
    assert 'var BASE_URL = "https://chatwoot.cap.gregagi.com";' in content
    assert 'websiteToken: "testtoken"' in content


@override_settings(CHATWOOT_BASE_URL="", CHATWOOT_WEBSITE_TOKEN="")
def test_privacy_policy_omits_chatwoot_when_widget_is_not_configured(client):
    response = client.get(reverse("privacy_policy"))

    assert response.status_code == 200
    assert "Chatwoot for customer support chat" not in response.content.decode()


@override_settings(CHATWOOT_BASE_URL="https://chatwoot.example.com", CHATWOOT_WEBSITE_TOKEN="token")
def test_privacy_policy_lists_chatwoot_when_widget_is_configured(client):
    response = client.get(reverse("privacy_policy"))

    assert response.status_code == 200
    assert "Chatwoot for customer support chat" in response.content.decode()


def test_pricing_page_ignores_legacy_checkout_params(auth_client, monkeypatch):
    calls = []

    def fake_async_task(*args, **kwargs):
        calls.append((args, kwargs))
        return "task-id"

    monkeypatch.setattr("apps.pages.views.async_task", fake_async_task)

    response = auth_client.get(f"{reverse('pricing')}?checkout=failed")
    assert response.status_code == 200

    assert calls == []


def test_legacy_free_access_url_redirects_to_pricing(client):
    response = client.get(reverse("free_access"))

    assert response.status_code == 301
    assert response.url == reverse("pricing")


def test_login_page_shows_passkey_option(client):
    response = client.get(reverse("account_login"))
    assert response.status_code == 200

    content = response.content.decode()
    assert "Sign in with a passkey" in content
    assert 'id="mfa_login"' in content
    assert 'name="login"' in content


def test_login_page_accepts_username_or_email_input(client):
    response = client.get(reverse("account_login"))
    assert response.status_code == 200

    content = response.content.decode()
    assert "Username or email" in content
    assert 'type="text"' in content
    assert 'autocomplete="username"' in content


def test_login_accepts_email(client, user):
    response = client.post(
        reverse("account_login"),
        data={"login": user.email, "password": "password123"},
    )

    assert response.status_code == 302
    assert response.url == reverse("home")


def test_login_accepts_username(client, user):
    response = client.post(
        reverse("account_login"),
        data={"login": user.username, "password": "password123"},
    )

    assert response.status_code == 302
    assert response.url == reverse("home")


def test_signup_page_shows_passkey_option(client):
    response = client.get(reverse("account_signup"))
    assert response.status_code == 200

    content = response.content.decode()
    assert "Create account with a passkey" in content


def test_signup_page_is_email_only(client):
    response = client.get(reverse("account_signup"))
    assert response.status_code == 200

    content = response.content.decode()
    assert 'name="email"' in content
    assert 'name="username"' not in content
    assert 'name="password1"' in content
    assert 'name="password2"' not in content


@override_settings(ALLOW_SIGNUPS=False)
def test_signup_page_is_closed_when_signups_are_disabled(client):
    response = client.get(reverse("account_signup"))
    assert response.status_code == 200

    content = response.content.decode()
    assert "Signups are paused" in content
    assert 'name="email"' not in content
    assert "Existing users can still sign in" in content


@override_settings(ALLOW_SIGNUPS=False)
def test_signup_post_does_not_create_user_when_signups_are_disabled(client, django_user_model):
    response = client.post(
        reverse("account_signup"),
        data={
            "email": "closed-signup@example.com",
            "password1": "StrongPass123!!",
        },
    )

    assert response.status_code == 200
    assert "Signups are paused" in response.content.decode()
    assert not django_user_model.objects.filter(email="closed-signup@example.com").exists()


@override_settings(ALLOW_SIGNUPS=False)
def test_passkey_signup_page_is_closed_when_signups_are_disabled(client):
    response = client.get(reverse("account_signup_by_passkey"))
    assert response.status_code == 200
    assert "Signups are paused" in response.content.decode()


def test_email_verification_sent_page_requires_pending_code_process(client):
    response = client.get(reverse("account_email_verification_sent"))
    assert response.status_code == 302
    assert response.url == reverse("account_login")


def test_signup_redirects_to_email_verification_code(client, monkeypatch):
    monkeypatch.setattr(
        "allauth.account.adapter.DefaultAccountAdapter.send_confirmation_mail",
        lambda *args, **kwargs: "ok",
    )
    monkeypatch.setattr("apps.core.models.async_task", lambda *args, **kwargs: "task-id")
    monkeypatch.setattr("apps.core.signals.async_task", lambda *args, **kwargs: "task-id")
    monkeypatch.setattr("apps.pages.views.async_task", lambda *args, **kwargs: "task-id")

    response = client.post(
        reverse("account_signup"),
        data={
            "email": "signup-redirect@example.com",
            "password1": "StrongPass123!!",
        },
    )

    assert response.status_code == 302
    assert response.url == reverse("account_email_verification_sent")


def test_signup_email_verification_code_page_uses_branded_template(client, monkeypatch):
    monkeypatch.setattr(
        "allauth.account.adapter.DefaultAccountAdapter.send_confirmation_mail",
        lambda *args, **kwargs: "ok",
    )
    monkeypatch.setattr("apps.core.models.async_task", lambda *args, **kwargs: "task-id")
    monkeypatch.setattr("apps.core.signals.async_task", lambda *args, **kwargs: "task-id")
    monkeypatch.setattr("apps.pages.views.async_task", lambda *args, **kwargs: "task-id")

    response = client.post(
        reverse("account_signup"),
        data={
            "email": "signup-code@example.com",
            "password1": "StrongPass123!!",
        },
        follow=True,
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert "Enter email verification code" in content
    assert "Confirm email" in content


@override_settings(ACCOUNT_EMAIL_VERIFICATION="none")
def test_signup_without_username_creates_user(client, django_user_model, monkeypatch):
    monkeypatch.setattr("apps.core.models.async_task", lambda *args, **kwargs: "task-id")
    monkeypatch.setattr("apps.core.signals.async_task", lambda *args, **kwargs: "task-id")
    monkeypatch.setattr("apps.pages.views.async_task", lambda *args, **kwargs: "task-id")

    response = client.post(
        reverse("account_signup"),
        data={
            "email": "email-only-user@example.com",
            "password1": "StrongPass123!!",
        },
    )

    assert response.status_code == 302
    user = django_user_model.objects.get(email="email-only-user@example.com")
    assert user.username


def test_signup_survives_confirmation_mail_failure(client, django_user_model, monkeypatch):
    def _raise_mailgun_error(*args, **kwargs):
        raise RuntimeError("Mailgun API response 401: Forbidden")

    monkeypatch.setattr(
        "allauth.account.adapter.DefaultAccountAdapter.send_confirmation_mail",
        _raise_mailgun_error,
    )

    response = client.post(
        reverse("account_signup"),
        data={
            "email": "signup-mail-failure@example.com",
            "password1": "StrongPass123!!",
            "password2": "StrongPass123!!",
        },
        follow=True,
    )

    assert response.status_code == 200
    user = django_user_model.objects.get(email="signup-mail-failure@example.com")
    assert user.username
    messages = [message.message for message in get_messages(response.wsgi_request)]
    assert (
        "Your account was created, but we could not send the confirmation email right now. "
        "Please retry from your account page in a few minutes."
    ) in messages


def test_passkey_signup_page_is_enabled(client):
    response = client.get("/accounts/signup/passkey/")
    assert response.status_code == 200
    assert "Create your free account with a passkey" in response.content.decode()


def test_signup_tracking_mixin_queues_expected_events(monkeypatch, user):
    calls = []

    def fake_async_task(*args, **kwargs):
        calls.append((args, kwargs))
        return "task-id"

    monkeypatch.setattr("apps.pages.views.async_task", fake_async_task)

    mixin = SignupTrackingMixin()
    mixin.user = user
    mixin.request = RequestFactory().post(reverse("account_signup"))
    mixin.request.COOKIES = {}
    mixin.tracking_source_name = "SignupTrackingTest"

    mixin._track_signup()

    alias_call, signup_call = calls
    assert alias_call[0][0] == "apps.core.tasks.try_create_posthog_alias"
    assert alias_call[1]["profile_id"] == user.profile.id
    assert signup_call[0][0] == "apps.core.tasks.track_event"
    assert signup_call[1]["event_name"] == "user_signed_up"
    assert signup_call[1]["profile_id"] == user.profile.id
    assert signup_call[1]["properties"]["funnel_step"] == "signup_completed"
    assert signup_call[1]["properties"]["signup_method"] == "password"
    assert signup_call[1]["properties"]["entrypoint"] == "ui"


def test_landing_authenticated_user_gets_primary_signup_cta(auth_client, user):
    response = auth_client.get(reverse("landing"))
    assert response.status_code == 200

    content = response.content.decode()
    assert "Open dashboard" in content
    assert "Review launch pricing" in content
    assert reverse("home") in content
    assert reverse("pricing") in content


def test_landing_header_omits_stack_link(client):
    response = client.get(reverse("landing"))
    assert response.status_code == 200

    content = response.content.decode()
    assert 'href="/uses"' not in content
    assert ">Stack</a>" not in content


def test_landing_subscribed_user_gets_primary_signup_cta(auth_client, user):
    user.profile.state = ProfileStates.SUBSCRIBED
    user.profile.save(update_fields=["state"])

    response = auth_client.get(reverse("landing"))
    assert response.status_code == 200

    content = response.content.decode()
    assert "Open dashboard" in content
    assert "Review launch pricing" in content
    assert reverse("home") in content
    assert reverse("pricing") in content


def test_landing_and_pricing_copy_is_product_led(client):
    landing_response = client.get(reverse("landing"))
    assert landing_response.status_code == 200
    landing_content = landing_response.content.decode()
    assert "hosted project generator" in landing_content
    assert "Generate the codebase. Ship the product." in landing_content
    assert "useful SaaS features" in landing_content
    assert "Generate your way" in landing_content
    assert "OpenAPI docs" in landing_content
    assert "/skill.md" in landing_content
    assert "https://djass.dev/api/docs" in landing_content
    assert "AI agent handoff" in landing_content
    assert "agency" not in landing_content.lower()

    pricing_response = client.get(reverse("pricing"))
    assert pricing_response.status_code == 200
    pricing_content = pricing_response.content.decode()
    assert "Launch pricing" in pricing_content
    assert "$10" in pricing_content
    assert "$100" in pricing_content
    assert "$200" in pricing_content
    assert "$999" in pricing_content
    assert "Review the starter repository" in pricing_content
    assert "Need full control?" not in pricing_content
    assert "agency" not in pricing_content.lower()


def test_landing_guest_ctas_are_simple(client):
    response = client.get(reverse("landing"))
    assert response.status_code == 200

    content = response.content.decode()
    assert "Create account" in content
    signin_link = (
        f'href="{reverse("account_login")}" '
        'class="dj-button dj-button-secondary sm:min-w-44">Sign in</a>'
    )
    assert signin_link in content
    assert "Configure your starter, queue generation, and keep project history" not in content
    assert "Continue from your existing project dashboard." not in content


def test_signup_cta_copy_uses_pricing_language(client):
    landing_response = client.get(reverse("landing"))
    assert landing_response.status_code == 200
    landing_content = landing_response.content.decode()
    assert "Create account" in landing_content
    assert "Review launch pricing" in landing_content

    pricing_response = client.get(reverse("pricing"))
    assert pricing_response.status_code == 200
    pricing_content = pricing_response.content.decode()
    assert "Create account to buy" in pricing_content
    assert "$999" in pricing_content
