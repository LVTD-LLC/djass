from urllib.parse import urlencode

import stripe
from allauth.account.internal.flows.email_verification import (
    send_verification_email_to_address,
)
from allauth.account.models import EmailAddress
from allauth.mfa.models import Authenticator
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.cache import cache
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView, UpdateView
from django_q.tasks import async_task

from apps.core.agent_prompts import (
    DJASS_API_BASE_URL,
    build_djass_agent_prompt,
    build_djass_agent_skill_md,
)
from apps.core.forms import ProfileUpdateForm, ProjectCreateForm
from apps.core.models import Profile, Project, ProjectStatus
from apps.core.project_limits import project_create_quota
from apps.core.stripe_webhooks import EVENT_HANDLERS
from djass.utils import get_djass_logger

stripe.api_key = settings.STRIPE_SECRET_KEY


logger = get_djass_logger(__name__)


def _user_can_create_projects(user):
    if not user.is_authenticated or not hasattr(user, "profile"):
        return False
    if _payments_enabled():
        return user.profile.has_active_subscription
    return True


def _user_project_count(user):
    return Project.objects.filter(user=user).count()


def _project_limit_reached(user):
    return _user_project_count(user) >= project_create_quota()


def _payments_enabled():
    return bool(getattr(settings, "PAYMENTS_ENABLED", False))


def _deny_project_access(request):
    if _payments_enabled() and request.user.is_authenticated and hasattr(request.user, "profile"):
        messages.error(request, "Project generation requires active account access.")
        return redirect("free_access")

    messages.error(
        request,
        (
            "We couldn't find an account profile for your signed-in user. "
            "Please contact support before creating projects."
        ),
    )
    return redirect("home")


def _queue_profile_event(profile, event_name, properties, source_function):
    async_task(
        "apps.core.tasks.track_event",
        profile_id=profile.id,
        event_name=event_name,
        properties=properties,
        source_function=source_function,
        group="Track Event",
    )


class HomeView(LoginRequiredMixin, TemplateView):
    login_url = "account_login"
    template_name = "pages/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        can_create_projects = _user_can_create_projects(self.request.user)
        context["projects"] = Project.objects.filter(user=self.request.user)
        context["project_limit_reached"] = can_create_projects and _project_limit_reached(
            self.request.user
        )
        context["can_generate"] = can_create_projects and not context["project_limit_reached"]
        context["agent_prompt_available"] = False
        if can_create_projects:
            context["projects_api_base_url"] = DJASS_API_BASE_URL
            skill_url = self.request.build_absolute_uri(reverse("agent_skill"))
            context["djass_agent_prompt"] = build_djass_agent_prompt(
                DJASS_API_BASE_URL,
                self.request.user.profile.key,
                skill_url=skill_url,
            )
            context["agent_prompt_available"] = True

        return context


class AgentSkillView(TemplateView):
    # Deliberately public: this page only serves static agent instructions.
    # Keep user-specific values, especially API keys, out of this context.
    template_name = "pages/agent-skill.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["djass_agent_skill_md"] = build_djass_agent_skill_md()
        return context


class ProjectCreateView(LoginRequiredMixin, TemplateView):
    login_url = "account_login"
    template_name = "pages/project-create.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["project_form"] = ProjectCreateForm(user=self.request.user)
        context["project_limit_reached"] = _user_can_create_projects(
            self.request.user
        ) and _project_limit_reached(self.request.user)
        context["can_generate"] = (
            _user_can_create_projects(self.request.user) and not context["project_limit_reached"]
        )
        return context


@login_required
@require_POST
def create_project(request):
    if not _user_can_create_projects(request.user):
        try:
            failure_reason = (
                "subscription_required" if _payments_enabled() else "account_unavailable"
            )
            _queue_profile_event(
                profile=request.user.profile,
                event_name="project_create_failed",
                properties={
                    "reason": failure_reason,
                    "funnel_step": "project_create_failed",
                    "entrypoint": "ui",
                },
                source_function="create_project",
            )
        except Profile.DoesNotExist:
            logger.warning("Project creation denied because user profile is missing")
        return _deny_project_access(request)

    project_quota = project_create_quota()
    if _user_project_count(request.user) >= project_quota:
        _queue_profile_event(
            profile=request.user.profile,
            event_name="project_create_failed",
            properties={
                "reason": "quota_exceeded",
                "quota": project_quota,
                "funnel_step": "project_create_failed",
                "entrypoint": "ui",
            },
            source_function="create_project",
        )
        messages.error(
            request,
            (
                f"You've reached the current limit of {project_quota} projects. "
                "Please contact support if you need more room."
            ),
        )
        return redirect("project_new")

    form = ProjectCreateForm(request.POST, user=request.user)
    if not form.is_valid():
        validation_fields = sorted(form.errors.keys())
        _queue_profile_event(
            profile=request.user.profile,
            event_name="project_create_failed",
            properties={
                "reason": "validation_error",
                "validation_fields": validation_fields,
                "funnel_step": "project_create_failed",
                "entrypoint": "ui",
            },
            source_function="create_project",
        )
        for field_name, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field_name}: {error}")
        return redirect("project_new")

    payload = form.get_cookiecutter_payload()
    project_name = payload["project_name"]
    project_slug = payload["project_slug"]

    project = Project.objects.create(
        user=request.user,
        name=project_name,
        slug=slugify(project_slug).replace("-", "_")[:255],
        input_payload=payload,
        status=ProjectStatus.QUEUED,
    )

    _queue_profile_event(
        profile=request.user.profile,
        event_name="project_created",
        properties={
            "project_id": project.id,
            "project_name": project.name,
            "project_slug": project.slug,
            "funnel_step": "project_created",
            "entrypoint": "ui",
        },
        source_function="create_project",
    )

    async_task(
        "apps.core.tasks.generate_project_artifact",
        project_id=project.id,
        group="Generate Project",
    )
    messages.success(request, f"Project '{project.name}' queued for generation.")
    return redirect("home")


@login_required
def download_project_artifact(request, project_id):
    project = get_object_or_404(Project, id=project_id, user=request.user)
    if project.status != ProjectStatus.READY or not hasattr(project, "artifact"):
        raise Http404("Artifact is not ready yet.")

    artifact = project.artifact
    artifact.zip_file.open("rb")
    safe_slug = project.slug or slugify(project.name) or "project"
    filename = f"{safe_slug}-{timezone.now().strftime('%Y%m%d')}.zip"
    return FileResponse(artifact.zip_file, as_attachment=True, filename=filename)


@require_POST
@login_required
def retry_project_generation(request, project_id):
    if not _user_can_create_projects(request.user):
        return _deny_project_access(request)

    project = get_object_or_404(Project, id=project_id, user=request.user)
    if project.status not in [ProjectStatus.FAILED, ProjectStatus.READY]:
        messages.error(request, "Project cannot be retried from its current state.")
        return redirect("home")

    project.status = ProjectStatus.QUEUED
    project.error_message = ""
    project.started_at = None
    project.finished_at = None
    project.save(
        update_fields=["status", "error_message", "started_at", "finished_at", "updated_at"]
    )

    async_task(
        "apps.core.tasks.generate_project_artifact",
        project_id=project.id,
        group="Generate Project",
    )
    messages.success(request, f"Regeneration queued for '{project.name}'.")
    return redirect("home")


class UserSettingsView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    login_url = "account_login"
    model = Profile
    form_class = ProfileUpdateForm
    success_message = "User Profile Updated"
    success_url = reverse_lazy("settings")
    template_name = "pages/user-settings.html"

    def get_object(self):
        profile, _created = Profile.objects.get_or_create(user=self.request.user)
        return profile

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        profile = self.object

        email_address = EmailAddress.objects.filter(user=user, email__iexact=user.email).first()
        context["email_verified"] = bool(email_address and email_address.verified)
        context["resend_confirmation_url"] = reverse("resend_confirmation")
        context["passkey_count"] = Authenticator.objects.filter(
            user=user,
            type=Authenticator.Type.WEBAUTHN,
        ).count()
        context["has_recovery_codes"] = Authenticator.objects.filter(
            user=user,
            type=Authenticator.Type.RECOVERY_CODES,
        ).exists()
        context["api_key"] = profile.key

        return context


@login_required
@require_POST
def resend_confirmation_email(request):
    user = request.user

    try:
        email_address = EmailAddress.objects.filter(user=user, email__iexact=user.email).first()

        if not email_address:
            messages.error(request, "No email address found for your account.")
            logger.warning(
                "[Resend Confirmation] No email address found",
                user_id=user.id,
                user_email=user.email,
            )
            return redirect("settings")

        if email_address.verified:
            messages.info(request, "Your email is already verified.")
            logger.info(
                "[Resend Confirmation] Email already verified",
                user_id=user.id,
                user_email=user.email,
            )
            return redirect("settings")

        sent = send_verification_email_to_address(request, email_address, signup=False)
        if not sent:
            messages.error(
                request,
                "Please wait before requesting another confirmation email.",
            )
            return redirect("settings")
        logger.info(
            "[Resend Confirmation] Email sent successfully",
            user_id=user.id,
            user_email=user.email,
        )
        if settings.ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED:
            return redirect("account_email_verification_sent")
        messages.success(request, "Confirmation email sent. Please check your inbox.")

    except Exception as e:
        messages.error(request, "Failed to send confirmation email. Please try again later.")
        logger.error(
            "[Resend Confirmation] Failed to send email",
            user_id=user.id,
            user_email=user.email,
            error=str(e),
            exc_info=True,
        )

    return redirect("settings")


@login_required
@require_POST
def delete_account(request):
    """Permanently delete the current user and all related data.

    Safety: requires a confirmation text value.
    """

    confirmation = request.POST.get("confirmation", "")
    if confirmation != "DELETE":
        messages.error(request, "Type DELETE to confirm account deletion.")
        return redirect("settings")

    user_id = request.user.id

    # Ensure we log the user out and remove data in a single flow.
    with transaction.atomic():
        user = request.user
        logout(request)
        user.delete()

    logger.info("User account deleted", user_id=user_id)
    return redirect(f"{reverse('landing')}?account_deleted=1")


@login_required
@require_POST
def create_checkout_session(request, pk, plan):  # noqa: C901
    if not _payments_enabled():
        messages.info(request, "Generation is free right now. You can create projects immediately.")
        return redirect("project_new")

    user = request.user
    profile = user.profile
    plan_key = (plan or "").lower()

    if plan_key != "one-time":
        logger.warning(
            "Attempted checkout for unsupported plan",
            plan=plan,
            user_id=user.id,
        )
        messages.error(request, "Only the one-time plan is available.")
        return redirect("free_access")

    if profile.has_active_subscription:
        messages.info(request, "Project generation is already active for this account.")
        return redirect("project_new")

    price_id = get_price_id_for_plan("one-time")
    if not price_id:
        logger.warning("Stripe price id not configured for one-time plan", user_id=user.id)
        messages.error(request, "Unable to find pricing for the selected plan.")
        return redirect("free_access")

    expected_amount_cents = settings.STRIPE_ONE_TIME_AMOUNT_CENTS
    try:
        price = stripe.Price.retrieve(price_id)
    except stripe.error.StripeError as exc:
        logger.error(
            "Stripe price validation failed",
            profile_id=profile.id,
            price_id=price_id,
            error=str(exc),
        )
        _queue_profile_event(
            profile=profile,
            event_name="checkout_failed",
            properties={
                "reason": "price_validation_failed",
                "error_type": exc.__class__.__name__,
                "plan": "one-time",
                "funnel_step": "checkout_failed",
                "entrypoint": "ui",
            },
            source_function="create_checkout_session",
        )
        messages.error(request, "Unable to validate pricing. Please try again.")
        return redirect("free_access")

    price_amount = getattr(price, "unit_amount", None)
    if price_amount is None and hasattr(price, "get"):
        price_amount = price.get("unit_amount")
    if price_amount != expected_amount_cents:
        logger.error(
            "Stripe one-time price amount mismatch",
            profile_id=profile.id,
            price_id=price_id,
            expected_amount_cents=expected_amount_cents,
            actual_amount_cents=price_amount,
        )
        _queue_profile_event(
            profile=profile,
            event_name="checkout_failed",
            properties={
                "reason": "price_amount_mismatch",
                "plan": "one-time",
                "funnel_step": "checkout_failed",
                "entrypoint": "ui",
                "expected_amount_cents": expected_amount_cents,
                "actual_amount_cents": price_amount,
            },
            source_function="create_checkout_session",
        )
        messages.error(request, "Pricing is being updated. Please try again in a moment.")
        return redirect("free_access")

    try:
        customer = get_or_create_stripe_customer(profile, user)
    except stripe.error.StripeError as exc:
        logger.error(
            "Stripe customer setup failed",
            profile_id=profile.id,
            error=str(exc),
        )
        _queue_profile_event(
            profile=profile,
            event_name="checkout_failed",
            properties={
                "reason": "customer_setup_failed",
                "error_type": exc.__class__.__name__,
                "funnel_step": "checkout_failed",
                "entrypoint": "ui",
            },
            source_function="create_checkout_session",
        )
        messages.error(request, "Unable to start checkout. Please try again.")
        return redirect("free_access")

    base_success_url = request.build_absolute_uri(reverse("project_new"))
    base_cancel_url = request.build_absolute_uri(reverse("free_access"))
    success_url = f"{base_success_url}?{urlencode({'checkout': 'success'})}"
    cancel_url = f"{base_cancel_url}?{urlencode({'checkout': 'canceled'})}"

    session_params = {
        "customer": customer.id,
        "payment_method_types": ["card"],
        "allow_promotion_codes": True,
        "automatic_tax": {"enabled": True},
        "line_items": [
            {
                "price": price_id,
                "quantity": 1,
            }
        ],
        "mode": "payment",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "customer_update": {
            "address": "auto",
        },
        "client_reference_id": str(user.id),
        "metadata": {
            "user_id": user.id,
            "pk": pk,
            "price_id": price_id,
            "plan": "one-time",
        },
    }

    try:
        checkout_session = stripe.checkout.Session.create(**session_params)
    except stripe.error.StripeError as exc:
        logger.error(
            "Stripe checkout session creation failed",
            profile_id=profile.id,
            plan="one-time",
            error=str(exc),
        )
        _queue_profile_event(
            profile=profile,
            event_name="checkout_failed",
            properties={
                "reason": "session_creation_failed",
                "error_type": exc.__class__.__name__,
                "plan": "one-time",
                "funnel_step": "checkout_failed",
                "entrypoint": "ui",
            },
            source_function="create_checkout_session",
        )
        messages.error(request, "Unable to start checkout. Please try again.")
        return redirect("free_access")

    event_properties = {
        "plan": "one-time",
        "price_id": price_id,
        "amount_cents": price_amount,
    }
    checkout_id = getattr(checkout_session, "id", None)
    if checkout_id:
        event_properties["checkout_id"] = checkout_id
    session_url = getattr(checkout_session, "url", None)
    if not session_url:
        logger.error(
            "Stripe checkout session missing URL",
            profile_id=profile.id,
            checkout_id=checkout_id,
        )
        _queue_profile_event(
            profile=profile,
            event_name="checkout_failed",
            properties={
                **event_properties,
                "reason": "session_url_missing",
                "funnel_step": "checkout_failed",
                "entrypoint": "ui",
            },
            source_function="create_checkout_session",
        )
        messages.error(request, "Unable to start checkout. Please try again.")
        return redirect("free_access")

    _queue_profile_event(
        profile=profile,
        event_name="checkout_started",
        properties={
            **event_properties,
            "funnel_step": "checkout_started",
            "entrypoint": "ui",
        },
        source_function="create_checkout_session",
    )

    return redirect(session_url)


@login_required
def create_customer_portal_session(request):
    if not _payments_enabled():
        messages.info(request, "Account access is free right now.")
        return redirect("settings")

    user = request.user
    profile = user.profile
    if not profile.stripe_customer_id:
        messages.error(request, "No Stripe customer found for this account.")
        return redirect("settings")

    try:
        session = stripe.billing_portal.Session.create(
            customer=profile.stripe_customer_id,
            return_url=request.build_absolute_uri(reverse("home")),
        )
    except stripe.error.StripeError as exc:
        logger.error(
            "Stripe portal session creation failed",
            profile_id=profile.id,
            stripe_customer_id=profile.stripe_customer_id,
            error=str(exc),
        )
        messages.error(request, "Unable to open the billing portal. Please try again.")
        return redirect("settings")

    session_url = getattr(session, "url", None)
    if not session_url:
        logger.error(
            "Stripe portal session missing URL",
            profile_id=profile.id,
            stripe_customer_id=profile.stripe_customer_id,
        )
        messages.error(request, "Unable to open the billing portal. Please try again.")
        return redirect("settings")

    return redirect(session_url)


class AdminPanelView(UserPassesTestMixin, TemplateView):
    template_name = "pages/admin-panel.html"
    login_url = "account_login"

    def test_func(self):
        return self.request.user.is_superuser

    def handle_no_permission(self):
        messages.error(self.request, "You don't have permission to access this page.")
        return redirect("home")

    def get_context_data(self, **kwargs):
        from datetime import timedelta

        from django.contrib.auth.models import User
        from django.utils import timezone

        from apps.core.models import Feedback, Profile

        context = super().get_context_data(**kwargs)

        now = timezone.now()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        total_users = User.objects.count()
        total_profiles = Profile.objects.count()
        total_feedback = Feedback.objects.count()

        new_users_week = User.objects.filter(date_joined__gte=week_ago).count()
        new_users_month = User.objects.filter(date_joined__gte=month_ago).count()
        feedback_week = Feedback.objects.filter(created_at__gte=week_ago).count()

        recent_users = User.objects.select_related("profile").order_by("-date_joined")[:10]
        recent_feedback = Feedback.objects.select_related("profile__user").order_by("-created_at")[
            :10
        ]

        # Calculate average users per day for last 30 days
        avg_users_per_day = new_users_month / 30 if new_users_month > 0 else 0

        context.update(
            {
                "total_users": total_users,
                "total_profiles": total_profiles,
                "total_feedback": total_feedback,
                "new_users_week": new_users_week,
                "new_users_month": new_users_month,
                "feedback_week": feedback_week,
                "recent_users": recent_users,
                "recent_feedback": recent_feedback,
                "avg_users_per_day": avg_users_per_day,
            }
        )

        logger.info(
            "Admin panel accessed",
            email=self.request.user.email,
            profile_id=self.request.user.profile.id,
        )

        return context


def get_price_id_for_plan(plan):
    plan_key = (plan or "").lower()
    price_id = settings.STRIPE_PRICE_IDS.get(plan_key) or None
    return price_id


def get_or_create_stripe_customer(profile, user):
    if profile.stripe_customer_id:
        try:
            return stripe.Customer.retrieve(profile.stripe_customer_id)
        except stripe.error.InvalidRequestError as exc:
            logger.warning(
                "Stripe customer lookup failed",
                profile_id=profile.id,
                stripe_customer_id=profile.stripe_customer_id,
                error=str(exc),
            )

    customer = stripe.Customer.create(
        email=user.email,
        name=user.get_full_name() or user.username,
        metadata={"user_id": user.id},
    )
    profile.stripe_customer_id = customer.id
    profile.save(update_fields=["stripe_customer_id"])
    return customer


@csrf_exempt
def stripe_webhook(request):
    logger.info("Stripe webhook received", request=request)

    if request.method != "POST":
        return HttpResponse(status=405)

    if not settings.STRIPE_WEBHOOK_SECRET:
        logger.error("Stripe webhook secret not configured")
        return HttpResponse(status=500)

    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
    if not sig_header:
        return HttpResponseBadRequest("Missing Stripe-Signature header")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=settings.STRIPE_WEBHOOK_SECRET,
        )
    except ValueError:
        return HttpResponseBadRequest("Invalid payload")
    except stripe.error.SignatureVerificationError:
        return HttpResponseBadRequest("Invalid signature")

    event_id = event.get("id")
    if event_id:
        cache_key = f"stripe_event:{event_id}"
        if cache.get(cache_key):
            logger.info(
                "Duplicate Stripe webhook received",
                event_type=event.get("type"),
                event_id=event_id,
            )
            return HttpResponse(status=200)

    handler = EVENT_HANDLERS.get(event.get("type"))
    if handler:
        handler(event)
    else:
        logger.info(
            "Unhandled Stripe webhook",
            event_type=event.get("type"),
            event_id=event.get("id"),
        )

    if event_id:
        cache.set(cache_key, True, timeout=60 * 60 * 24)

    return HttpResponse(status=200)
