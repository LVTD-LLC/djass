import pytest
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


def test_pricing_page_shows_one_time_copy(client):
    response = client.get(reverse("pricing"))
    assert response.status_code == 200

    content = response.content.decode()
    assert "$999" in content
    assert "Unlimited project generations for client and internal products" in content
    assert "Lifetime updates to the starter" in content


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


def test_login_page_shows_passkey_option(client):
    response = client.get(reverse("account_login"))
    assert response.status_code == 200

    content = response.content.decode()
    assert "Sign in with a passkey" in content
    assert 'id="mfa_login"' in content
    assert 'name="login"' in content


def test_signup_page_shows_passkey_option(client):
    response = client.get(reverse("account_signup"))
    assert response.status_code == 200

    content = response.content.decode()
    assert "Sign up using a passkey" in content


def test_signup_page_is_email_only(client):
    response = client.get(reverse("account_signup"))
    assert response.status_code == 200

    content = response.content.decode()
    assert 'name="email"' in content
    assert 'name="username"' not in content


@override_settings(ACCOUNT_EMAIL_VERIFICATION="none")
def test_signup_without_username_creates_user(client, django_user_model):
    response = client.post(
        reverse("account_signup"),
        data={
            "email": "email-only-user@example.com",
            "password1": "StrongPass123!!",
            "password2": "StrongPass123!!",
        },
    )

    assert response.status_code == 302
    user = django_user_model.objects.get(email="email-only-user@example.com")
    assert user.username


def test_passkey_signup_page_uses_custom_template(client):
    response = client.get(reverse("account_signup_by_passkey"))
    assert response.status_code == 200

    content = response.content.decode()
    assert "Create your account with a passkey" in content
    assert "Continue with passkey" in content


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


def test_landing_authenticated_user_gets_pricing_cta(auth_client, user):
    response = auth_client.get(reverse("landing"))
    assert response.status_code == 200

    content = response.content.decode()
    assert "See the premium agency plan" in content
    assert reverse("pricing") in content


def test_landing_subscribed_user_gets_pricing_cta(auth_client, user):
    user.profile.state = ProfileStates.SUBSCRIBED
    user.profile.save(update_fields=["state"])

    response = auth_client.get(reverse("landing"))
    assert response.status_code == 200

    content = response.content.decode()
    assert "See the premium agency plan" in content
    assert reverse("pricing") in content
