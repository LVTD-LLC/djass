from django.http import HttpRequest

from apps.api.auth import APIAuthPrincipal
from apps.api.models import ProjectAPIAuditLog
from apps.core.models import Project
from djass.utils import get_djass_logger

logger = get_djass_logger(__name__)


def _client_ip(request: HttpRequest) -> str | None:
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR")


def action_for_request(request: HttpRequest) -> str | None:
    path = request.path
    method = request.method.upper()

    if path == "/api/v1/projects":
        if method == "POST":
            return ProjectAPIAuditLog.ACTION_CREATE
        if method == "GET":
            return ProjectAPIAuditLog.ACTION_LIST

    if path.endswith("/status") and method == "GET":
        return ProjectAPIAuditLog.ACTION_STATUS

    if path.endswith("/download") and method == "GET":
        return ProjectAPIAuditLog.ACTION_DOWNLOAD

    if "/api/v1/projects/" in path and method == "GET":
        return ProjectAPIAuditLog.ACTION_GET

    return None


def log_project_api_action(
    request: HttpRequest,
    *,
    action: str,
    status_code: int,
    principal: APIAuthPrincipal | None = None,
    project: Project | None = None,
    metadata: dict | None = None,
):
    try:
        ProjectAPIAuditLog.objects.create(
            profile=principal.profile if principal else None,
            api_key=principal.project_api_key if principal else None,
            project=project,
            action=action,
            status_code=status_code,
            method=request.method.upper(),
            path=request.path,
            ip_address=_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:512],
            key_type=principal.key_type if principal else "",
            metadata=metadata or {},
        )
    except Exception as exc:  # pragma: no cover
        logger.warning(
            "Failed to persist API audit log",
            action=action,
            status_code=status_code,
            error=str(exc),
        )
