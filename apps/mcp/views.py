import json
from typing import Any

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.http import FileResponse, Http404, HttpRequest, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django_q.tasks import async_task
from pydantic import ValidationError as PydanticValidationError

from apps.api.audit import log_project_api_action
from apps.api.auth import APIAuthPrincipal, header_or_query_api_key_auth
from apps.api.models import ProjectAPIAuditLog
from apps.api.schemas import ProjectCreateIn
from apps.core.generator_options import COOKIECUTTER_FIELD_DEFAULTS, MODULE_FLAG_KEYS
from apps.core.models import Project, ProjectStatus
from apps.core.project_limits import project_create_quota
from djass.utils import get_djass_logger

logger = get_djass_logger(__name__)

MCP_PROTOCOL_VERSION = "2025-06-18"


def _json_dumps(value: Any) -> str:
    return json.dumps(value, cls=DjangoJSONEncoder, indent=2)


def _mcp_result(request_id: Any, result: dict[str, Any]) -> JsonResponse:
    return JsonResponse(
        {"jsonrpc": "2.0", "id": request_id, "result": result}, encoder=DjangoJSONEncoder
    )


def _mcp_error(
    request_id: Any,
    code: int,
    message: str,
    data: dict[str, Any] | None = None,
    status: int = 200,
):
    payload: dict[str, Any] = {"code": code, "message": message}
    if data:
        payload["data"] = data
    return JsonResponse({"jsonrpc": "2.0", "id": request_id, "error": payload}, status=status)


def _tool_text(payload: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": _json_dumps(payload)}]}


def _principal(request: HttpRequest) -> APIAuthPrincipal | None:
    return header_or_query_api_key_auth.authenticate(request)


def _scope_error(principal: APIAuthPrincipal, scope: str) -> dict[str, Any] | None:
    if principal.has_scope(scope):
        return None
    return {
        "code": "insufficient_scope",
        "message": f"API key is missing required scope: {scope}",
        "required_scope": scope,
    }


def _serialize_project(project: Project) -> dict[str, Any]:
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


def _download_url(request: HttpRequest, project: Project) -> str:
    return request.build_absolute_uri(reverse("mcp_project_download", args=[project.id]))


def _download_payload(request: HttpRequest, project: Project) -> dict[str, Any]:
    artifact = project.artifact
    return {
        "project_id": project.id,
        "status": project.status,
        "artifact_ready": True,
        "download_url": _download_url(request, project),
        "auth": (
            "Send Authorization: Bearer <Djass API key> or X-API-Key with the download "
            "request. Do not put API keys in public logs or committed files."
        ),
        "filename": (
            f"{project.slug or slugify(project.name) or 'project'}-"
            f"{timezone.now().strftime('%Y%m%d')}.zip"
        ),
        "size_bytes": artifact.size_bytes,
        "sha256": artifact.sha256,
    }


def _generation_options_payload() -> dict[str, Any]:
    return {
        "template_path": str(settings.COOKIECUTTER_TEMPLATE_PATH),
        "defaults": dict(COOKIECUTTER_FIELD_DEFAULTS),
        "module_flags": list(MODULE_FLAG_KEYS),
        "schema": ProjectCreateIn.model_json_schema(),
        "recommended_flow": [
            "Call djass_generation_options first so your prompt stays current.",
            "Ask the user for every required field and every y/n option not specified.",
            "Only call djass_create_project after intent and options are clear.",
            "Poll djass_get_project_status until ready, then call djass_get_project_download.",
        ],
    }


def _project_payload(
    arguments: dict[str, Any], principal: APIAuthPrincipal
) -> tuple[dict, dict | None]:
    try:
        data = ProjectCreateIn.model_validate(arguments)
    except PydanticValidationError as exc:
        return {}, {"code": "validation_error", "violations": exc.errors()}

    payload = data.model_dump()
    payload.update(getattr(data, "__pydantic_extra__", None) or {})
    if not payload.get("author_email"):
        payload["author_email"] = principal.profile.user.email or ""
    if not payload.get("caprover_app_name"):
        payload["caprover_app_name"] = COOKIECUTTER_FIELD_DEFAULTS["caprover_app_name"]

    unknown = sorted(set(payload) - set(COOKIECUTTER_FIELD_DEFAULTS))
    invalid_flags = sorted(
        key for key in MODULE_FLAG_KEYS if key in payload and payload[key] not in {"y", "n"}
    )
    if unknown or invalid_flags:
        return {}, {
            "code": "invalid_generator_option",
            "message": "Request includes unknown or invalid generator options.",
            "unknown": unknown,
            "invalid_flags": invalid_flags,
        }

    for key, default_value in COOKIECUTTER_FIELD_DEFAULTS.items():
        payload.setdefault(key, default_value)
    return payload, None


def _create_project(request: HttpRequest, principal: APIAuthPrincipal, arguments: dict[str, Any]):
    scope_error = _scope_error(principal, "projects:create")
    if scope_error:
        log_project_api_action(
            request,
            action=ProjectAPIAuditLog.ACTION_CREATE,
            status_code=403,
            principal=principal,
            metadata={"transport": "mcp", **scope_error},
        )
        return {"error": scope_error}, 403

    payload, payload_error = _project_payload(arguments, principal)
    if payload_error:
        log_project_api_action(
            request,
            action=ProjectAPIAuditLog.ACTION_CREATE,
            status_code=400,
            principal=principal,
            metadata={"transport": "mcp", **payload_error},
        )
        return {"error": payload_error}, 400

    normalized_slug = slugify(payload["project_slug"]).replace("-", "_")
    if not normalized_slug:
        return {
            "error": {
                "code": "invalid_project_slug",
                "message": "project_slug must contain letters or numbers.",
            }
        }, 400

    project_quota = project_create_quota()
    user_project_count = Project.objects.filter(user=principal.profile.user).count()
    if user_project_count >= project_quota:
        return {
            "error": {
                "code": "quota_exceeded",
                "message": "Project quota exceeded for this API identity.",
                "quota": project_quota,
            }
        }, 429

    try:
        project = Project.objects.create(
            user=principal.profile.user,
            name=payload["project_name"],
            slug=normalized_slug[:255],
            input_payload=payload,
            status=ProjectStatus.QUEUED,
        )
        async_task(
            "apps.core.tasks.generate_project_artifact",
            project_id=project.id,
            group="Generate Project",
        )
    except Exception as exc:
        logger.error(
            "MCP project creation failed", error=str(exc), user_id=principal.profile.user_id
        )
        return {
            "error": {"code": "internal_error", "message": "Internal error while creating project."}
        }, 500

    log_project_api_action(
        request,
        action=ProjectAPIAuditLog.ACTION_CREATE,
        status_code=201,
        principal=principal,
        project=project,
        metadata={"transport": "mcp"},
    )
    return {"project": _serialize_project(project)}, 201


def _list_projects(request: HttpRequest, principal: APIAuthPrincipal, arguments: dict[str, Any]):
    scope_error = _scope_error(principal, "projects:read")
    if scope_error:
        return {"error": scope_error}, 403

    limit = max(1, min(int(arguments.get("limit", 20)), 100))
    offset = max(0, int(arguments.get("offset", 0)))
    queryset = Project.objects.filter(user=principal.profile.user).prefetch_related("artifact")
    total = queryset.count()
    projects = [_serialize_project(project) for project in queryset[offset : offset + limit]]
    log_project_api_action(
        request,
        action=ProjectAPIAuditLog.ACTION_LIST,
        status_code=200,
        principal=principal,
        metadata={"transport": "mcp", "count": len(projects), "total": total},
    )
    return {"projects": projects, "total": total, "limit": limit, "offset": offset}, 200


def _get_project_status(
    request: HttpRequest, principal: APIAuthPrincipal, arguments: dict[str, Any]
):
    scope_error = _scope_error(principal, "projects:read")
    if scope_error:
        return {"error": scope_error}, 403

    project_id = arguments.get("project_id")
    try:
        project = Project.objects.prefetch_related("artifact").get(
            id=project_id, user=principal.profile.user
        )
    except Project.DoesNotExist:
        return {"error": {"code": "project_not_found", "message": "Project not found."}}, 404

    payload = _serialize_project(project)
    if project.status == ProjectStatus.READY and hasattr(project, "artifact"):
        payload["download"] = _download_payload(request, project)
    return payload, 200


def _get_project_download(
    request: HttpRequest, principal: APIAuthPrincipal, arguments: dict[str, Any]
):
    scope_error = _scope_error(principal, "projects:read")
    if scope_error:
        return {"error": scope_error}, 403

    project_id = arguments.get("project_id")
    try:
        project = Project.objects.select_related("artifact").get(
            id=project_id, user=principal.profile.user
        )
    except Project.DoesNotExist:
        return {"error": {"code": "project_not_found", "message": "Project not found."}}, 404

    if project.status != ProjectStatus.READY or not hasattr(project, "artifact"):
        return {
            "error": {
                "code": "artifact_not_ready",
                "message": (
                    "Generated project ZIP is not ready yet. Call djass_get_project_status "
                    "and retry after status is ready."
                ),
                "status": project.status,
            }
        }, 409

    log_project_api_action(
        request,
        action=ProjectAPIAuditLog.ACTION_DOWNLOAD,
        status_code=200,
        principal=principal,
        project=project,
        metadata={"transport": "mcp"},
    )
    return {"download": _download_payload(request, project)}, 200


def _tools() -> list[dict[str, Any]]:
    return [
        {
            "name": "djass_generation_options",
            "description": (
                "Return the latest Djass project-generation schema, defaults, feature flags, "
                "and recommended agent workflow."
            ),
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "name": "djass_create_project",
            "description": "Queue a Django SaaS project generation job for the authenticated user.",
            "inputSchema": ProjectCreateIn.model_json_schema(),
        },
        {
            "name": "djass_list_projects",
            "description": "List projects generated by the authenticated Djass user.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
                    "offset": {"type": "integer", "minimum": 0, "default": 0},
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "djass_get_project_status",
            "description": (
                "Check queued/generating/ready/failed status for one generated project. "
                "When ready, the response includes ZIP download details."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {"project_id": {"type": "integer"}},
                "required": ["project_id"],
                "additionalProperties": False,
            },
        },
        {
            "name": "djass_get_project_download",
            "description": (
                "Return the authenticated download URL and checksum for a ready generated "
                "project ZIP. Use this after djass_get_project_status reports ready."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {"project_id": {"type": "integer"}},
                "required": ["project_id"],
                "additionalProperties": False,
            },
        },
    ]


def _call_tool(request: HttpRequest, request_id: Any, params: dict[str, Any]):
    name = params.get("name")
    arguments = params.get("arguments") or {}

    if name == "djass_generation_options":
        return _mcp_result(request_id, _tool_text(_generation_options_payload()))

    principal = _principal(request)
    if not principal:
        return _mcp_error(
            request_id,
            -32001,
            (
                "Authentication required. Provide a Djass API key via Authorization: "
                "Bearer <key>, X-API-Key, or ?api_key=."
            ),
            status=401,
        )

    if name == "djass_create_project":
        payload, status_code = _create_project(request, principal, arguments)
    elif name == "djass_list_projects":
        payload, status_code = _list_projects(request, principal, arguments)
    elif name == "djass_get_project_status":
        payload, status_code = _get_project_status(request, principal, arguments)
    elif name == "djass_get_project_download":
        payload, status_code = _get_project_download(request, principal, arguments)
    else:
        return _mcp_error(request_id, -32602, f"Unknown tool: {name}")

    if "error" in payload:
        return _mcp_error(
            request_id,
            -32000,
            payload["error"].get("message", "Tool call failed."),
            payload["error"],
            status=status_code,
        )
    return _mcp_result(request_id, _tool_text(payload))


@csrf_exempt
@require_http_methods(["GET", "POST"])
def mcp_endpoint(request: HttpRequest):
    if request.method == "GET":
        return JsonResponse(
            {
                "name": "Djass MCP Server",
                "protocol": "mcp",
                "protocol_version": MCP_PROTOCOL_VERSION,
                "endpoint": request.build_absolute_uri(request.path),
                "auth": "Authorization: Bearer <Djass API key>, X-API-Key, or ?api_key=",
                "tools": [tool["name"] for tool in _tools()],
                "setup_prompt_url": request.build_absolute_uri("/mcp/prompt"),
            }
        )

    try:
        message = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return _mcp_error(None, -32700, "Parse error", status=400)

    request_id = message.get("id")
    method = message.get("method")
    params = message.get("params") or {}

    if method == "initialize":
        return _mcp_result(
            request_id,
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "djass", "version": "1.0.0"},
            },
        )
    if method == "notifications/initialized":
        return JsonResponse({}, status=202)
    if method == "tools/list":
        return _mcp_result(request_id, {"tools": _tools()})
    if method == "tools/call":
        return _call_tool(request, request_id, params)

    return _mcp_error(request_id, -32601, f"Method not found: {method}")


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
        metadata={"transport": "mcp", "direct_download": True},
    )
    return FileResponse(artifact.zip_file, as_attachment=True, filename=filename)


@require_http_methods(["GET"])
def mcp_prompt(request: HttpRequest):
    base_url = request.build_absolute_uri("/").rstrip("/")
    mcp_url = request.build_absolute_uri("/mcp")
    options_url = request.build_absolute_uri("/api/v1/project-options")
    prompt = "\n".join(
        [
            "Use Djass to generate Django SaaS projects for this user.",
            "",
            "Connection:",
            f"- Djass site: {base_url}",
            f"- MCP endpoint: {mcp_url}",
            "- Auth: ask the user for their Djass API key and send it as "
            "Authorization: Bearer <key> or X-API-Key. Never print or commit the key.",
            "",
            "Workflow:",
            "1. Connect to the Djass MCP server.",
            "2. Always call djass_generation_options before creating a project. "
            f"If MCP is unavailable, fetch {options_url}.",
            "3. Ask concise follow-up questions for every required field and every "
            "current option the user did not specify.",
            "4. If the user explicitly says to decide for them, choose sensible "
            "defaults, summarize those choices, then continue.",
            "5. Only call djass_create_project after the intent and options are clear.",
            "6. Poll djass_get_project_status until status is ready or failed.",
            "7. When ready, call djass_get_project_download and download the ZIP from "
            "the returned URL using the same Authorization header.",
        ]
    )
    return JsonResponse(
        {"prompt": prompt, "options": _generation_options_payload()}, encoder=DjangoJSONEncoder
    )
