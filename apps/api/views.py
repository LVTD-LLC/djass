from django.core.cache import cache
from django.db import connection
from django.http import HttpRequest
from django.utils.text import slugify
from django_q.tasks import async_task
from ninja import NinjaAPI
from ninja.errors import AuthenticationError, HttpError, ValidationError

from apps.api.auth import header_or_query_api_key_auth, session_auth, superuser_api_auth
from apps.api.schemas import (
    ApiError,
    BlogPostIn,
    BlogPostOut,
    ProjectCreateIn,
    ProjectCreateOut,
    ProjectListOut,
    ProjectOut,
    ProjectStatusOut,
    SubmitFeedbackIn,
    SubmitFeedbackOut,
    UserSettingsOut,
)
from apps.blog.models import BlogPost
from apps.core.choices import ProfileStates
from apps.core.models import Feedback, Project, ProjectStatus
from djass.utils import get_djass_logger

logger = get_djass_logger(__name__)

api = NinjaAPI()


def _error(status: int, code: str, message: str, *, details: dict | None = None):
    return status, {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        }
    }


@api.exception_handler(AuthenticationError)
def on_authentication_error(request: HttpRequest, exc: AuthenticationError):
    return api.create_response(
        request,
        _error(401, "auth_required", str(exc))[1],
        status=401,
    )


@api.exception_handler(ValidationError)
def on_validation_error(request: HttpRequest, exc: ValidationError):
    return api.create_response(
        request,
        _error(
            422,
            "validation_error",
            "Request validation failed.",
            details={"violations": exc.errors},
        )[1],
        status=422,
    )


@api.exception_handler(HttpError)
def on_http_error(request: HttpRequest, exc: HttpError):
    details = {}
    message = exc.message
    if not isinstance(message, str):
        details = {"message": message}
        message = "Request failed."

    return api.create_response(
        request,
        _error(exc.status_code, "http_error", message, details=details)[1],
        status=exc.status_code,
    )


def _serialize_project(project: Project) -> dict:
    return {
        "id": project.id,
        "name": project.name,
        "slug": project.slug,
        "status": project.status,
        "error_message": project.error_message,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
        "started_at": project.started_at,
        "finished_at": project.finished_at,
        "artifact_ready": hasattr(project, "artifact"),
        "input_payload": project.input_payload,
    }


@api.get("/healthcheck", auth=None, include_in_schema=False, tags=["private"])
def healthcheck(request: HttpRequest):
    """Comprehensive healthcheck endpoint for monitoring and load balancers."""

    checks = {
        "database": False,
        "redis": False,
    }

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["database"] = True
    except Exception as e:
        logger.error(
            "Healthcheck failed: Database connection error",
            error=str(e),
            exc_info=True,
        )

    try:
        cache_key = "healthcheck_test"
        cache_value = "ok"
        cache.set(cache_key, cache_value, timeout=10)
        retrieved_value = cache.get(cache_key)

        if retrieved_value == cache_value:
            checks["redis"] = True
        else:
            logger.error(
                "Healthcheck failed: Redis value mismatch",
                expected=cache_value,
                retrieved=retrieved_value,
            )
    except Exception as e:
        logger.error(
            "Healthcheck failed: Redis connection error",
            error=str(e),
            exc_info=True,
        )

    healthy = all(checks.values())
    payload = {
        "healthy": healthy,
        "checks": checks,
    }

    if healthy:
        logger.info("Healthcheck passed", **checks)
        return payload

    logger.error("Healthcheck failed", **checks)
    return 503, payload


@api.post(
    "/submit-feedback",
    response={200: SubmitFeedbackOut, 401: ApiError, 422: ApiError},
    auth=[session_auth],
    include_in_schema=False,
    tags=["private"],
)
def submit_feedback(request: HttpRequest, data: SubmitFeedbackIn):
    profile = request.auth
    try:
        Feedback.objects.create(profile=profile, feedback=data.feedback, page=data.page)
        return {"success": True, "message": "Feedback submitted successfully"}
    except Exception as e:
        logger.error("Failed to submit feedback", error=str(e), profile_id=profile.id)
        return {"success": False, "message": "Failed to submit feedback. Please try again."}


@api.post(
    "/blog-posts/submit",
    response={200: BlogPostOut, 401: ApiError, 403: ApiError, 422: ApiError},
    auth=[superuser_api_auth],
    include_in_schema=False,
    tags=["admin"],
)
def submit_blog_post(request: HttpRequest, data: BlogPostIn):
    profile = request.auth

    if not profile or not getattr(profile.user, "is_superuser", False):
        return _error(403, "forbidden", "Forbidden: superuser access required.")

    try:
        BlogPost.objects.create(
            title=data.title,
            description=data.description,
            slug=data.slug,
            tags=data.tags,
            content=data.content,
            status=data.status,
        )
        return BlogPostOut(status="success", message="Blog post submitted successfully.")
    except Exception as e:
        return BlogPostOut(status="failure", message=f"Failed to submit blog post: {str(e)}")


@api.get(
    "/user/settings",
    response={200: UserSettingsOut, 401: ApiError, 500: ApiError},
    auth=[session_auth],
    include_in_schema=False,
    tags=["private"],
)
def user_settings(request: HttpRequest):
    profile = request.auth
    try:
        profile_data = {
            "has_pro_subscription": profile.has_active_subscription,
        }
        data = {"profile": profile_data}

        return data
    except Exception as e:
        logger.error(
            "Error fetching user settings",
            error=str(e),
            profile_id=profile.id,
            exc_info=True,
        )
        raise HttpError(500, "An unexpected error occurred.") from e


@api.post(
    "/v1/projects",
    response={201: ProjectCreateOut, 400: ApiError, 401: ApiError, 403: ApiError},
    auth=[header_or_query_api_key_auth],
    tags=["v1"],
)
def create_project_v1(request: HttpRequest, data: ProjectCreateIn):
    profile = request.auth
    if not profile:
        return _error(401, "auth_required", "Authentication required.")

    allowed_states = {
        ProfileStates.TRIAL_STARTED,
        ProfileStates.SUBSCRIBED,
        ProfileStates.CANCELLED,
    }
    if profile.state not in allowed_states and not profile.user.is_superuser:
        return _error(
            403,
            "subscription_required",
            "Project generation requires an active subscription.",
        )

    normalized_slug = slugify(data.project_slug).replace("-", "_")
    if not normalized_slug:
        return _error(
            400,
            "invalid_project_slug",
            "project_slug must contain letters or numbers.",
            details={"field": "project_slug"},
        )

    payload = data.dict()
    if not payload.get("author_email"):
        payload["author_email"] = profile.user.email or ""

    project = Project.objects.create(
        user=profile.user,
        name=data.project_name,
        slug=normalized_slug[:255],
        input_payload=payload,
        status=ProjectStatus.QUEUED,
    )
    async_task(
        "apps.core.tasks.generate_project_artifact",
        project_id=project.id,
        group="Generate Project",
    )

    return 201, {"project": _serialize_project(project)}


@api.get(
    "/v1/projects",
    response={200: ProjectListOut, 401: ApiError},
    auth=[header_or_query_api_key_auth],
    tags=["v1"],
)
def list_projects_v1(request: HttpRequest):
    profile = request.auth
    if not profile:
        return _error(401, "auth_required", "Authentication required.")

    projects = [
        _serialize_project(project)
        for project in Project.objects.filter(user=profile.user).prefetch_related("artifact")
    ]
    return {"projects": projects, "total": len(projects)}


@api.get(
    "/v1/projects/{project_id}",
    response={200: ProjectOut, 401: ApiError, 404: ApiError},
    auth=[header_or_query_api_key_auth],
    tags=["v1"],
)
def get_project_v1(request: HttpRequest, project_id: int):
    profile = request.auth
    if not profile:
        return _error(401, "auth_required", "Authentication required.")

    try:
        project = Project.objects.prefetch_related("artifact").get(id=project_id, user=profile.user)
    except Project.DoesNotExist:
        return _error(
            404,
            "project_not_found",
            "Project not found.",
            details={"project_id": project_id},
        )

    return _serialize_project(project)


@api.get(
    "/v1/projects/{project_id}/status",
    response={200: ProjectStatusOut, 401: ApiError, 404: ApiError},
    auth=[header_or_query_api_key_auth],
    tags=["v1"],
)
def get_project_status_v1(request: HttpRequest, project_id: int):
    profile = request.auth
    if not profile:
        return _error(401, "auth_required", "Authentication required.")

    try:
        project = Project.objects.prefetch_related("artifact").get(id=project_id, user=profile.user)
    except Project.DoesNotExist:
        return _error(
            404,
            "project_not_found",
            "Project not found.",
            details={"project_id": project_id},
        )

    return {
        "id": project.id,
        "status": project.status,
        "error_message": project.error_message,
        "artifact_ready": hasattr(project, "artifact"),
        "started_at": project.started_at,
        "finished_at": project.finished_at,
        "updated_at": project.updated_at,
    }
