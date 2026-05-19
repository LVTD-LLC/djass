import json

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import FileResponse, HttpRequest
from django.utils import timezone
from django.utils.text import slugify
from django_q.tasks import async_task
from ninja import NinjaAPI, Query
from ninja.errors import AuthenticationError, HttpError, ValidationError

from apps.api.audit import action_for_request, log_project_api_action
from apps.api.auth import (
    APIAuthPrincipal,
    header_or_query_api_key_auth,
    session_auth,
    superuser_api_auth,
)
from apps.api.models import ProjectAPIAuditLog
from apps.api.schemas import (
    ApiError,
    BlogPostIn,
    BlogPostOut,
    ProjectCreateIn,
    ProjectCreateOut,
    ProjectGeneratorOptionsOut,
    ProjectListOut,
    ProjectOut,
    ProjectStatusOut,
    SubmitFeedbackIn,
    SubmitFeedbackOut,
    UserSettingsOut,
)
from apps.blog.models import BlogPost
from apps.core.generator_options import (
    COOKIECUTTER_FIELD_DEFAULTS,
    MODULE_FLAG_KEYS,
    get_generator_option_catalog,
)
from apps.core.models import Feedback, Project, ProjectStatus
from djass.utils import get_djass_logger

logger = get_djass_logger(__name__)

api = NinjaAPI()


ERROR_TAXONOMY = {
    "auth_required": {"category": "auth", "retryable": False},
    "insufficient_scope": {"category": "auth", "retryable": False},
    "quota_exceeded": {"category": "quota", "retryable": False},
    "invalid_project_slug": {"category": "validation", "retryable": False},
    "invalid_generator_option": {"category": "validation", "retryable": False},
    "validation_error": {"category": "validation", "retryable": False},
    "project_not_found": {"category": "validation", "retryable": False},
    "artifact_not_ready": {"category": "retryable", "retryable": True},
    "retryable_error": {"category": "retryable", "retryable": True},
    "internal_error": {"category": "internal", "retryable": False},
    "http_error": {"category": "internal", "retryable": False},
}


def _error(status: int, code: str, message: str, *, details: dict | None = None):
    taxonomy = ERROR_TAXONOMY.get(code, {"category": "internal", "retryable": False})
    return status, {
        "error": {
            "code": code,
            "category": taxonomy["category"],
            "message": message,
            "retryable": taxonomy["retryable"],
            "details": details or {},
        }
    }


@api.exception_handler(AuthenticationError)
def on_authentication_error(request: HttpRequest, exc: AuthenticationError):
    action = action_for_request(request)
    if action:
        log_project_api_action(
            request,
            action=action,
            status_code=401,
            metadata={
                "error": "auth_required",
                "api_key_present": bool(getattr(request, "api_key_attempt", None)),
            },
        )

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


def _project_create_payload(request: HttpRequest, data: ProjectCreateIn) -> dict:
    payload = data.model_dump()
    extra_payload = getattr(data, "__pydantic_extra__", None) or {}
    payload.update(extra_payload)

    try:
        raw_payload = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        raw_payload = {}

    if isinstance(raw_payload, dict):
        for key, value in raw_payload.items():
            payload.setdefault(key, value)
    return payload


def _invalid_cookiecutter_options(payload: dict) -> dict[str, list[str]]:
    unknown_keys = sorted(set(payload) - set(COOKIECUTTER_FIELD_DEFAULTS))
    invalid_flags = sorted(
        key for key in MODULE_FLAG_KEYS if key in payload and payload[key] not in {"y", "n"}
    )
    return {
        "unknown": unknown_keys,
        "invalid_flags": invalid_flags,
    }


def _validate_project_create_payload(
    request: HttpRequest,
    principal: APIAuthPrincipal,
    profile,
    data: ProjectCreateIn,
):
    payload = _project_create_payload(request, data)
    if not payload.get("author_email"):
        payload["author_email"] = profile.user.email or ""

    option_errors = _invalid_cookiecutter_options(payload)
    if option_errors["unknown"] or option_errors["invalid_flags"]:
        _queue_profile_event(
            profile=profile,
            event_name="project_create_failed",
            properties={
                "reason": "invalid_generator_option",
                "funnel_step": "project_create_failed",
                "entrypoint": "api",
            },
            source_function="create_project_v1",
        )
        log_project_api_action(
            request,
            action="project.create",
            status_code=400,
            principal=principal,
            metadata={
                "error": "invalid_generator_option",
                **option_errors,
            },
        )
        return None, _error(
            400,
            "invalid_generator_option",
            "Request includes unknown or invalid generator options.",
            details=option_errors,
        )

    for key, default_value in COOKIECUTTER_FIELD_DEFAULTS.items():
        payload.setdefault(key, default_value)
    return payload, None


def _require_scope(principal: APIAuthPrincipal, scope: str):
    if principal.has_scope(scope):
        return None
    return _error(
        403,
        "insufficient_scope",
        f"API key is missing required scope: {scope}",
        details={"required_scope": scope},
    )


def _project_create_quota() -> int:
    return int(getattr(settings, "PROJECT_API_MAX_PROJECTS_PER_USER", 200))


def _queue_profile_event(profile, event_name: str, properties: dict, source_function: str) -> None:
    try:
        async_task(
            "apps.core.tasks.track_event",
            profile_id=profile.id,
            event_name=event_name,
            properties=properties,
            source_function=source_function,
            group="Track Event",
        )
    except Exception as exc:
        logger.warning(
            "Failed to queue profile event",
            event_name=event_name,
            profile_id=getattr(profile, "id", None),
            error=str(exc),
        )


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
            "can_generate_projects": True,
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


@api.get(
    "/v1/project-options",
    response={200: ProjectGeneratorOptionsOut},
    auth=None,
    tags=["v1"],
)
def get_project_options_v1(request: HttpRequest):
    return get_generator_option_catalog().as_api_payload()


@api.post(
    "/v1/projects",
    response={
        201: ProjectCreateOut,
        400: ApiError,
        401: ApiError,
        403: ApiError,
        429: ApiError,
        500: ApiError,
        503: ApiError,
    },
    auth=[header_or_query_api_key_auth],
    tags=["v1"],
)
def create_project_v1(request: HttpRequest, data: ProjectCreateIn):
    principal = request.auth
    profile = principal.profile if principal else None
    if not profile:
        return _error(401, "auth_required", "Authentication required.")

    scope_error = _require_scope(principal, "projects:create")
    if scope_error:
        _queue_profile_event(
            profile=profile,
            event_name="user_auth_failed",
            properties={
                "reason": "insufficient_scope",
                "required_scope": "projects:create",
                "funnel_step": "auth_failed",
                "entrypoint": "api",
            },
            source_function="create_project_v1",
        )
        log_project_api_action(
            request,
            action="project.create",
            status_code=403,
            principal=principal,
            metadata={"error": "insufficient_scope", "required_scope": "projects:create"},
        )
        return scope_error

    normalized_slug = slugify(data.project_slug).replace("-", "_")
    if not normalized_slug:
        _queue_profile_event(
            profile=profile,
            event_name="project_create_failed",
            properties={
                "reason": "invalid_project_slug",
                "funnel_step": "project_create_failed",
                "entrypoint": "api",
            },
            source_function="create_project_v1",
        )
        log_project_api_action(
            request,
            action="project.create",
            status_code=400,
            principal=principal,
            metadata={"error": "invalid_project_slug"},
        )
        return _error(
            400,
            "invalid_project_slug",
            "project_slug must contain letters or numbers.",
            details={"field": "project_slug"},
        )

    user_project_count = Project.objects.filter(user=profile.user).count()
    project_quota = _project_create_quota()
    if user_project_count >= project_quota:
        _queue_profile_event(
            profile=profile,
            event_name="project_create_failed",
            properties={
                "reason": "quota_exceeded",
                "quota": project_quota,
                "funnel_step": "project_create_failed",
                "entrypoint": "api",
            },
            source_function="create_project_v1",
        )
        log_project_api_action(
            request,
            action="project.create",
            status_code=429,
            principal=principal,
            metadata={"error": "quota_exceeded", "quota": project_quota},
        )
        return _error(
            429,
            "quota_exceeded",
            "Project quota exceeded for this API identity.",
            details={
                "quota": project_quota,
                "retry_guidance": "Delete old projects or request limit bump.",
            },
        )

    payload, payload_error = _validate_project_create_payload(request, principal, profile, data)
    if payload_error:
        return payload_error

    try:
        project = Project.objects.create(
            user=profile.user,
            name=data.project_name,
            slug=normalized_slug[:255],
            input_payload=payload,
            status=ProjectStatus.QUEUED,
        )
        _queue_profile_event(
            profile=profile,
            event_name="project_created",
            properties={
                "project_id": project.id,
                "project_name": project.name,
                "project_slug": project.slug,
                "funnel_step": "project_created",
                "entrypoint": "api",
            },
            source_function="create_project_v1",
        )
        async_task(
            "apps.core.tasks.generate_project_artifact",
            project_id=project.id,
            group="Generate Project",
        )
    except OSError as exc:
        logger.warning(
            "Retryable project creation failure",
            error=str(exc),
            user_id=profile.user_id,
        )
        _queue_profile_event(
            profile=profile,
            event_name="project_create_failed",
            properties={
                "reason": "retryable_error",
                "error_type": exc.__class__.__name__,
                "funnel_step": "project_create_failed",
                "entrypoint": "api",
            },
            source_function="create_project_v1",
        )
        log_project_api_action(
            request,
            action="project.create",
            status_code=503,
            principal=principal,
            metadata={"error": "retryable_error"},
        )
        return _error(
            503,
            "retryable_error",
            "Temporary failure while queueing project generation.",
            details={"retry_guidance": "Retry with exponential backoff."},
        )
    except Exception as exc:
        logger.error("Internal project creation failure", error=str(exc), user_id=profile.user_id)
        _queue_profile_event(
            profile=profile,
            event_name="project_create_failed",
            properties={
                "reason": "internal_error",
                "error_type": exc.__class__.__name__,
                "funnel_step": "project_create_failed",
                "entrypoint": "api",
            },
            source_function="create_project_v1",
        )
        log_project_api_action(
            request,
            action="project.create",
            status_code=500,
            principal=principal,
            metadata={"error": "internal_error"},
        )
        return _error(
            500,
            "internal_error",
            "Internal error while creating project.",
            details={"retry_guidance": "Retry later or contact support if persistent."},
        )

    log_project_api_action(
        request,
        action="project.create",
        status_code=201,
        principal=principal,
        project=project,
    )
    _queue_profile_event(
        profile=profile,
        event_name="project_created",
        properties={
            "project_id": project.id,
            "project_name": project.name,
            "project_slug": project.slug,
            "funnel_step": "project_created",
        },
        source_function="create_project_v1",
    )
    return 201, {"project": _serialize_project(project)}


@api.get(
    "/v1/projects",
    response={200: ProjectListOut, 401: ApiError, 403: ApiError, 422: ApiError, 500: ApiError},
    auth=[header_or_query_api_key_auth],
    tags=["v1"],
)
def list_projects_v1(
    request: HttpRequest,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: ProjectStatus | None = None,
):
    principal = request.auth
    profile = principal.profile if principal else None
    if not profile:
        return _error(401, "auth_required", "Authentication required.")

    scope_error = _require_scope(principal, "projects:read")
    if scope_error:
        log_project_api_action(
            request,
            action="project.list",
            status_code=403,
            principal=principal,
            metadata={"error": "insufficient_scope", "required_scope": "projects:read"},
        )
        return scope_error

    try:
        queryset = Project.objects.filter(user=profile.user).prefetch_related("artifact")
        filters = {}
        if status:
            queryset = queryset.filter(status=status)
            filters["status"] = status

        total = queryset.count()
        rows = list(queryset[offset : offset + limit])
        projects = [_serialize_project(project) for project in rows]
    except Exception as exc:
        logger.error("Internal project list failure", error=str(exc), user_id=profile.user_id)
        log_project_api_action(
            request,
            action="project.list",
            status_code=500,
            principal=principal,
            metadata={"error": "internal_error"},
        )
        return _error(
            500,
            "internal_error",
            "Internal error while listing projects.",
            details={"retry_guidance": "Retry later."},
        )

    log_project_api_action(
        request,
        action="project.list",
        status_code=200,
        principal=principal,
        metadata={"count": len(projects), "total": total, "limit": limit, "offset": offset},
    )
    return {
        "projects": projects,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_next": offset + len(projects) < total,
        "filters": filters,
    }


@api.get(
    "/v1/projects/{project_id}",
    response={200: ProjectOut, 401: ApiError, 403: ApiError, 404: ApiError, 500: ApiError},
    auth=[header_or_query_api_key_auth],
    tags=["v1"],
)
def get_project_v1(request: HttpRequest, project_id: int):
    principal = request.auth
    profile = principal.profile if principal else None
    if not profile:
        return _error(401, "auth_required", "Authentication required.")

    scope_error = _require_scope(principal, "projects:read")
    if scope_error:
        log_project_api_action(
            request,
            action="project.get",
            status_code=403,
            principal=principal,
            metadata={"error": "insufficient_scope", "required_scope": "projects:read"},
        )
        return scope_error

    try:
        project = Project.objects.prefetch_related("artifact").get(id=project_id, user=profile.user)
    except Project.DoesNotExist:
        log_project_api_action(
            request,
            action="project.get",
            status_code=404,
            principal=principal,
            metadata={"error": "project_not_found", "project_id": project_id},
        )
        return _error(
            404,
            "project_not_found",
            "Project not found.",
            details={"project_id": project_id},
        )
    except Exception as exc:
        logger.error("Internal project get failure", error=str(exc), user_id=profile.user_id)
        log_project_api_action(
            request,
            action="project.get",
            status_code=500,
            principal=principal,
            metadata={"error": "internal_error", "project_id": project_id},
        )
        return _error(
            500,
            "internal_error",
            "Internal error while fetching project.",
            details={"project_id": project_id, "retry_guidance": "Retry later."},
        )

    log_project_api_action(
        request,
        action="project.get",
        status_code=200,
        principal=principal,
        project=project,
    )
    return _serialize_project(project)


@api.get(
    "/v1/projects/{project_id}/status",
    response={200: ProjectStatusOut, 401: ApiError, 403: ApiError, 404: ApiError, 500: ApiError},
    auth=[header_or_query_api_key_auth],
    tags=["v1"],
)
def get_project_status_v1(request: HttpRequest, project_id: int):
    principal = request.auth
    profile = principal.profile if principal else None
    if not profile:
        return _error(401, "auth_required", "Authentication required.")

    scope_error = _require_scope(principal, "projects:read")
    if scope_error:
        log_project_api_action(
            request,
            action="project.status",
            status_code=403,
            principal=principal,
            metadata={"error": "insufficient_scope", "required_scope": "projects:read"},
        )
        return scope_error

    try:
        project = Project.objects.prefetch_related("artifact").get(id=project_id, user=profile.user)
    except Project.DoesNotExist:
        log_project_api_action(
            request,
            action="project.status",
            status_code=404,
            principal=principal,
            metadata={"error": "project_not_found", "project_id": project_id},
        )
        return _error(
            404,
            "project_not_found",
            "Project not found.",
            details={"project_id": project_id},
        )
    except Exception as exc:
        logger.error("Internal project status failure", error=str(exc), user_id=profile.user_id)
        log_project_api_action(
            request,
            action="project.status",
            status_code=500,
            principal=principal,
            metadata={"error": "internal_error", "project_id": project_id},
        )
        return _error(
            500,
            "internal_error",
            "Internal error while fetching project status.",
            details={"project_id": project_id, "retry_guidance": "Retry later."},
        )

    log_project_api_action(
        request,
        action="project.status",
        status_code=200,
        principal=principal,
        project=project,
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


@api.get(
    "/v1/projects/{project_id}/download",
    response={401: ApiError, 403: ApiError, 404: ApiError, 409: ApiError, 500: ApiError},
    auth=[header_or_query_api_key_auth],
    tags=["v1"],
)
def download_project_artifact_v1(request: HttpRequest, project_id: int):
    principal = request.auth
    profile = principal.profile if principal else None
    if not profile:
        return _error(401, "auth_required", "Authentication required.")

    scope_error = _require_scope(principal, "projects:read")
    if scope_error:
        log_project_api_action(
            request,
            action=ProjectAPIAuditLog.ACTION_DOWNLOAD,
            status_code=403,
            principal=principal,
            metadata={"error": "insufficient_scope", "required_scope": "projects:read"},
        )
        return scope_error

    try:
        project = Project.objects.select_related("artifact").get(id=project_id, user=profile.user)
    except Project.DoesNotExist:
        log_project_api_action(
            request,
            action=ProjectAPIAuditLog.ACTION_DOWNLOAD,
            status_code=404,
            principal=principal,
            metadata={"error": "project_not_found", "project_id": project_id},
        )
        return _error(
            404,
            "project_not_found",
            "Project not found.",
            details={"project_id": project_id},
        )
    except Exception as exc:
        logger.error(
            "Internal project artifact download lookup failure",
            error=str(exc),
            user_id=profile.user_id,
        )
        log_project_api_action(
            request,
            action=ProjectAPIAuditLog.ACTION_DOWNLOAD,
            status_code=500,
            principal=principal,
            metadata={"error": "internal_error", "project_id": project_id},
        )
        return _error(
            500,
            "internal_error",
            "Internal error while fetching project artifact.",
            details={"project_id": project_id, "retry_guidance": "Retry later."},
        )

    if project.status != ProjectStatus.READY or not hasattr(project, "artifact"):
        log_project_api_action(
            request,
            action=ProjectAPIAuditLog.ACTION_DOWNLOAD,
            status_code=409,
            principal=principal,
            project=project,
            metadata={"error": "artifact_not_ready", "project_status": project.status},
        )
        return _error(
            409,
            "artifact_not_ready",
            "Project artifact is not ready yet.",
            details={
                "project_id": project_id,
                "status": project.status,
                "retry_guidance": "Poll the status endpoint until artifact_ready is true.",
            },
        )

    artifact = project.artifact
    try:
        artifact.zip_file.open("rb")
    except Exception as exc:
        logger.error(
            "Internal project artifact file open failure", error=str(exc), project_id=project.id
        )
        log_project_api_action(
            request,
            action=ProjectAPIAuditLog.ACTION_DOWNLOAD,
            status_code=500,
            principal=principal,
            project=project,
            metadata={"error": "internal_error", "project_id": project_id},
        )
        return _error(
            500,
            "internal_error",
            "Internal error while opening project artifact.",
            details={"project_id": project_id, "retry_guidance": "Retry later."},
        )

    safe_slug = project.slug or slugify(project.name) or "project"
    filename = f"{safe_slug}-{timezone.now().strftime('%Y%m%d')}.zip"
    log_project_api_action(
        request,
        action=ProjectAPIAuditLog.ACTION_DOWNLOAD,
        status_code=200,
        principal=principal,
        project=project,
        metadata={"size_bytes": artifact.size_bytes, "sha256": artifact.sha256},
    )
    return FileResponse(artifact.zip_file, as_attachment=True, filename=filename)
