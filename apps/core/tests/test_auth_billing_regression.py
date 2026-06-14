from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.test import override_settings
from django.urls import reverse

from apps.core.choices import EmailType, ProfileStates
from apps.core.stripe_webhooks import handle_checkout_completed
from apps.core.tests.test_helpers import build_checkout_completed_event
from djass.adapters import CustomAccountAdapter


@pytest.mark.django_db
def test_signup_page_remains_email_only(client):
    response = client.get(reverse("account_signup"))

    assert response.status_code == 200
    content = response.content.decode()
    assert 'name="email"' in content
    assert 'name="username"' not in content
    assert 'name="password1"' in content
    assert 'name="password2"' not in content


@pytest.mark.django_db
def test_confirmation_mail_tracks_welcome_vs_resend(user, monkeypatch):
    adapter = CustomAccountAdapter()
    email_confirmation = SimpleNamespace(email_address=SimpleNamespace(email=user.email, user=user))

    tracked = []

    monkeypatch.setattr(
        "djass.adapters.track_email_sent",
        lambda **kwargs: tracked.append(kwargs),
    )
    monkeypatch.setattr(
        "allauth.account.adapter.DefaultAccountAdapter.send_confirmation_mail",
        lambda *args, **kwargs: "ok",
    )

    adapter.send_confirmation_mail(request=None, emailconfirmation=email_confirmation, signup=True)
    adapter.send_confirmation_mail(request=None, emailconfirmation=email_confirmation, signup=False)

    assert tracked[0]["email_type"] == EmailType.WELCOME
    assert tracked[1]["email_type"] == EmailType.EMAIL_CONFIRMATION


@override_settings(PAYMENTS_ENABLED=False)
@pytest.mark.django_db
def test_checkout_route_does_not_start_external_session(auth_client, monkeypatch):
    monkeypatch.setattr(
        "apps.core.views.stripe.checkout.Session.create",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("External session should not be created")
        ),
    )

    response = auth_client.post(reverse("user_upgrade_checkout_session", args=[1, "one-time"]))

    assert response.status_code == 302
    assert response.url == reverse("project_new")


@pytest.mark.django_db
def test_paid_checkout_unlocks_entitlement_and_generation_gate(
    sync_state_transitions,
    auth_client,
    user,
):
    user.profile.state = ProfileStates.STRANGER
    user.profile.save(update_fields=["state"])
    user.profile.state_transitions.all().delete()

    assert user.profile.state == ProfileStates.STRANGER
    assert user.profile.has_active_subscription is False
    response = auth_client.get(reverse("project_new"))
    assert response.status_code == 200
    assert "Generation is locked" in response.content.decode()

    event = build_checkout_completed_event(
        customer_id="cus_unlock",
        checkout_id="cs_unlock",
        payment_status="paid",
        mode="payment",
        metadata={"user_id": user.id, "price_id": "price_one_time", "plan": "one-time"},
        amount_total=99900,
        currency="usd",
        payment_intent="pi_unlock",
    )

    with patch("apps.core.stripe_webhooks.core_tasks.track_event"):
        handle_checkout_completed(event)

    user.profile.refresh_from_db()
    assert user.profile.state == ProfileStates.SUBSCRIBED
    assert user.profile.has_active_subscription is True


@pytest.mark.django_db
def test_paid_checkout_is_idempotent_when_checkout_id_missing(sync_state_transitions, profile):
    event = build_checkout_completed_event(
        customer_id="cus_pi_only",
        checkout_id=None,
        payment_status="paid",
        mode="payment",
        metadata={"user_id": profile.user_id, "price_id": "price_one_time", "plan": "one-time"},
        amount_total=99900,
        currency="usd",
        payment_intent="pi_only_once",
    )

    with (
        patch("apps.core.stripe_webhooks.core_tasks.track_state_change") as track_state_change,
        patch("apps.core.stripe_webhooks.core_tasks.track_event") as track_event,
    ):
        handle_checkout_completed(event)
        handle_checkout_completed(event)

    assert track_state_change.call_count == 1
    assert track_event.call_count == 1
