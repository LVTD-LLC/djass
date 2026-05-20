from django.urls import path
from django.views.generic import RedirectView

from apps.pages import views

urlpatterns = [
    path("", views.LandingPageView.as_view(), name="landing"),
    path("privacy-policy", views.PrivacyPolicyView.as_view(), name="privacy_policy"),
    path("terms-of-service", views.TermsOfServiceView.as_view(), name="terms_of_service"),
    path("pricing", views.PricingView.as_view(), name="pricing"),
    path(
        "free-access",
        RedirectView.as_view(pattern_name="pricing", permanent=True),
        name="free_access",
    ),
]
