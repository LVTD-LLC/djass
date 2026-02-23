from types import SimpleNamespace

import pytest
from django.test import override_settings
from django.urls import reverse


@override_settings(STRIPE_PRICE_IDS={"one-time": "price_one_time", "monthly": "price_monthly"})
@pytest.mark.django_db
def test_create_checkout_session_one_time_uses_payment_mode(auth_client, monkeypatch):
    captured = {}

    def fake_customer_create(**_kwargs):
        return SimpleNamespace(id="cus_one_time")

    def fake_session_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(url="https://example.com/checkout")

    monkeypatch.setattr("apps.core.views.stripe.Customer.create", fake_customer_create)
    monkeypatch.setattr("apps.core.views.stripe.checkout.Session.create", fake_session_create)

    url = reverse("user_upgrade_checkout_session", args=[1, "one-time"])
    response = auth_client.post(url)

    assert response.status_code == 303
    assert captured["mode"] == "payment"
    assert "subscription_data" not in captured


@override_settings(STRIPE_PRICE_IDS={"one-time": "price_one_time", "monthly": "price_monthly"})
@pytest.mark.django_db
def test_create_checkout_session_monthly_uses_subscription_mode(auth_client, monkeypatch):
    captured = {}

    def fake_customer_create(**_kwargs):
        return SimpleNamespace(id="cus_monthly")

    def fake_session_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(url="https://example.com/checkout")

    monkeypatch.setattr("apps.core.views.stripe.Customer.create", fake_customer_create)
    monkeypatch.setattr("apps.core.views.stripe.checkout.Session.create", fake_session_create)

    url = reverse("user_upgrade_checkout_session", args=[1, "monthly"])
    response = auth_client.post(url)

    assert response.status_code == 303
    assert captured["mode"] == "subscription"
    assert captured["subscription_data"]["metadata"]["plan"] == "monthly"


@override_settings(
    STRIPE_PRICE_IDS={
        "one-time": "price_one_time",
        "monthly": "price_monthly",
        "yearly": "price_yearly",
    }
)
@pytest.mark.django_db
def test_create_checkout_session_yearly_uses_subscription_mode(auth_client, monkeypatch):
    captured = {}

    def fake_customer_create(**_kwargs):
        return SimpleNamespace(id="cus_yearly")

    def fake_session_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(url="https://example.com/checkout")

    monkeypatch.setattr("apps.core.views.stripe.Customer.create", fake_customer_create)
    monkeypatch.setattr("apps.core.views.stripe.checkout.Session.create", fake_session_create)

    url = reverse("user_upgrade_checkout_session", args=[1, "yearly"])
    response = auth_client.post(url)

    assert response.status_code == 303
    assert captured["mode"] == "subscription"
    assert captured["subscription_data"]["metadata"]["plan"] == "yearly"
