import pytest
from django.urls import reverse

from apps.core.choices import ProfileStates


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
