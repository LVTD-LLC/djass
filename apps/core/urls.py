from django.urls import path
from django.views.generic import RedirectView

from apps.core import views

urlpatterns = [
    # App pages
    path("home", views.HomeView.as_view(), name="home"),
    path("skill.md", views.AgentSkillView.as_view(), name="agent_skill"),
    path("agent-skill", RedirectView.as_view(pattern_name="agent_skill", permanent=True)),
    path("settings", views.UserSettingsView.as_view(), name="settings"),
    path("admin-panel", views.AdminPanelView.as_view(), name="admin_panel"),
    path("projects/new", views.ProjectCreateView.as_view(), name="project_new"),
    path("projects/create", views.create_project, name="project_create"),
    path("projects/<int:project_id>", views.ProjectDetailView.as_view(), name="project_detail"),
    path(
        "projects/<int:project_id>/download",
        views.download_project_artifact,
        name="project_download",
    ),
    path("projects/<int:project_id>/retry", views.retry_project_generation, name="project_retry"),
    # Utils
    path("resend-confirmation/", views.resend_confirmation_email, name="resend_confirmation"),
    path("delete-account/", views.delete_account, name="delete_account"),
    # Stripe webhooks and legacy account access routes
    path("stripe-webhook/", views.stripe_webhook, name="stripe_webhook"),
    path(
        "create-checkout-session/<int:pk>/<str:plan>/",
        views.create_checkout_session,
        name="user_upgrade_checkout_session",
    ),
    path(
        "create-customer-portal/",
        views.create_customer_portal_session,
        name="create_customer_portal_session",
    ),
]
