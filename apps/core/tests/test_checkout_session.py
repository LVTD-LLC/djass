from types import SimpleNamespace

import pytest
from django.test import override_settings
from django.urls import reverse

from apps.core.choices import ProfileStates


@pytest.mark.django_db
def test_legacy_checkout_route_redirects_to_project_creation(auth_client, monkeypatch):
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
    STRIPE_PRICE_IDS={"one-time": "price_one_time"},
    STRIPE_ONE_TIME_AMOUNT_CENTS=99900,
)
@pytest.mark.django_db
def test_enabled_checkout_route_keeps_one_time_payment_flow(auth_client, user, monkeypatch):
    captured = {}
    async_calls = []
    user.profile.state = ProfileStates.STRANGER
    user.profile.save(update_fields=["state"])

    monkeypatch.setattr(
        "apps.core.views.stripe.Price.retrieve",
        lambda *_args, **_kwargs: SimpleNamespace(unit_amount=99900),
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
    assert captured["line_items"][0]["price"] == "price_one_time"
    assert captured["metadata"]["plan"] == "one-time"
    assert captured["success_url"].endswith(f"{reverse('project_new')}?checkout=success")
    assert captured["cancel_url"].endswith(f"{reverse('free_access')}?checkout=canceled")
    tracking_call = next(
        call for call in async_calls if call[0][0] == "apps.core.tasks.track_event"
    )
    assert tracking_call[1]["event_name"] == "checkout_started"
    assert tracking_call[1]["properties"]["checkout_id"] == "cs_checkout"


@override_settings(
    PAYMENTS_ENABLED=True,
    STRIPE_PRICE_IDS={"one-time": "price_one_time"},
)
@pytest.mark.django_db
def test_enabled_checkout_skips_external_session_for_active_pro_user(auth_client, monkeypatch):
    monkeypatch.setattr(
        "apps.core.views.stripe.checkout.Session.create",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("Checkout should not be started for an active pro user")
        ),
    )

    response = auth_client.post(reverse("user_upgrade_checkout_session", args=[1, "one-time"]))

    assert response.status_code == 302
    assert response.url == reverse("project_new")


@pytest.mark.django_db
def test_legacy_customer_portal_route_redirects_to_settings(auth_client, monkeypatch):
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
