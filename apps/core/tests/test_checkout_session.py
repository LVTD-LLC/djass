from types import SimpleNamespace

import pytest
from django.test import override_settings
from django.urls import reverse

from apps.core.choices import ProfileStates
from apps.core.models import LaunchPriceReservation
from apps.core.pricing import get_launch_price_tier

LAUNCH_PRICE_IDS = {
    "launch_10": "price_launch_10",
    "launch_100": "price_launch_100",
    "launch_200": "price_launch_200",
    "launch_999": "price_launch_999",
}


@override_settings(PAYMENTS_ENABLED=False)
@pytest.mark.django_db
def test_disabled_payments_checkout_route_redirects_to_project_creation(auth_client, monkeypatch):
    monkeypatch.setattr(
        "apps.core.views.stripe.checkout.Session.create",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("Checkout should not be started while generation is free")
        ),
    )

    response = auth_client.post(reverse("user_upgrade_checkout_session", args=[1, "one-time"]))

    assert response.status_code == 302
    assert response.url == reverse("project_new")


@override_settings(
    PAYMENTS_ENABLED=True,
    STRIPE_PRICE_IDS=LAUNCH_PRICE_IDS,
)
@pytest.mark.django_db
def test_enabled_checkout_route_uses_current_launch_tier(auth_client, user, monkeypatch):
    captured = {}
    async_calls = []
    user.profile.state = ProfileStates.STRANGER
    user.profile.save(update_fields=["state"])

    monkeypatch.setattr(
        "apps.core.views.stripe.Price.retrieve",
        lambda *_args, **_kwargs: SimpleNamespace(unit_amount=1000),
    )
    monkeypatch.setattr(
        "apps.core.views.stripe.Customer.create",
        lambda **_kwargs: SimpleNamespace(id="cus_checkout"),
    )

    def fake_session_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id="cs_checkout", url="https://example.com/checkout")

    def fake_async_task(*args, **kwargs):
        async_calls.append((args, kwargs))
        return "task-id"

    monkeypatch.setattr("apps.core.views.stripe.checkout.Session.create", fake_session_create)
    monkeypatch.setattr("apps.core.views.async_task", fake_async_task)

    response = auth_client.post(reverse("user_upgrade_checkout_session", args=[1, "one-time"]))

    assert response.status_code == 302
    assert response.url == "https://example.com/checkout"
    assert captured["mode"] == "payment"
    assert captured["line_items"][0]["price"] == "price_launch_10"
    assert captured["metadata"]["plan"] == "one-time"
    assert captured["metadata"]["price_tier"] == "launch_10"
    assert captured["metadata"]["price_amount"] == 10
    assert captured["success_url"].endswith(f"{reverse('project_new')}?checkout=success")
    assert captured["cancel_url"].endswith(f"{reverse('free_access')}?checkout=canceled")
    tracking_call = next(
        call for call in async_calls if call[0][0] == "apps.core.tasks.track_event"
    )
    assert tracking_call[1]["event_name"] == "checkout_started"
    assert tracking_call[1]["properties"]["checkout_id"] == "cs_checkout"
    assert tracking_call[1]["properties"]["price_tier"] == "launch_10"
    reservation = LaunchPriceReservation.objects.get(user=user)
    assert reservation.status == LaunchPriceReservation.Status.PENDING
    assert reservation.tier_key == "launch_10"
    assert reservation.amount_cents == 1000
    assert reservation.stripe_checkout_session_id == "cs_checkout"


@override_settings(
    PAYMENTS_ENABLED=True,
    STRIPE_PRICE_IDS=LAUNCH_PRICE_IDS,
)
@pytest.mark.django_db
def test_enabled_checkout_route_moves_to_next_launch_tier(
    auth_client, user, django_user_model, monkeypatch
):
    captured = {}
    user.profile.state = ProfileStates.STRANGER
    user.profile.save(update_fields=["state"])
    for index in range(10):
        paid_user = django_user_model.objects.create_user(
            username=f"paid-{index}",
            email=f"paid-{index}@example.com",
            password="password123",
        )
        paid_user.profile.state = ProfileStates.SUBSCRIBED
        paid_user.profile.save(update_fields=["state"])

    monkeypatch.setattr(
        "apps.core.views.stripe.Price.retrieve",
        lambda *_args, **_kwargs: SimpleNamespace(unit_amount=10000),
    )
    monkeypatch.setattr(
        "apps.core.views.stripe.Customer.create",
        lambda **_kwargs: SimpleNamespace(id="cus_checkout"),
    )
    monkeypatch.setattr("apps.core.views.async_task", lambda *args, **kwargs: "task-id")

    def fake_session_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id="cs_checkout", url="https://example.com/checkout")

    monkeypatch.setattr("apps.core.views.stripe.checkout.Session.create", fake_session_create)

    response = auth_client.post(reverse("user_upgrade_checkout_session", args=[1, "one-time"]))

    assert response.status_code == 302
    assert captured["line_items"][0]["price"] == "price_launch_100"
    assert captured["metadata"]["price_tier"] == "launch_100"
    assert captured["metadata"]["price_amount"] == 100


def test_get_launch_price_tier_boundaries():
    assert get_launch_price_tier(0).key == "launch_10"
    assert get_launch_price_tier(9).key == "launch_10"
    assert get_launch_price_tier(10).key == "launch_100"
    assert get_launch_price_tier(19).key == "launch_100"
    assert get_launch_price_tier(20).key == "launch_200"
    assert get_launch_price_tier(29).key == "launch_200"
    assert get_launch_price_tier(30).key == "launch_999"


@override_settings(
    PAYMENTS_ENABLED=True,
    STRIPE_PRICE_IDS=LAUNCH_PRICE_IDS,
)
@pytest.mark.django_db
def test_enabled_checkout_handles_missing_session_url(auth_client, user, monkeypatch):
    async_calls = []
    user.profile.state = ProfileStates.STRANGER
    user.profile.save(update_fields=["state"])

    monkeypatch.setattr(
        "apps.core.views.stripe.Price.retrieve",
        lambda *_args, **_kwargs: SimpleNamespace(unit_amount=1000),
    )
    monkeypatch.setattr(
        "apps.core.views.stripe.Customer.create",
        lambda **_kwargs: SimpleNamespace(id="cus_checkout"),
    )
    monkeypatch.setattr(
        "apps.core.views.stripe.checkout.Session.create",
        lambda **_kwargs: SimpleNamespace(id="cs_missing_url"),
    )
    monkeypatch.setattr(
        "apps.core.views.async_task",
        lambda *args, **kwargs: async_calls.append((args, kwargs)) or "task-id",
    )

    response = auth_client.post(reverse("user_upgrade_checkout_session", args=[1, "one-time"]))

    assert response.status_code == 302
    assert response.url == reverse("free_access")
    tracking_call = next(
        call for call in async_calls if call[0][0] == "apps.core.tasks.track_event"
    )
    assert tracking_call[1]["event_name"] == "checkout_failed"
    assert tracking_call[1]["properties"]["reason"] == "session_url_missing"
    assert tracking_call[1]["properties"]["checkout_id"] == "cs_missing_url"
    reservation = LaunchPriceReservation.objects.get(user=user)
    assert reservation.status == LaunchPriceReservation.Status.CANCELED
    assert reservation.canceled_reason == "session_url_missing"


@override_settings(
    PAYMENTS_ENABLED=True,
    STRIPE_PRICE_IDS=LAUNCH_PRICE_IDS,
)
@pytest.mark.django_db
def test_enabled_checkout_counts_pending_launch_reservations(
    auth_client, user, django_user_model, monkeypatch
):
    captured = {}
    user.profile.state = ProfileStates.STRANGER
    user.profile.save(update_fields=["state"])
    for index in range(9):
        paid_user = django_user_model.objects.create_user(
            username=f"paid-reserved-{index}",
            email=f"paid-reserved-{index}@example.com",
            password="password123",
        )
        paid_user.profile.state = ProfileStates.SUBSCRIBED
        paid_user.profile.save(update_fields=["state"])
    pending_user = django_user_model.objects.create_user(
        username="pending-reservation",
        email="pending-reservation@example.com",
        password="password123",
    )
    LaunchPriceReservation.objects.create(
        user=pending_user,
        tier_key="launch_10",
        amount_cents=1000,
        status=LaunchPriceReservation.Status.PENDING,
    )

    monkeypatch.setattr(
        "apps.core.views.stripe.Price.retrieve",
        lambda *_args, **_kwargs: SimpleNamespace(unit_amount=10000),
    )
    monkeypatch.setattr(
        "apps.core.views.stripe.Customer.create",
        lambda **_kwargs: SimpleNamespace(id="cus_checkout"),
    )
    monkeypatch.setattr("apps.core.views.async_task", lambda *args, **kwargs: "task-id")

    def fake_session_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id="cs_checkout_reserved", url="https://example.com/checkout")

    monkeypatch.setattr("apps.core.views.stripe.checkout.Session.create", fake_session_create)

    response = auth_client.post(reverse("user_upgrade_checkout_session", args=[1, "one-time"]))

    assert response.status_code == 302
    assert captured["line_items"][0]["price"] == "price_launch_100"
    assert captured["metadata"]["price_tier"] == "launch_100"


@override_settings(
    PAYMENTS_ENABLED=True,
    STRIPE_PRICE_IDS=LAUNCH_PRICE_IDS,
)
@pytest.mark.django_db
def test_enabled_checkout_skips_external_session_for_active_pro_user(
    auth_client, user, monkeypatch
):
    user.profile.state = ProfileStates.SUBSCRIBED
    user.profile.save(update_fields=["state"])

    monkeypatch.setattr(
        "apps.core.views.stripe.checkout.Session.create",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("Checkout should not be started for an active pro user")
        ),
    )

    response = auth_client.post(reverse("user_upgrade_checkout_session", args=[1, "one-time"]))

    assert response.status_code == 302
    assert response.url == reverse("project_new")


@override_settings(PAYMENTS_ENABLED=False)
@pytest.mark.django_db
def test_disabled_payments_customer_portal_route_redirects_to_settings(
    auth_client, monkeypatch
):
    monkeypatch.setattr(
        "apps.core.views.stripe.billing_portal.Session.create",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("Portal should not be opened while account access is free")
        ),
    )

    response = auth_client.get(reverse("create_customer_portal_session"))

    assert response.status_code == 302
    assert response.url == reverse("settings")


@override_settings(PAYMENTS_ENABLED=True)
@pytest.mark.django_db
def test_enabled_customer_portal_route_creates_stripe_session(auth_client, user, monkeypatch):
    user.profile.stripe_customer_id = "cus_portal"
    user.profile.save(update_fields=["stripe_customer_id"])

    monkeypatch.setattr(
        "apps.core.views.stripe.billing_portal.Session.create",
        lambda **kwargs: SimpleNamespace(url="https://example.com/portal", **kwargs),
    )

    response = auth_client.get(reverse("create_customer_portal_session"))

    assert response.status_code == 302
    assert response.url == "https://example.com/portal"


@override_settings(PAYMENTS_ENABLED=True)
@pytest.mark.django_db
def test_enabled_customer_portal_handles_missing_session_url(auth_client, user, monkeypatch):
    user.profile.stripe_customer_id = "cus_portal"
    user.profile.save(update_fields=["stripe_customer_id"])

    monkeypatch.setattr(
        "apps.core.views.stripe.billing_portal.Session.create",
        lambda **_kwargs: SimpleNamespace(id="bps_missing_url"),
    )

    response = auth_client.get(reverse("create_customer_portal_session"))

    assert response.status_code == 302
    assert response.url == reverse("settings")
