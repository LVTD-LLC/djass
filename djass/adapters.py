import re
import uuid

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib import messages
from django.contrib.auth import get_user_model

from apps.core.choices import EmailType
from apps.core.utils import track_email_sent
from djass.utils import get_djass_logger

logger = get_djass_logger(__name__)

User = get_user_model()


class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Custom adapter to track email confirmations and welcome emails.
    """

    def send_confirmation_mail(self, request, emailconfirmation, signup):
        """
        Override to track email confirmation sends.

        Args:
            request: The HTTP request
            emailconfirmation: The email confirmation object
            signup: Boolean indicating if this is during signup (True) or resend (False)
        """
        profile = (
            emailconfirmation.email_address.user.profile
            if hasattr(emailconfirmation.email_address.user, "profile")
            else None
        )

        # Track as welcome email during signup, confirmation email on resend
        email_type = EmailType.WELCOME if signup else EmailType.EMAIL_CONFIRMATION

        logger.info(
            "[Send Confirmation Mail] Sending email",
            signup=signup,
            email_type=email_type,
            user_id=emailconfirmation.email_address.user.id,
            email=emailconfirmation.email_address.email,
        )

        try:
            result = super().send_confirmation_mail(request, emailconfirmation, signup)
            track_email_sent(
                email_address=emailconfirmation.email_address.email,
                email_type=email_type,
                profile=profile,
            )
            return result
        except Exception as error:
            response = getattr(error, "response", None)
            response_text = None
            if response is not None:
                response_text = getattr(response, "text", None)

            logger.error(
                "[Send Confirmation Mail] Failed to send email",
                error=str(error),
                error_type=type(error).__name__,
                status_code=getattr(error, "status_code", None),
                response_text=response_text,
                exc_info=True,
                user_id=emailconfirmation.email_address.user.id,
                email=emailconfirmation.email_address.email,
                signup=signup,
            )

            if signup:
                if request is not None and hasattr(request, "_messages"):
                    messages.warning(
                        request,
                        "Your account was created, but we could not send the confirmation email right now. "
                        "Please retry from your account page in a few minutes.",
                    )
                return None

            raise

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom adapter to automatically generate usernames from email addresses
    during social authentication signup, bypassing the username selection page.
    """

    def populate_user(self, request, sociallogin, data):
        """
        Automatically set username from email address before user creation.
        Uses the part before @ symbol as username, ensuring uniqueness.
        """
        user = super().populate_user(request, sociallogin, data)

        if not user.username and user.email:
            base_username = re.sub(r"[^\w]", "", user.email.split("@")[0])
            if not base_username:
                base_username = f"user{uuid.uuid4().hex[:8]}"
            username = base_username

            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1

            user.username = username

        return user
