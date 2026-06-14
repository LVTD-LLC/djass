from allauth.account.views import SignupByPasskeyView, SignupView
from django.conf import settings
from django.views.generic import TemplateView
from django_q.tasks import async_task

from apps.core.agent_prompts import DJASS_OPENAPI_DOCS_URL
from apps.core.pricing import LAUNCH_PRICE_TIERS, get_launch_price_tier
from djass.utils import get_djass_logger

logger = get_djass_logger(__name__)


class LandingPageView(TemplateView):
    template_name = "pages/landing-page.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["djass_openapi_docs_url"] = DJASS_OPENAPI_DOCS_URL
        context["current_price_tier"] = get_launch_price_tier()

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
                "signup_method": ("passkey" if "passkey" in self.request.path else "password"),
                "funnel_step": "signup_completed",
                "entrypoint": "ui",
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
    # signup.html uses allauth's injected entrance context for passkey signup
    # keys such as PASSKEY_SIGNUP_ENABLED and signup_by_passkey_url.
    template_name = "account/signup.html"
    tracking_source_name = "AccountSignupView"


class AccountSignupByPasskeyView(SignupTrackingMixin, SignupByPasskeyView):
    template_name = "account/signup_by_passkey.html"
    tracking_source_name = "AccountSignupByPasskeyView"


class PricingView(TemplateView):
    template_name = "pages/pricing.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["launch_price_tiers"] = LAUNCH_PRICE_TIERS
        context["current_price_tier"] = get_launch_price_tier()
        if self.request.user.is_authenticated and hasattr(self.request.user, "profile"):
            context["has_pro_subscription"] = self.request.user.profile.has_active_subscription
        else:
            context["has_pro_subscription"] = False
        return context


class PrivacyPolicyView(TemplateView):
    template_name = "pages/privacy-policy.html"


class TermsOfServiceView(TemplateView):
    template_name = "pages/terms-of-service.html"
