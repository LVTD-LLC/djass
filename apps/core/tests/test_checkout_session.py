from types import SimpleNamespace

import pytest
from django.test import override_settings
from django.urls import reverse

from apps.core.choices import ProfileStates


@override_settings(STRIPE_PRICE_IDS={"one-time": "price_one_time"})
@pytest.mark.django_db
def test_create_checkout_session_one_time_uses_payment_mode(auth_client, monkeypatch):
    captured = {}
    async_calls = []

    def fake_customer_create(**_kwargs):
        return SimpleNamespace(id="cus_one_time")

    def fake_session_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id="cs_test_checkout", url="https://example.com/checkout")

    def fake_async_task(*args, **kwargs):
        async_calls.append((args, kwargs))
        return "task-id"

    monkeypatch.setattr("apps.core.views.stripe.Customer.create", fake_customer_create)
    monkeypatch.setattr("apps.core.views.stripe.checkout.Session.create", fake_session_create)
    monkeypatch.setattr("apps.core.views.async_task", fake_async_task)

    url = reverse("user_upgrade_checkout_session", args=[1, "one-time"])
    response = auth_client.post(url)

    assert response.status_code == 302
    assert captured["mode"] == "payment"
    assert captured["metadata"]["plan"] == "one-time"
    assert captured["success_url"].endswith(f"{reverse('project_new')}?checkout=success")
    assert captured["cancel_url"].endswith(f"{reverse('pricing')}?checkout=canceled")
    assert "subscription_data" not in captured
    tracking_call = next(
        call for call in async_calls if call[0][0] == "apps.core.tasks.track_event"
    )
    assert tracking_call[1]["event_name"] == "checkout_session_created"
    assert tracking_call[1]["properties"]["checkout_id"] == "cs_test_checkout"
    assert tracking_call[1]["properties"]["plan"] == "one-time"


@override_settings(STRIPE_PRICE_IDS={"one-time": "price_one_time"})
@pytest.mark.django_db
def test_create_checkout_session_rejects_non_one_time_plan(auth_client, monkeypatch):
    called = {}

    def fake_customer_create(**_kwargs):
        called["customer"] = True
        return SimpleNamespace(id="cus_monthly")

    def fake_session_create(**kwargs):
        called["session"] = kwargs
        return SimpleNamespace(url="https://example.com/checkout")

    monkeypatch.setattr("apps.core.views.stripe.Customer.create", fake_customer_create)
    monkeypatch.setattr("apps.core.views.stripe.checkout.Session.create", fake_session_create)

    url = reverse("user_upgrade_checkout_session", args=[1, "monthly"])
    response = auth_client.post(url)

    assert response.status_code == 302
    assert response.url == reverse("pricing")
    assert called == {}


@override_settings(STRIPE_PRICE_IDS={"one-time": "price_one_time"})
@pytest.mark.django_db
def test_create_checkout_session_prevents_duplicate_active_subscription(
    auth_client,
    user,
    monkeypatch,
):
    user.profile.state = ProfileStates.SUBSCRIBED
    user.profile.save(update_fields=["state"])

    monkeypatch.setattr(
        "apps.core.views.stripe.checkout.Session.create",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("Checkout session should not be created")
        ),
    )

    url = reverse("user_upgrade_checkout_session", args=[1, "one-time"])
    response = auth_client.post(url)

    assert response.status_code == 302
    assert response.url == reverse("project_new")
