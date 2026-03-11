import os

import stripe
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create (or fetch) the Djass one-time Stripe product + $1,200 premium price"

    def add_arguments(self, parser):
        parser.add_argument(
            "--amount",
            type=int,
            default=120000,
            help="Price amount in minor units (cents). Default: 120000 ($1,200)",
        )
        parser.add_argument(
            "--currency",
            default="usd",
            help="Three-letter ISO currency code. Default: usd",
        )
        parser.add_argument(
            "--product-name",
            default="Djass Lifetime Access",
            help="Stripe product name",
        )
        parser.add_argument(
            "--product-slug",
            default="djass-lifetime",
            help="Slug stored in Stripe metadata for idempotency",
        )
        parser.add_argument(
            "--lookup-key",
            default="djass-premium-usd-1200",
            help="Price lookup key to keep idempotent references",
        )
        parser.add_argument(
            "--stripe-context",
            default="",
            help="Optional Stripe-Context account id (required for Organization API keys)",
        )

    def handle(self, *args, **options):
        stripe_key = settings.STRIPE_SECRET_KEY or os.environ.get("STRIPE_API_KEY", "")
        if not stripe_key:
            raise CommandError("Stripe key is missing. Set STRIPE_SECRET_KEY (or STRIPE_API_KEY).")

        stripe.api_key = stripe_key

        request_options = {}
        stripe_context = (options.get("stripe_context") or "").strip()
        if stripe_context:
            request_options["stripe_context"] = stripe_context

        amount = options["amount"]
        currency = options["currency"].lower().strip()
        product_name = options["product_name"].strip()
        product_slug = options["product_slug"].strip()
        lookup_key = options["lookup_key"].strip()

        product = self._get_or_create_product(
            product_name=product_name,
            product_slug=product_slug,
            request_options=request_options,
        )
        price = self._get_or_create_price(
            product_id=product.id,
            amount=amount,
            currency=currency,
            lookup_key=lookup_key,
            product_slug=product_slug,
            request_options=request_options,
        )

        self.stdout.write(self.style.SUCCESS("Djass lifetime Stripe setup complete."))
        self.stdout.write(f"Product: {product.id} ({product.name})")
        self.stdout.write(f"Price: {price.id} ({currency} {amount})")
        self.stdout.write(f"STRIPE_PRICE_ID_ONE_TIME={price.id}")

    def _get_or_create_product(self, product_name, product_slug, request_options):
        products = stripe.Product.list(active=True, limit=100, **request_options)
        for product in products.auto_paging_iter():
            metadata = product.get("metadata", {}) or {}
            if metadata.get("slug") == product_slug:
                return product
            if product.get("name") == product_name:
                return product

        return stripe.Product.create(
            name=product_name,
            description=(
                "Djass lifetime one-time payment for unlimited project generations "
                "and forever updates."
            ),
            metadata={
                "slug": product_slug,
                "plan": "one-time",
                "app": "djass",
            },
            **request_options,
        )

    def _get_or_create_price(
        self,
        product_id,
        amount,
        currency,
        lookup_key,
        product_slug,
        request_options,
    ):
        prices = stripe.Price.list(product=product_id, active=True, limit=100, **request_options)
        for price in prices.auto_paging_iter():
            metadata = price.get("metadata", {}) or {}
            if (
                price.get("type") == "one_time"
                and price.get("unit_amount") == amount
                and price.get("currency") == currency
                and (metadata.get("slug") == product_slug or price.get("lookup_key") == lookup_key)
            ):
                return price

        return stripe.Price.create(
            product=product_id,
            unit_amount=amount,
            currency=currency,
            lookup_key=lookup_key,
            nickname="Djass Lifetime Access",
            metadata={
                "slug": product_slug,
                "plan": "one-time",
                "app": "djass",
            },
            **request_options,
        )
