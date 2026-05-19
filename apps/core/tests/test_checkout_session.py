import pytest
from django.urls import reverse


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
