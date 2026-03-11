import pytest
from django.test import RequestFactory
from django.urls import reverse

from apps.core.choices import ProfileStates
from apps.pages.views import SignupTrackingMixin

pytestmark = pytest.mark.django_db


def test_pricing_page_shows_one_time_copy(client):
    response = client.get(reverse("pricing"))
    assert response.status_code == 200

    content = response.content.decode()
    assert "$1,200" in content
    assert "Unlimited project generations" in content
    assert "Forever updates" in content


def test_login_page_shows_passkey_option(client):
    response = client.get(reverse("account_login"))
    assert response.status_code == 200

    content = response.content.decode()
    assert "Sign in with a passkey" in content
    assert 'id="mfa_login"' in content


def test_signup_page_shows_passkey_option(client):
    response = client.get(reverse("account_signup"))
    assert response.status_code == 200

    content = response.content.decode()
    assert "Sign up using a passkey" in content


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


def test_landing_authenticated_user_gets_checkout_cta(auth_client, user):
    response = auth_client.get(reverse("landing"))
    assert response.status_code == 200

    content = response.content.decode()
    assert "Get premium access — $1,200" in content
    assert reverse("user_upgrade_checkout_session", args=[user.id, "one-time"]) in content


def test_landing_subscribed_user_gets_onboarding_cta(auth_client, user):
    user.profile.state = ProfileStates.SUBSCRIBED
    user.profile.save(update_fields=["state"])

    response = auth_client.get(reverse("landing"))
    assert response.status_code == 200

    content = response.content.decode()
    assert "Start onboarding" in content
    assert reverse("project_new") in content
