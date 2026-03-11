from types import SimpleNamespace

from django.core.management import call_command
from django.test import override_settings


class FakeListObject:
    def __init__(self, items):
        self._items = items

    def auto_paging_iter(self):
        return iter(self._items)


class FakeStripeObject(dict):
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc


@override_settings(STRIPE_SECRET_KEY="sk_test_123")
def test_setup_stripe_lifetime_price_creates_product_and_price(monkeypatch, capsys):
    calls = {}

    def fake_product_list(**_kwargs):
        return FakeListObject([])

    def fake_product_create(**kwargs):
        calls["product_create"] = kwargs
        return SimpleNamespace(id="prod_djass", name=kwargs["name"])

    def fake_price_list(**_kwargs):
        return FakeListObject([])

    def fake_price_create(**kwargs):
        calls["price_create"] = kwargs
        return SimpleNamespace(id="price_djass_1200")

    monkeypatch.setattr(
        "apps.core.management.commands.setup_stripe_lifetime_price.stripe.Product.list",
        fake_product_list,
    )
    monkeypatch.setattr(
        "apps.core.management.commands.setup_stripe_lifetime_price.stripe.Product.create",
        fake_product_create,
    )
    monkeypatch.setattr(
        "apps.core.management.commands.setup_stripe_lifetime_price.stripe.Price.list",
        fake_price_list,
    )
    monkeypatch.setattr(
        "apps.core.management.commands.setup_stripe_lifetime_price.stripe.Price.create",
        fake_price_create,
    )

    call_command("setup_stripe_lifetime_price")

    output = capsys.readouterr().out
    assert "STRIPE_PRICE_ID_ONE_TIME=price_djass_1200" in output
    assert calls["product_create"]["metadata"]["slug"] == "djass-lifetime"
    assert calls["price_create"]["unit_amount"] == 120000
    assert calls["price_create"]["currency"] == "usd"


@override_settings(STRIPE_SECRET_KEY="sk_test_123")
def test_setup_stripe_lifetime_price_reuses_existing_product_and_price(monkeypatch, capsys):
    product = FakeStripeObject(
        {
            "id": "prod_existing",
            "name": "Djass Lifetime Access",
            "metadata": {"slug": "djass-lifetime"},
        }
    )
    price = FakeStripeObject(
        {
            "id": "price_existing",
            "type": "one_time",
            "unit_amount": 120000,
            "currency": "usd",
            "lookup_key": "djass-premium-usd-1200",
            "metadata": {"slug": "djass-lifetime"},
        }
    )

    def fake_product_list(**_kwargs):
        return FakeListObject([product])

    def fake_price_list(**_kwargs):
        return FakeListObject([price])

    monkeypatch.setattr(
        "apps.core.management.commands.setup_stripe_lifetime_price.stripe.Product.list",
        fake_product_list,
    )
    monkeypatch.setattr(
        "apps.core.management.commands.setup_stripe_lifetime_price.stripe.Price.list",
        fake_price_list,
    )
    monkeypatch.setattr(
        "apps.core.management.commands.setup_stripe_lifetime_price.stripe.Product.create",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("Product should not be created")),
    )
    monkeypatch.setattr(
        "apps.core.management.commands.setup_stripe_lifetime_price.stripe.Price.create",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("Price should not be created")),
    )

    call_command("setup_stripe_lifetime_price")

    output = capsys.readouterr().out
    assert "STRIPE_PRICE_ID_ONE_TIME=price_existing" in output
