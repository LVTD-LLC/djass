from allauth.account.views import SignupByPasskeyView, SignupView
from django.conf import settings
from django.contrib import messages
from django.views.generic import TemplateView
from django_q.tasks import async_task

from apps.core.models import Profile
from djass.utils import get_djass_logger

logger = get_djass_logger(__name__)


class LandingPageView(TemplateView):
    template_name = "pages/landing-page.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.user.is_authenticated and settings.POSTHOG_API_KEY:
            user = self.request.user
            profile = user.profile

            async_task(
                "apps.core.tasks.try_create_posthog_alias",
                profile_id=profile.id,
                cookies=self.request.COOKIES,
                source_function="LandingPageView - get_context_data",
                group="Create Posthog Alias",
            )
        

        if self.request.user.is_authenticated:
            try:
                profile = self.request.user.profile
                context["has_pro_subscription"] = profile.has_active_subscription
            except Profile.DoesNotExist:
                context["has_pro_subscription"] = False
        else:
            context["has_pro_subscription"] = False

        return context


class SignupTrackingMixin:
    tracking_source_name = "signup"

    def _track_signup(self):
        user = self.user
        profile = user.profile

        async_task(
            "apps.core.tasks.try_create_posthog_alias",
            profile_id=profile.id,
            cookies=self.request.COOKIES,
            source_function=f"{self.tracking_source_name} - form_valid",
            group="Create Posthog Alias",
        )

        async_task(
            "apps.core.tasks.track_event",
            profile_id=profile.id,
            event_name="user_signed_up",
            properties={
                "signup_method": (
                    "passkey" if "passkey" in self.request.path else "password"
                ),
                "funnel_step": "signup_completed",
                "$set": {
                    "email": profile.user.email,
                    "username": profile.user.username,
                },
            },
            source_function=f"{self.tracking_source_name} - form_valid",
            group="Track Event",
        )

    def form_valid(self, form):
        response = super().form_valid(form)
        self._track_signup()
        return response


class AccountSignupView(SignupTrackingMixin, SignupView):
    template_name = "account/signup.html"
    tracking_source_name = "AccountSignupView"


class AccountSignupByPasskeyView(SignupTrackingMixin, SignupByPasskeyView):
    template_name = "account/signup_by_passkey.html"
    tracking_source_name = "AccountSignupByPasskeyView"


class PricingView(TemplateView):
    template_name = "pages/pricing.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        checkout_status = self.request.GET.get("checkout")
        if checkout_status == "canceled":
            messages.info(
                self.request,
                "Checkout was canceled. You can resume whenever you're ready.",
            )
        elif checkout_status == "failed":
            messages.error(self.request, "Payment did not complete. Please try checkout again.")

        if checkout_status in {"canceled", "failed"} and self.request.user.is_authenticated:
            profile = self.request.user.profile
            async_task(
                "apps.core.tasks.track_event",
                profile_id=profile.id,
                event_name="checkout_failed",
                properties={
                    "reason": checkout_status,
                    "funnel_step": "checkout_failed",
                },
                source_function="PricingView - get_context_data",
                group="Track Event",
            )

        if self.request.user.is_authenticated:
            try:
                profile = self.request.user.profile
                context["has_pro_subscription"] = profile.has_active_subscription
            except Profile.DoesNotExist:
                context["has_pro_subscription"] = False
        else:
            context["has_pro_subscription"] = False

        return context



class PrivacyPolicyView(TemplateView):
    template_name = "pages/privacy-policy.html"


class TermsOfServiceView(TemplateView):
    template_name = "pages/terms-of-service.html"
