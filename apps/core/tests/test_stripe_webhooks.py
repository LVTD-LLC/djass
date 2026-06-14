from unittest.mock import patch

import pytest

from apps.core.choices import ProfileStates
from apps.core.models import LaunchPriceReservation, Profile
from apps.core.stripe_webhooks import (
    handle_checkout_completed,
    handle_created_subscription,
    handle_deleted_subscription,
    handle_updated_subscription,
)
from apps.core.tests.test_helpers import build_checkout_completed_event, build_subscription_event


@pytest.mark.django_db
def test_handle_created_subscription_starts_trial(sync_state_transitions, profile):
    event = build_subscription_event(
        status="trialing",
        customer_id="cus_trial",
        subscription_id="sub_trial",
        metadata={"user_id": profile.user_id},
        trial_end=1_700_000_000,
    )

    handle_created_subscription(event)

    profile.refresh_from_db()
    assert profile.stripe_customer_id == "cus_trial"
    assert profile.stripe_subscription_id == "sub_trial"
    assert profile.state == ProfileStates.TRIAL_STARTED


@pytest.mark.django_db
def test_handle_updated_subscription_marks_cancelled(sync_state_transitions, profile):
    event = build_subscription_event(
        status="active",
        customer_id="cus_cancel",
        subscription_id="sub_cancel",
        metadata={"user_id": profile.user_id},
        cancel_at_period_end=True,
        current_period_end=1_700_000_100,
    )

    handle_updated_subscription(event)

    profile.refresh_from_db()
    assert profile.stripe_customer_id == "cus_cancel"
    assert profile.stripe_subscription_id == "sub_cancel"
    assert profile.state == ProfileStates.CANCELLED


@pytest.mark.django_db
def test_handle_updated_subscription_marks_cancelled_on_cancel_at(sync_state_transitions, profile):
    event = build_subscription_event(
        status="active",
        customer_id="cus_cancel_at",
        subscription_id="sub_cancel_at",
        metadata={"user_id": profile.user_id},
        cancel_at_period_end=False,
        cancel_at=1_700_000_100,
    )

    handle_updated_subscription(event)

    profile.refresh_from_db()
    assert profile.state == ProfileStates.CANCELLED


@pytest.mark.django_db
def test_handle_updated_subscription_marks_trial_ended(sync_state_transitions, profile):
    event = build_subscription_event(
        status="canceled",
        customer_id="cus_trial_end",
        subscription_id="sub_trial_end",
        metadata={"user_id": profile.user_id},
    )
    event["data"]["previous_attributes"] = {"status": "trialing"}

    handle_updated_subscription(event)

    profile.refresh_from_db()
    assert profile.state == ProfileStates.TRIAL_ENDED


@pytest.mark.django_db
def test_handle_deleted_subscription_churns_and_clears_subscription_id(
    sync_state_transitions, profile
):
    Profile.objects.filter(id=profile.id).update(
        stripe_customer_id="cus_deleted",
        stripe_subscription_id="sub_deleted",
        state=ProfileStates.SUBSCRIBED,
    )

    event = build_subscription_event(
        status="canceled",
        customer_id="cus_deleted",
        subscription_id="sub_deleted",
        ended_at=1_700_000_200,
    )

    handle_deleted_subscription(event)

    profile.refresh_from_db()
    assert profile.state == ProfileStates.CHURNED
    assert profile.stripe_subscription_id == ""


@pytest.mark.django_db
def test_handle_checkout_completed_payment_grants_access(sync_state_transitions, profile):
    event = build_checkout_completed_event(
        customer_id="cus_paid",
        checkout_id="cs_paid",
        payment_status="paid",
        mode="payment",
        metadata={
            "user_id": profile.user_id,
            "price_id": "price_one_time",
            "plan": "one-time",
        },
        amount_total=2500,
        currency="usd",
        payment_intent="pi_paid",
    )

    with patch("apps.core.stripe_webhooks.core_tasks.track_event") as track_event:
        reservation = LaunchPriceReservation.objects.create(
            user=profile.user,
            tier_key="launch_10",
            amount_cents=1000,
            stripe_checkout_session_id="cs_paid",
        )
        handle_checkout_completed(event)

    profile.refresh_from_db()
    reservation.refresh_from_db()
    assert profile.stripe_customer_id == "cus_paid"
    assert profile.state == ProfileStates.SUBSCRIBED
    assert profile.current_state == ProfileStates.SUBSCRIBED
    assert reservation.status == LaunchPriceReservation.Status.PAID
    assert reservation.stripe_payment_intent == "pi_paid"
    track_event.assert_called_once_with(
        profile_id=profile.id,
        event_name="checkout_succeeded",
        properties={
            "checkout_id": "cs_paid",
            "payment_intent": "pi_paid",
            "amount": 2500,
            "currency": "usd",
            "price_id": "price_one_time",
            "plan": "one-time",
            "funnel_step": "checkout_succeeded",
            "entrypoint": "api",
            "stripe_event_id": event["id"],
        },
        source_function="stripe_webhook handle_checkout_completed",
    )


@pytest.mark.django_db
def test_handle_checkout_completed_is_idempotent_by_checkout_id(sync_state_transitions, profile):
    event = build_checkout_completed_event(
        customer_id="cus_paid",
        checkout_id="cs_idempotent",
        payment_status="paid",
        mode="payment",
        metadata={"user_id": profile.user_id, "price_id": "price_one_time"},
        amount_total=120000,
        currency="usd",
        payment_intent="pi_idempotent",
    )

    with (
        patch("apps.core.stripe_webhooks.core_tasks.track_state_change") as track_state_change,
        patch("apps.core.stripe_webhooks.core_tasks.track_event") as track_event,
    ):
        handle_checkout_completed(event)
        handle_checkout_completed(event)

    assert track_state_change.call_count == 1
    assert track_event.call_count == 1


@pytest.mark.django_db
def test_handle_checkout_completed_tracks_payment_failure_event(sync_state_transitions, profile):
    event = build_checkout_completed_event(
        customer_id="cus_unpaid",
        checkout_id="cs_unpaid",
        payment_status="unpaid",
        mode="payment",
        metadata={
            "user_id": profile.user_id,
            "price_id": "price_one_time",
            "plan": "one-time",
        },
        payment_intent="pi_unpaid",
    )

    with (
        patch("apps.core.stripe_webhooks.core_tasks.track_state_change") as track_state_change,
        patch("apps.core.stripe_webhooks.core_tasks.track_event") as track_event,
    ):
        reservation = LaunchPriceReservation.objects.create(
            user=profile.user,
            tier_key="launch_10",
            amount_cents=1000,
            stripe_checkout_session_id="cs_unpaid",
        )
        handle_checkout_completed(event)

    reservation.refresh_from_db()
    assert reservation.status == LaunchPriceReservation.Status.CANCELED
    assert reservation.canceled_reason == "payment_not_paid"
    track_state_change.assert_not_called()
    track_event.assert_called_once_with(
        profile_id=profile.id,
        event_name="checkout_failed",
        properties={
            "checkout_id": "cs_unpaid",
            "payment_status": "unpaid",
            "mode": "payment",
            "price_id": "price_one_time",
            "plan": "one-time",
            "reason": "payment_not_paid",
            "funnel_step": "checkout_failed",
            "entrypoint": "api",
            "stripe_event_id": event["id"],
        },
        source_function="stripe_webhook handle_checkout_completed",
    )


@pytest.mark.django_db
def test_handle_checkout_completed_falls_back_to_client_reference_id(
    sync_state_transitions, profile
):
    event = build_checkout_completed_event(
        customer_id="",
        checkout_id="cs_ref_only",
        payment_status="paid",
        mode="payment",
        metadata={"price_id": "price_one_time", "plan": "one-time"},
        client_reference_id=str(profile.user_id),
        amount_total=99900,
        currency="usd",
        payment_intent="pi_ref_only",
    )

    with patch("apps.core.stripe_webhooks.core_tasks.track_event"):
        handle_checkout_completed(event)

    profile.refresh_from_db()
    assert profile.state == ProfileStates.SUBSCRIBED


@pytest.mark.django_db
def test_handle_checkout_completed_falls_back_to_customer_email(sync_state_transitions, profile):
    event = build_checkout_completed_event(
        customer_id="",
        checkout_id="cs_email_only",
        payment_status="paid",
        mode="payment",
        metadata={"price_id": "price_one_time", "plan": "one-time"},
        customer_details={"email": profile.user.email},
        amount_total=99900,
        currency="usd",
        payment_intent="pi_email_only",
    )

    with patch("apps.core.stripe_webhooks.core_tasks.track_event"):
        handle_checkout_completed(event)

    profile.refresh_from_db()
    assert profile.state == ProfileStates.SUBSCRIBED
