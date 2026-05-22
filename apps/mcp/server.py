import json
import os
from typing import Any, Literal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djass.settings")

import django
from django.apps import apps as django_apps

if not django_apps.ready:
    django.setup()

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from apps.core.generator_options import COOKIECUTTER_FIELD_DEFAULTS
from apps.mcp import services
from apps.mcp.services import MCPServiceError

YNFlag = Literal["y", "n"]
CAPROVER_APP_NAME_DEFAULT = COOKIECUTTER_FIELD_DEFAULTS["caprover_app_name"]

mcp = FastMCP("Djass")


def _tool_error(exc: MCPServiceError) -> ToolError:
    return ToolError(json.dumps(exc.to_dict(), indent=2, sort_keys=True))


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
    use_buttondown: YNFlag,
    use_s3: YNFlag,
    use_stripe: YNFlag,
    use_sentry: YNFlag,
    generate_blog: YNFlag,
    generate_docs: YNFlag,
    use_mjml: YNFlag,
    use_ai: YNFlag,
    use_logfire: YNFlag,
    use_healthchecks: YNFlag,
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
        "use_buttondown": use_buttondown,
        "use_s3": use_s3,
        "use_stripe": use_stripe,
        "use_sentry": use_sentry,
        "generate_blog": generate_blog,
        "generate_docs": generate_docs,
        "use_mjml": use_mjml,
        "use_ai": use_ai,
        "use_logfire": use_logfire,
        "use_healthchecks": use_healthchecks,
        "use_mcp": use_mcp,
        "use_ci": use_ci,
        "use_digitalocean": use_digitalocean,
    }
    if extra_context:
        payload.update(extra_context)
    return payload


@mcp.tool()
def get_generator_options() -> dict[str, Any]:
    """Return the Djass cookiecutter fields, defaults, feature flags, and template path."""

    return services.get_generator_options()


@mcp.tool()
def create_project(
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
    use_buttondown: YNFlag = "y",
    use_s3: YNFlag = "y",
    use_stripe: YNFlag = "y",
    use_sentry: YNFlag = "y",
    generate_blog: YNFlag = "y",
    generate_docs: YNFlag = "y",
    use_mjml: YNFlag = "y",
    use_ai: YNFlag = "y",
    use_logfire: YNFlag = "y",
    use_healthchecks: YNFlag = "y",
    use_mcp: YNFlag = "n",
    use_ci: YNFlag = "y",
    use_digitalocean: YNFlag = "n",
    user_email: str | None = None,
    username: str | None = None,
    create_user: bool = True,
    grant_project_access: bool = True,
    extra_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a Djass Project row and queue background generation through Django Q2."""

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
        use_buttondown=use_buttondown,
        use_s3=use_s3,
        use_stripe=use_stripe,
        use_sentry=use_sentry,
        generate_blog=generate_blog,
        generate_docs=generate_docs,
        use_mjml=use_mjml,
        use_ai=use_ai,
        use_logfire=use_logfire,
        use_healthchecks=use_healthchecks,
        use_mcp=use_mcp,
        use_ci=use_ci,
        use_digitalocean=use_digitalocean,
        extra_context=extra_context,
    )
    try:
        return services.queue_project_generation(
            payload,
            user_email=user_email,
            username=username,
            create_user=create_user,
            grant_project_access=grant_project_access,
            extra_context=extra_context,
        )
    except MCPServiceError as exc:
        raise _tool_error(exc) from exc


@mcp.tool()
def generate_project(
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
    use_buttondown: YNFlag = "y",
    use_s3: YNFlag = "y",
    use_stripe: YNFlag = "y",
    use_sentry: YNFlag = "y",
    generate_blog: YNFlag = "y",
    generate_docs: YNFlag = "y",
    use_mjml: YNFlag = "y",
    use_ai: YNFlag = "y",
    use_logfire: YNFlag = "y",
    use_healthchecks: YNFlag = "y",
    use_mcp: YNFlag = "n",
    use_ci: YNFlag = "y",
    use_digitalocean: YNFlag = "n",
    user_email: str | None = None,
    username: str | None = None,
    create_user: bool = True,
    grant_project_access: bool = True,
    extra_context: dict[str, Any] | None = None,
    output_dir: str | None = None,
    extract: bool = True,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Create a Djass project, run Cookiecutter synchronously, and optionally export the zip."""

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
        use_buttondown=use_buttondown,
        use_s3=use_s3,
        use_stripe=use_stripe,
        use_sentry=use_sentry,
        generate_blog=generate_blog,
        generate_docs=generate_docs,
        use_mjml=use_mjml,
        use_ai=use_ai,
        use_logfire=use_logfire,
        use_healthchecks=use_healthchecks,
        use_mcp=use_mcp,
        use_ci=use_ci,
        use_digitalocean=use_digitalocean,
        extra_context=extra_context,
    )
    try:
        return services.generate_project_now(
            payload,
            user_email=user_email,
            username=username,
            create_user=create_user,
            grant_project_access=grant_project_access,
            extra_context=extra_context,
            output_dir=output_dir,
            extract=extract,
            overwrite=overwrite,
        )
    except MCPServiceError as exc:
        raise _tool_error(exc) from exc


@mcp.tool()
def get_project(project_id: int, user_email: str | None = None) -> dict[str, Any]:
    """Fetch one Djass project by id, optionally scoped to a user email."""

    try:
        return services.get_project(project_id, user_email=user_email)
    except MCPServiceError as exc:
        raise _tool_error(exc) from exc


@mcp.tool()
def list_projects(
    user_email: str | None = None,
    status: Literal["queued", "generating", "ready", "failed"] | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """List Djass projects, optionally scoped by user email and status."""

    try:
        return services.list_projects(
            user_email=user_email,
            status=status,
            limit=limit,
            offset=offset,
        )
    except MCPServiceError as exc:
        raise _tool_error(exc) from exc


@mcp.tool()
def export_project_artifact(
    project_id: int,
    output_dir: str,
    user_email: str | None = None,
    extract: bool = True,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Write a ready project artifact zip to disk and optionally extract it."""

    try:
        return services.export_project_artifact(
            project_id,
            output_dir=output_dir,
            user_email=user_email,
            extract=extract,
            overwrite=overwrite,
        )
    except MCPServiceError as exc:
        raise _tool_error(exc) from exc


@mcp.resource("djass://generator/options")
def generator_options_resource() -> str:
    """JSON description of supported Djass generator inputs."""

    return json.dumps(services.get_generator_options(), indent=2, sort_keys=True)


@mcp.resource("djass://projects/{project_id}")
def project_resource(project_id: str) -> str:
    """JSON representation of one Djass project."""

    try:
        return json.dumps(
            services.get_project(
                int(project_id),
                user_email=services.default_mcp_user_email(),
            ),
            indent=2,
            sort_keys=True,
        )
    except MCPServiceError as exc:
        raise _tool_error(exc) from exc


@mcp.resource("djass://projects/{project_id}/artifact.zip", mime_type="application/zip")
def project_artifact_resource(project_id: str) -> bytes:
    """Binary zip artifact for a ready Djass project."""

    try:
        return services.read_project_artifact_bytes(
            int(project_id),
            user_email=services.default_mcp_user_email(),
        )
    except MCPServiceError as exc:
        raise _tool_error(exc) from exc


@mcp.prompt()
def generate_djass_project_prompt(app_idea: str) -> str:
    """Prompt an agent to transform an app idea into a Djass generation call."""

    return (
        "Create a concise Djass project generation payload for this app idea, then call "
        "`generate_project` with an explicit `project_name`, Python-safe `project_slug`, "
        "short `project_description`, repository URL if known, author fields if known, and "
        "only the feature flags that should differ from their defaults.\n\n"
        f"App idea:\n{app_idea}"
    )


def main() -> None:
    transport = os.environ.get("DJASS_MCP_TRANSPORT", "stdio")
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
