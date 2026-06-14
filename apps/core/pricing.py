from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.choices import ProfileStates
from apps.core.models import LaunchPriceLedger, LaunchPriceReservation, Profile


@dataclass(frozen=True)
class LaunchPriceTier:
    key: str
    amount: int
    first_paid_member: int
    last_paid_member: int | None = None

    @property
    def amount_cents(self):
        return self.amount * 100

    @property
    def display_amount(self):
        return f"${self.amount:,}"

    @property
    def seats(self):
        if self.last_paid_member is None:
            return f"{self.first_paid_member}+"
        return f"{self.first_paid_member}-{self.last_paid_member}"

    @property
    def spot_count(self):
        if self.last_paid_member is None:
            return None
        return self.last_paid_member - self.first_paid_member + 1

    @property
    def availability_label(self):
        if self.spot_count is None:
            return f"Spot {self.first_paid_member}+"
        if self.first_paid_member == 1:
            return f"First {self.spot_count} spots"
        return f"Next {self.spot_count} spots"


LAUNCH_PRICE_TIERS = (
    LaunchPriceTier(key="launch_10", amount=10, first_paid_member=1, last_paid_member=10),
    LaunchPriceTier(key="launch_100", amount=100, first_paid_member=11, last_paid_member=20),
    LaunchPriceTier(key="launch_200", amount=200, first_paid_member=21, last_paid_member=30),
    LaunchPriceTier(key="launch_999", amount=999, first_paid_member=31),
)

PAID_PROFILE_STATES = (
    ProfileStates.SUBSCRIBED,
    ProfileStates.CANCELLED,
)
ACTIVE_RESERVATION_WINDOW = timedelta(hours=24)
LAUNCH_PRICE_LEDGER_KEY = "launch_ladder"


def get_paid_member_count():
    return Profile.objects.filter(state__in=PAID_PROFILE_STATES).count()


def get_pending_launch_reservation_count():
    active_since = timezone.now() - ACTIVE_RESERVATION_WINDOW
    return LaunchPriceReservation.objects.filter(
        status=LaunchPriceReservation.Status.PENDING,
        created_at__gte=active_since,
    ).count()


def get_claimed_launch_price_spot_count():
    return get_paid_member_count() + get_pending_launch_reservation_count()


def get_launch_price_tier(paid_member_count=None):
    paid_member_count = (
        get_claimed_launch_price_spot_count() if paid_member_count is None else paid_member_count
    )
    next_paid_member = paid_member_count + 1

    for tier in LAUNCH_PRICE_TIERS:
        if tier.last_paid_member is None or next_paid_member <= tier.last_paid_member:
            return tier

    return LAUNCH_PRICE_TIERS[-1]


def get_launch_price_spots_left(paid_member_count=None):
    paid_member_count = (
        get_claimed_launch_price_spot_count() if paid_member_count is None else paid_member_count
    )
    current_tier = get_launch_price_tier(paid_member_count)
    if current_tier.last_paid_member is None:
        return None
    return max(current_tier.last_paid_member - paid_member_count, 0)


def get_price_id_for_tier(tier):
    return settings.STRIPE_PRICE_IDS.get(tier.key) or None


def reserve_launch_price_tier(user):
    with transaction.atomic():
        LaunchPriceLedger.objects.select_for_update().get_or_create(key=LAUNCH_PRICE_LEDGER_KEY)
        LaunchPriceReservation.objects.filter(
            user=user,
            status=LaunchPriceReservation.Status.PENDING,
        ).update(
            status=LaunchPriceReservation.Status.CANCELED,
            canceled_reason="replaced_by_new_checkout",
            updated_at=timezone.now(),
        )
        current_tier = get_launch_price_tier()
        reservation = LaunchPriceReservation.objects.create(
            user=user,
            tier_key=current_tier.key,
            amount_cents=current_tier.amount_cents,
        )
    return current_tier, reservation


def cancel_launch_price_reservation(reservation, reason):
    if reservation is None or reservation.status != LaunchPriceReservation.Status.PENDING:
        return
    reservation.status = LaunchPriceReservation.Status.CANCELED
    reservation.canceled_reason = reason[:255]
    reservation.save(update_fields=["status", "canceled_reason", "updated_at"])


def attach_checkout_session_to_reservation(reservation, checkout_id):
    if reservation is None or not checkout_id:
        return
    reservation.stripe_checkout_session_id = checkout_id
    reservation.save(update_fields=["stripe_checkout_session_id", "updated_at"])


def mark_launch_price_reservation_paid(checkout_id, payment_intent=""):
    if not checkout_id:
        return
    LaunchPriceReservation.objects.filter(
        stripe_checkout_session_id=checkout_id,
        status=LaunchPriceReservation.Status.PENDING,
    ).update(
        status=LaunchPriceReservation.Status.PAID,
        stripe_payment_intent=payment_intent or "",
        updated_at=timezone.now(),
    )


def cancel_launch_price_reservation_for_checkout(checkout_id, reason):
    if not checkout_id:
        return
    LaunchPriceReservation.objects.filter(
        stripe_checkout_session_id=checkout_id,
        status=LaunchPriceReservation.Status.PENDING,
    ).update(
        status=LaunchPriceReservation.Status.CANCELED,
        canceled_reason=reason[:255],
        updated_at=timezone.now(),
    )
