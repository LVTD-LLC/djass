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
def test_setup_stripe_lifetime_price_creates_product_and_launch_prices(monkeypatch, capsys):
    calls = {"prices": []}

    def fake_product_list(**_kwargs):
        return FakeListObject([])

    def fake_product_create(**kwargs):
        calls["product_create"] = kwargs
        return SimpleNamespace(id="prod_djass", name=kwargs["name"])

    def fake_price_list(**_kwargs):
        return FakeListObject([])

    def fake_price_create(**kwargs):
        calls["prices"].append(kwargs)
        return SimpleNamespace(id=f"price_{kwargs['metadata']['tier']}")

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
    assert "STRIPE_PRICE_ID_LAUNCH_10=price_launch_10" in output
    assert "STRIPE_PRICE_ID_LAUNCH_100=price_launch_100" in output
    assert "STRIPE_PRICE_ID_LAUNCH_200=price_launch_200" in output
    assert "STRIPE_PRICE_ID_LAUNCH_999=price_launch_999" in output
    assert calls["product_create"]["metadata"]["slug"] == "djass"
    assert [price["unit_amount"] for price in calls["prices"]] == [1000, 10000, 20000, 99900]
    assert {price["currency"] for price in calls["prices"]} == {"usd"}


@override_settings(STRIPE_SECRET_KEY="sk_test_123")
def test_setup_stripe_lifetime_price_reuses_existing_product_and_price(monkeypatch, capsys):
    product = FakeStripeObject(
        {
            "id": "prod_existing",
            "name": "Djass",
            "metadata": {"slug": "djass"},
        }
    )
    prices = [
        FakeStripeObject(
            {
                "id": f"price_existing_{amount}",
                "type": "one_time",
                "unit_amount": amount,
                "currency": "usd",
                "lookup_key": f"djass-{tier}-usd",
                "metadata": {"slug": "djass", "tier": tier},
            }
        )
        for tier, amount in [
            ("launch_10", 1000),
            ("launch_100", 10000),
            ("launch_200", 20000),
            ("launch_999", 99900),
        ]
    ]

    def fake_product_list(**_kwargs):
        return FakeListObject([product])

    def fake_price_list(**_kwargs):
        return FakeListObject(prices)

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
    assert "STRIPE_PRICE_ID_LAUNCH_10=price_existing_1000" in output
    assert "STRIPE_PRICE_ID_LAUNCH_999=price_existing_99900" in output
