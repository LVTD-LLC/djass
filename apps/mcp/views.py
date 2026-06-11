from django.conf import settings
from django.http import FileResponse, Http404, HttpRequest, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods

from apps.api.audit import log_project_api_action
from apps.api.auth import APIAuthPrincipal, header_or_query_api_key_auth
from apps.api.models import ProjectAPIAuditLog
from apps.core.models import Project, ProjectStatus
from apps.mcp import services


def _site_url() -> str:
    return str(settings.SITE_URL).rstrip("/")


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


@require_http_methods(["GET", "OPTIONS"])
def mcp_protected_resource_metadata(request: HttpRequest):
    base_url = _site_url() or request.build_absolute_uri("/").rstrip("/")
    return JsonResponse(
        {
            "resource": f"{base_url}/mcp",
            "authorization_servers": [f"{base_url}/"],
            "scopes_supported": [],
            "bearer_methods_supported": ["header"],
        }
    )


@require_http_methods(["GET"])
def mcp_prompt(request: HttpRequest):
    base_url = _site_url() or request.build_absolute_uri("/").rstrip("/")
    mcp_url = f"{base_url}/mcp"
    skill_url = f"{base_url}{reverse('agent_skill')}"
    options_url = f"{base_url}/api/v1/project-options"
    prompt = "\n".join(
        [
            "Use Djass to generate Django SaaS projects for this user.",
            "",
            "First read and follow the Djass skill instructions:",
            skill_url,
            "",
            "Hosted Djass MCP URL:",
            mcp_url,
            "",
            "Auth:",
            "- Ask the user for their Djass API key.",
            "- Send it as Authorization: Bearer <key>. Never print or commit the key.",
            "",
            "HTTP fallback API base, only if hosted MCP is unavailable:",
            options_url.removesuffix("/project-options"),
        ]
    )
    return JsonResponse({"prompt": prompt, "options": services.get_generator_options()})
