import os

import stripe
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.core.pricing import LAUNCH_PRICE_TIERS


class Command(BaseCommand):
    help = "Create (or fetch) the Djass one-time Stripe product + launch ladder prices"

    def add_arguments(self, parser):
        parser.add_argument(
            "--currency",
            default="usd",
            help="Three-letter ISO currency code. Default: usd",
        )
        parser.add_argument(
            "--product-name",
            default="Djass",
            help="Stripe product name",
        )
        parser.add_argument(
            "--product-slug",
            default="djass",
            help="Slug stored in Stripe metadata for idempotency",
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

        currency = options["currency"].lower().strip()
        product_name = options["product_name"].strip()
        product_slug = options["product_slug"].strip()

        product = self._get_or_create_product(
            product_name=product_name,
            product_slug=product_slug,
            request_options=request_options,
        )
        prices = [
            self._get_or_create_price(
                product_id=product.id,
                tier=tier,
                currency=currency,
                product_slug=product_slug,
                request_options=request_options,
            )
            for tier in LAUNCH_PRICE_TIERS
        ]

        self.stdout.write(self.style.SUCCESS("Djass launch ladder Stripe setup complete."))
        self.stdout.write(f"Product: {product.id} ({product.name})")
        for tier, price in zip(LAUNCH_PRICE_TIERS, prices, strict=True):
            env_name = f"STRIPE_PRICE_ID_{tier.key.upper()}"
            self.stdout.write(f"{tier.display_amount}: {price.id}")
            self.stdout.write(f"{env_name}={price.id}")

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
                "Djass one-time lifetime access for unlimited project generations "
                "with launch ladder pricing."
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
        tier,
        currency,
        product_slug,
        request_options,
    ):
        amount = tier.amount_cents
        lookup_key = f"djass-{tier.key}-{currency}"
        prices = stripe.Price.list(product=product_id, active=True, limit=100, **request_options)
        for price in prices.auto_paging_iter():
            metadata = price.get("metadata", {}) or {}
            if (
                price.get("type") == "one_time"
                and price.get("unit_amount") == amount
                and price.get("currency") == currency
                and (metadata.get("tier") == tier.key or price.get("lookup_key") == lookup_key)
            ):
                return price

        return stripe.Price.create(
            product=product_id,
            unit_amount=amount,
            currency=currency,
            lookup_key=lookup_key,
            nickname=f"Djass Lifetime Access {tier.display_amount}",
            metadata={
                "slug": product_slug,
                "plan": "one-time",
                "app": "djass",
                "tier": tier.key,
            },
            **request_options,
        )
