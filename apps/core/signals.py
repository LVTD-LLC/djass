from allauth.account.signals import email_confirmed, user_signed_up
from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.db.models.signals import post_save
from django.dispatch import receiver
from django_q.tasks import async_task

from apps.core.tasks import add_email_to_buttondown

from apps.core.models import Profile, ProfileStates
from djass.utils import get_djass_logger

logger = get_djass_logger(__name__)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        profile = Profile.objects.create(user=instance)
        profile.track_state_change(
            to_state=ProfileStates.SIGNED_UP,
            source_function="create_user_profile signal",
        )

    if instance.id == 1:
        # Use update() to avoid triggering the signal again
        User.objects.filter(id=1).update(is_staff=True, is_superuser=True)


@receiver(email_confirmed)
def add_email_to_buttondown_on_confirm(sender, **kwargs):
    logger.info(
        "Adding new user to buttondown newsletter, on email confirmation",
        kwargs=kwargs,
        sender=sender,
    )
    async_task(add_email_to_buttondown, kwargs["email_address"], tag="user")


@receiver(user_signed_up)
def email_confirmation_callback(sender, request, user, **kwargs):
    if 'sociallogin' in kwargs:
        logger.info(
            "Adding new user to buttondown newsletter on social signup",
            kwargs=kwargs,
            sender=sender,
        )
        email = kwargs['sociallogin'].user.email
        if email:
            async_task(add_email_to_buttondown, email, tag="user")


@receiver(user_logged_in)
def track_user_login(sender, request, user, **kwargs):
    if not hasattr(user, "profile"):
        return

    profile = user.profile

    async_task(
        "apps.core.tasks.try_create_posthog_alias",
        profile_id=profile.id,
        cookies=request.COOKIES,
        source_function="user_logged_in signal",
        group="Create Posthog Alias",
    )

    async_task(
        "apps.core.tasks.track_event",
        profile_id=profile.id,
        event_name="user_authenticated",
        properties={
            "auth_method": "passkey" if "passkey" in request.path else "password",
            "funnel_step": "auth_completed",
            "entrypoint": "ui",
        },
        source_function="user_logged_in signal",
        group="Track Event",
    )


@receiver(user_login_failed)
def track_user_login_failed(sender, credentials=None, request=None, **kwargs):
    email = (credentials or {}).get("email") or (credentials or {}).get("username")
    if not email:
        return

    profile = Profile.objects.filter(user__email=email).select_related("user").first()
    if not profile:
        return

    auth_method = "password"
    if request and "passkey" in (request.path or ""):
        auth_method = "passkey"

    async_task(
        "apps.core.tasks.track_event",
        profile_id=profile.id,
        event_name="user_auth_failed",
        properties={
            "auth_method": auth_method,
            "reason": "invalid_credentials",
            "funnel_step": "auth_failed",
        },
        source_function="user_login_failed signal",
        group="Track Event",
    )

