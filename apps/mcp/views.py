from django.conf import settings
from django.http import FileResponse, Http404, HttpRequest, JsonResponse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods

from apps.api.audit import log_project_api_action
from apps.api.auth import APIAuthPrincipal, header_or_query_api_key_auth
from apps.api.models import ProjectAPIAuditLog
from apps.core.models import Project, ProjectStatus
from apps.mcp import services


def _principal(request: HttpRequest) -> APIAuthPrincipal | None:
    return header_or_query_api_key_auth.authenticate(request)


def _scope_error(principal: APIAuthPrincipal, scope: str) -> dict | None:
    if principal.has_scope(scope):
        return None
    return {
        "code": "insufficient_scope",
        "message": f"API key is missing required scope: {scope}",
        "required_scope": scope,
    }


@require_http_methods(["GET"])
def mcp_project_download(request: HttpRequest, project_id: int):
    principal = _principal(request)
    if not principal:
        return JsonResponse(
            {"error": {"code": "auth_required", "message": "Authentication required."}}, status=401
        )

    scope_error = _scope_error(principal, "projects:read")
    if scope_error:
        return JsonResponse({"error": scope_error}, status=403)

    try:
        project = Project.objects.select_related("artifact").get(
            id=project_id, user=principal.profile.user
        )
    except Project.DoesNotExist as exc:
        raise Http404("Project not found.") from exc

    if project.status != ProjectStatus.READY or not hasattr(project, "artifact"):
        raise Http404("Artifact is not ready yet.")

    artifact = project.artifact
    artifact.zip_file.open("rb")
    safe_slug = project.slug or slugify(project.name) or "project"
    filename = f"{safe_slug}-{timezone.now().strftime('%Y%m%d')}.zip"
    log_project_api_action(
        request,
        action=ProjectAPIAuditLog.ACTION_DOWNLOAD,
        status_code=200,
        principal=principal,
        project=project,
        metadata={"transport": "fastmcp", "direct_download": True},
    )
    return FileResponse(artifact.zip_file, as_attachment=True, filename=filename)


@require_http_methods(["GET"])
def mcp_prompt(request: HttpRequest):
    base_url = str(settings.SITE_URL).rstrip("/")
    mcp_url = f"{base_url}/mcp"
    options_url = f"{base_url}/api/v1/project-options"
    prompt = "\n".join(
        [
            "Use Djass to generate Django SaaS projects for this user.",
            "",
            "Connection:",
            f"- Djass site: {base_url}",
            f"- FastMCP endpoint: {mcp_url}",
            "- Auth: ask the user for their Djass API key and send it as Authorization: "
            "Bearer <key>. Never print or commit the key.",
            "",
            "Workflow:",
            "1. Connect to the hosted Djass FastMCP server.",
            "2. Always call djass_generation_options before creating a project. "
            f"If MCP is unavailable, fetch {options_url}.",
            "3. Ask concise follow-up questions for every required field and every "
            "current option the user did not specify.",
            "4. If the user explicitly says to decide for them, choose sensible defaults, "
            "summarize those choices, then continue.",
            "5. Only call djass_create_project after the intent and options are clear.",
            "6. Poll djass_get_project_status until status is ready or failed.",
            "7. When ready, call djass_get_project_download and download the ZIP from "
            "the returned URL using the same Authorization header.",
        ]
    )
    return JsonResponse({"prompt": prompt, "options": services.get_generator_options()})
