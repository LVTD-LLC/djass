import os
from typing import Any, Literal
from urllib.parse import urlparse

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djass.settings")

import django
from asgiref.sync import sync_to_async
from django.apps import apps as django_apps
from django.conf import settings
from django.utils.text import slugify
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import AnyHttpUrl

if not django_apps.ready:
    django.setup()

from apps.api.auth import _resolve_api_principal
from apps.core.generator_options import COOKIECUTTER_FIELD_DEFAULTS
from apps.core.models import Profile, ProjectStatus
from apps.mcp import services
from apps.mcp.services import MCPServiceError

YNFlag = Literal["y", "n"]
CAPROVER_APP_NAME_DEFAULT = COOKIECUTTER_FIELD_DEFAULTS["caprover_app_name"]


class DjassAPITokenVerifier(TokenVerifier):
    async def verify_token(self, token: str) -> AccessToken | None:
        principal = await sync_to_async(_resolve_api_principal)(token)
        if not principal:
            return None
        return AccessToken(
            token=token,
            client_id=str(principal.profile.user_id),
            scopes=sorted(principal.scopes),
        )


def _site_url() -> str:
    return str(settings.SITE_URL).rstrip("/") or "https://djass.dev"


def _auth_settings() -> AuthSettings:
    site_url = _site_url()
    return AuthSettings(
        issuer_url=AnyHttpUrl(site_url),
        resource_server_url=AnyHttpUrl(f"{site_url}/mcp"),
        required_scopes=[],
    )


def _transport_security_settings() -> TransportSecuritySettings:
    site_url = _site_url()
    parsed_site_url = urlparse(site_url)
    allowed_hosts = {
        "127.0.0.1",
        "127.0.0.1:*",
        "localhost",
        "localhost:*",
        "[::1]",
        "[::1]:*",
    }
    if parsed_site_url.netloc:
        allowed_hosts.add(parsed_site_url.netloc)
    if parsed_site_url.hostname:
        allowed_hosts.add(parsed_site_url.hostname)

    allowed_origins = {
        "http://127.0.0.1",
        "http://127.0.0.1:*",
        "http://localhost",
        "http://localhost:*",
        "http://[::1]",
        "http://[::1]:*",
        site_url,
    }
    return TransportSecuritySettings(
        allowed_hosts=sorted(allowed_hosts),
        allowed_origins=sorted(allowed_origins),
    )


hosted_mcp = FastMCP(
    "Djass",
    instructions=(
        "Generate Django SaaS projects through Djass. Call djass_generation_options first, "
        "then djass_create_project, poll djass_get_project_status, and finally call "
        "djass_get_project_download when the artifact is ready."
    ),
    token_verifier=DjassAPITokenVerifier(),
    auth=_auth_settings(),
    streamable_http_path="/mcp",
    json_response=True,
    stateless_http=True,
    transport_security=_transport_security_settings(),
)


def _tool_error(exc: MCPServiceError) -> ToolError:
    return ToolError(str(exc.to_dict()))


def _profile_from_token(required_scope: str | None = None) -> Profile:
    access_token = get_access_token()
    if access_token is None:
        raise ToolError("Authentication required. Send Authorization: Bearer <Djass API key>.")
    if required_scope and required_scope not in set(access_token.scopes):
        raise ToolError(f"API key is missing required scope: {required_scope}")
    try:
        return Profile.objects.select_related("user").get(user_id=int(access_token.client_id))
    except (TypeError, ValueError, Profile.DoesNotExist) as exc:
        raise ToolError("Authenticated Djass profile was not found.") from exc


def _payload_from_args(
    *,
    project_name: str,
    project_slug: str,
    caprover_app_name: str,
    project_description: str,
    repo_url: str,
    author_name: str,
    author_email: str,
    author_url: str,
    project_main_color: str,
    use_posthog: YNFlag,
    use_chatwoot: YNFlag,
    use_s3: YNFlag,
    use_stripe: YNFlag,
    use_sentry: YNFlag,
    generate_blog: YNFlag,
    generate_docs: YNFlag,
    use_mjml: YNFlag,
    use_keyboard_shortcuts: YNFlag,
    use_ai: YNFlag,
    use_logfire: YNFlag,
    use_healthchecks: YNFlag,
    use_apprise: YNFlag,
    use_mcp: YNFlag,
    use_ci: YNFlag,
    use_digitalocean: YNFlag,
    extra_context: dict[str, Any] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "project_name": project_name,
        "project_slug": project_slug,
        "caprover_app_name": caprover_app_name or CAPROVER_APP_NAME_DEFAULT,
        "project_description": project_description,
        "repo_url": repo_url,
        "author_name": author_name,
        "author_email": author_email,
        "author_url": author_url,
        "project_main_color": project_main_color,
        "use_posthog": use_posthog,
        "use_chatwoot": use_chatwoot,
        "use_s3": use_s3,
        "use_stripe": use_stripe,
        "use_sentry": use_sentry,
        "generate_blog": generate_blog,
        "generate_docs": generate_docs,
        "use_mjml": use_mjml,
        "use_keyboard_shortcuts": use_keyboard_shortcuts,
        "use_ai": use_ai,
        "use_logfire": use_logfire,
        "use_healthchecks": use_healthchecks,
        "use_apprise": use_apprise,
        "use_mcp": use_mcp,
        "use_ci": use_ci,
        "use_digitalocean": use_digitalocean,
    }
    if extra_context:
        payload.update(extra_context)
    return payload


@hosted_mcp.tool(name="djass_generation_options")
def djass_generation_options() -> dict[str, Any]:
    """Return the Djass cookiecutter fields, defaults, feature flags, and template path."""

    options = services.get_generator_options()
    options["recommended_flow"] = [
        "Call djass_generation_options first so your prompt stays current.",
        "Ask the user for every required field and every y/n option not specified.",
        "Only call djass_create_project after intent and options are clear.",
        "Poll djass_get_project_status until ready, then call djass_get_project_download.",
    ]
    return options


@hosted_mcp.tool(name="djass_create_project")
def djass_create_project(
    project_name: str,
    project_slug: str,
    caprover_app_name: str = "",
    project_description: str = "",
    repo_url: str = "",
    author_name: str = "",
    author_email: str = "",
    author_url: str = "",
    project_main_color: str = "green",
    use_posthog: YNFlag = "y",
    use_chatwoot: YNFlag = "n",
    use_s3: YNFlag = "y",
    use_stripe: YNFlag = "y",
    use_sentry: YNFlag = "y",
    generate_blog: YNFlag = "y",
    generate_docs: YNFlag = "y",
    use_mjml: YNFlag = "y",
    use_keyboard_shortcuts: YNFlag = "y",
    use_ai: YNFlag = "y",
    use_logfire: YNFlag = "y",
    use_healthchecks: YNFlag = "y",
    use_apprise: YNFlag = "n",
    use_mcp: YNFlag = "n",
    use_ci: YNFlag = "y",
    use_digitalocean: YNFlag = "n",
    extra_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Queue a Django SaaS project generation job for the authenticated Djass user."""

    profile = _profile_from_token("projects:create")
    payload = _payload_from_args(
        project_name=project_name,
        project_slug=project_slug,
        caprover_app_name=caprover_app_name,
        project_description=project_description,
        repo_url=repo_url,
        author_name=author_name,
        author_email=author_email,
        author_url=author_url,
        project_main_color=project_main_color,
        use_posthog=use_posthog,
        use_chatwoot=use_chatwoot,
        use_s3=use_s3,
        use_stripe=use_stripe,
        use_sentry=use_sentry,
        generate_blog=generate_blog,
        generate_docs=generate_docs,
        use_mjml=use_mjml,
        use_keyboard_shortcuts=use_keyboard_shortcuts,
        use_ai=use_ai,
        use_logfire=use_logfire,
        use_healthchecks=use_healthchecks,
        use_apprise=use_apprise,
        use_mcp=use_mcp,
        use_ci=use_ci,
        use_digitalocean=use_digitalocean,
        extra_context=extra_context,
    )
    try:
        return services.queue_project_generation_for_user(
            payload,
            user=profile.user,
            extra_context=extra_context,
        )
    except MCPServiceError as exc:
        raise _tool_error(exc) from exc


@hosted_mcp.tool(name="djass_list_projects")
def djass_list_projects(
    status: Literal["queued", "generating", "ready", "failed"] | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """List projects generated by the authenticated Djass user."""

    profile = _profile_from_token("projects:read")
    try:
        return services.list_projects(
            user_email=profile.user.email,
            status=status,
            limit=limit,
            offset=offset,
        )
    except MCPServiceError as exc:
        raise _tool_error(exc) from exc


@hosted_mcp.tool(name="djass_get_project_status")
def djass_get_project_status(project_id: int) -> dict[str, Any]:
    """Check queued/generating/ready/failed status for one generated project."""

    profile = _profile_from_token("projects:read")
    try:
        project = services.get_project(project_id, user_email=profile.user.email)
    except MCPServiceError as exc:
        raise _tool_error(exc) from exc
    if project["status"] == ProjectStatus.READY and project.get("artifact_ready"):
        project["download"] = _download_payload(project)
    return project


def _download_payload(project: dict[str, Any]) -> dict[str, Any]:
    safe_slug = project.get("slug") or slugify(project.get("name", "")) or "project"
    base_url = _site_url()
    artifact = project.get("artifact") or {}
    return {
        "project_id": project["id"],
        "download_url": f"{base_url}/mcp/projects/{project['id']}/download",
        "auth": "Send Authorization: Bearer <Djass API key> with the download request.",
        "filename": f"{safe_slug}.zip",
        "size_bytes": artifact.get("size_bytes"),
        "sha256": artifact.get("sha256"),
    }


@hosted_mcp.tool(name="djass_get_project_download")
def djass_get_project_download(project_id: int) -> dict[str, Any]:
    """Return the authenticated download URL and checksum for a ready generated project ZIP."""

    project = djass_get_project_status(project_id)
    if project["status"] != ProjectStatus.READY or not project.get("artifact_ready"):
        raise ToolError("Generated project ZIP is not ready yet. Poll status and retry.")
    return {"download": _download_payload(project)}


@hosted_mcp.prompt(name="generate_djass_project")
def generate_djass_project_prompt(app_idea: str) -> str:
    """Prompt an agent to transform an app idea into a Djass generation call."""

    return (
        "Use the hosted Djass FastMCP server to generate a Django SaaS project. "
        "Call djass_generation_options first, ask concise follow-up questions for missing "
        "required fields/options, then call djass_create_project. Poll "
        "djass_get_project_status until ready. Finally call djass_get_project_download and "
        "download the returned ZIP URL with the same Authorization bearer token.\n\n"
        f"App idea:\n{app_idea}"
    )


application = hosted_mcp.streamable_http_app()
