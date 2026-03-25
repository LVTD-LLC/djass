import pytest
from django.contrib.messages import get_messages
from django.test import RequestFactory, override_settings
from django.urls import reverse

from apps.core.choices import ProfileStates
from apps.pages.views import SignupTrackingMixin

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(
        username="testuser",
        email="testuser@example.com",
        password="password123",
    )


@pytest.fixture
def auth_client(client, user):
    client.force_login(user)
    return client


def test_pricing_page_shows_product_led_one_time_copy(client):
    response = client.get(reverse("pricing"))
    assert response.status_code == 200

    content = response.content.decode()
    assert "$999" in content
    assert "founders and teams shipping Django SaaS repeatedly" in content
    assert "Unlimited starter generations for new SaaS products, experiments, and internal tools" in content
    assert "Djass Premium Agency Plan" not in content
    assert "client SaaS repeatedly" not in content


def test_pricing_checkout_failed_queues_tracking_event(auth_client, monkeypatch, user):
    calls = []

    def fake_async_task(*args, **kwargs):
        calls.append((args, kwargs))
        return "task-id"

    monkeypatch.setattr("apps.pages.views.async_task", fake_async_task)

    response = auth_client.get(f"{reverse('pricing')}?checkout=failed")
    assert response.status_code == 200

    tracking_call = next(call for call in calls if call[0][0] == "apps.core.tasks.track_event")
    assert tracking_call[1]["profile_id"] == user.profile.id
    assert tracking_call[1]["event_name"] == "checkout_failed"
    assert tracking_call[1]["properties"]["reason"] == "failed"
    assert tracking_call[1]["properties"]["entrypoint"] == "ui"


def test_login_page_hides_passkey_option(client):
    response = client.get(reverse("account_login"))
    assert response.status_code == 200

    content = response.content.decode()
    assert "Sign in with a passkey" not in content
    assert 'id="mfa_login"' not in content
    assert 'name="login"' in content


def test_signup_page_hides_passkey_option(client):
    response = client.get(reverse("account_signup"))
    assert response.status_code == 200

    content = response.content.decode()
    assert "Sign up using a passkey" not in content


def test_signup_page_is_email_only(client):
    response = client.get(reverse("account_signup"))
    assert response.status_code == 200

    content = response.content.decode()
    assert 'name="email"' in content
    assert 'name="username"' not in content
    assert 'name="password1"' in content
    assert 'name="password2"' not in content


def test_email_verification_sent_page_uses_branded_template(client):
    response = client.get(reverse("account_email_verification_sent"))
    assert response.status_code == 200

    content = response.content.decode()
    assert "Check your inbox" in content
    assert "Continue to dashboard" in content


def test_signup_redirects_to_dashboard_without_blocking_on_email_confirmation(client, monkeypatch):
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
    assert response.url == reverse("home")


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


def test_passkey_signup_page_is_disabled(client):
    response = client.get("/accounts/signup/passkey/")
    assert response.status_code == 404


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
    assert "Open your dashboard" in content
    assert "See pricing and what’s included" in content
    assert reverse("home") in content
    assert reverse("pricing") in content


def test_landing_subscribed_user_gets_primary_signup_cta(auth_client, user):
    user.profile.state = ProfileStates.SUBSCRIBED
    user.profile.save(update_fields=["state"])

    response = auth_client.get(reverse("landing"))
    assert response.status_code == 200

    content = response.content.decode()
    assert "Open your dashboard" in content
    assert "See pricing and what’s included" in content
    assert reverse("home") in content
    assert reverse("pricing") in content


def test_landing_and_pricing_copy_is_product_led(client):
    landing_response = client.get(reverse("landing"))
    assert landing_response.status_code == 200
    landing_content = landing_response.content.decode()
    assert "hosted workflow for <strong>django-saas-starter</strong>" in landing_content
    assert "Founders, product teams, and solo builders" in landing_content
    assert "How it works" in landing_content
    assert "UI flow" in landing_content
    assert "API flow" in landing_content
    assert "Djass generates in the background" in landing_content
    assert "agency" not in landing_content.lower()

    pricing_response = client.get(reverse("pricing"))
    assert pricing_response.status_code == 200
    pricing_content = pricing_response.content.decode()
    assert "One plan for serious Django SaaS work" in pricing_content
    assert "founders and teams shipping Django SaaS repeatedly" in pricing_content
    assert "Review the open-source baseline" in pricing_content
    assert "Need full control?" not in pricing_content
    assert "self-host for free" not in pricing_content
    assert "agency" not in pricing_content.lower()


def test_landing_guest_ctas_explain_destination(client):
    response = client.get(reverse("landing"))
    assert response.status_code == 200

    content = response.content.decode()
    assert "Create your Djass account" in content
    assert "Create an account to configure your starter, run generation, and track project history." in content
    assert "Sign in to your dashboard" in content
    assert "Go to your existing Djass account and continue from your project dashboard." in content


def test_signup_cta_copy_does_not_use_free_trial_language(client):
    landing_response = client.get(reverse("landing"))
    assert landing_response.status_code == 200
    landing_content = landing_response.content.decode()
    assert "Create your Djass account" in landing_content
    assert "Start for Free" not in landing_content

    pricing_response = client.get(reverse("pricing"))
    assert pricing_response.status_code == 200
    pricing_content = pricing_response.content.decode()
    assert "Create account to unlock premium access" in pricing_content
    assert "Start for Free" not in pricing_content
