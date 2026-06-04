from textwrap import dedent

DJASS_API_BASE_URL = "https://djass.dev/api/v1"
DJASS_OPENAPI_DOCS_URL = "https://djass.dev/api/docs"
DJASS_MCP_DOCS_URL = "https://djass.dev/docs/api/mcp-server/"


def build_djass_agent_skill_md() -> str:
    skill = dedent(
        """\
        ---
        name: djass-project-generator
        description: >
          Generate Djass project repositories with Djass MCP tools first, then
          fall back to the Djass Projects API only when MCP is unavailable. Use
          when a user asks to create a new Djass/django-saas-starter project,
          retrieve generated repo ZIPs, or automate Djass project setup.
        ---

        # Djass Project Generator

        ## Runtime Inputs

        Prefer a configured Djass MCP server. Expected tool names:

        - `get_generator_options`
        - `create_project`
        - `get_project`
        - `list_projects`
        - `export_project_artifact`

        MCP setup docs: __DJASS_MCP_DOCS_URL__

        For HTTP fallback, expect these values from the user, environment, or
        calling prompt:

        - `DJASS_BASE_URL`: base API URL ending in `/api/v1`, for example
          `__DJASS_API_BASE_URL__`.
        - `DJASS_API_KEY`: Djass API key. Treat it as a secret. Prefer the
          `X-API-Key` header.

        OpenAPI docs: __DJASS_OPENAPI_DOCS_URL__

        ## Preferred MCP Workflow

        If Djass MCP tools are available in your tool list, use them. Do not make
        raw HTTP calls unless MCP is unavailable or a tool fails with clear
        fallback guidance.

        1. Discover current generator options with `get_generator_options`.

           The response includes:
           - `defaults`: every supported cookiecutter field and default value.
           - `groups`: feature flags grouped with labels and descriptions for
             UI, API, and MCP clients.
           - `module_flags`: backwards-compatible flat feature flag names.

        2. Ask the user for missing product-specific values:
           - `project_name`
           - `project_slug`
           - `project_description`
           - `repo_url`
           - author fields, if they matter for the generated repository

        3. Ask the user which optional features and generator options they need
           and will use. Do not silently choose optional services from the app
           idea alone. In particular, ask the user to confirm enabled/disabled
           values for feature flags such as analytics, support chat, storage,
           payments, error monitoring, admin notifications, blog/docs, MJML, AI,
           Logfire, health checks, MCP scaffolding, CI, and deployment provider support.
           If the user says to use Djass defaults, treat that as confirmation.

        4. Call `create_project` with explicit project fields and feature flags
           as `"y"` or `"n"`. Then use `get_project` or `list_projects` until the
           status is `ready` or `failed`.

        5. Retrieve the artifact after `artifact_ready: true`.
           - For hosted MCP servers, do not assume the server can write into the
             agent's local workspace. Read `djass://projects/{project_id}/artifact.zip`
             or use the artifact URL from `get_project`, then save and unzip it
             in the client workspace.
           - Use `export_project_artifact` only when the MCP server shares a
             filesystem with the agent, such as a local stdio MCP server.

        6. Inspect the generated repo:
           - `djass-manifest.json`
           - `project-metadata.json`
           - the generated repo's README/setup instructions

        Project statuses are:

        - `queued`
        - `generating`
        - `ready`
        - `failed`

        `artifact_ready: true` means the ZIP export/download should be available.

        ## MCP Option Guidance

        Djass MCP tools are the preferred control plane for generating a project.
        The generator option `use_mcp` is different: it controls whether the
        generated repository itself includes Model Context Protocol support for
        future agent workflows.

        Set `use_mcp` to `"y"` when the resulting repository should include MCP
        server/tooling scaffolding. Otherwise keep the discovered default only
        after the user confirms they want defaults.

        ## API Fallback Authentication

        Send one of:

        - `X-API-Key: <DJASS_API_KEY>`
        - `Authorization: Bearer <DJASS_API_KEY>`

        A key needs `projects:create` to create projects and `projects:read` to list,
        inspect, poll, or download project artifacts.

        ## API Fallback Workflow

        Use this only when Djass MCP tools are not available.

        1. Discover current generator options:
           `GET {DJASS_BASE_URL}/project-options`

           This endpoint is public and returns:
           - `defaults`: every supported cookiecutter field and default value.
           - `groups`: feature flag options grouped with labels and descriptions
             for UI, API, and MCP clients.

        2. Ask the user which optional feature flags and generator options they
           need and will use. Do not infer optional services from the app idea
           alone. If the user says to use Djass defaults, treat that as
           confirmation.

        3. Create a project:
           `POST {DJASS_BASE_URL}/projects`

           Send JSON with core fields:
           - `project_name`
           - `project_slug`
           - `project_description`
           - `repo_url`
           - `author_name`
           - `author_email`
           - `author_url`
           - `project_main_color`

           Include feature flags discovered from `/project-options` as `"y"` or `"n"`.
           Unknown fields or non-`"y"`/`"n"` feature flag values can fail validation.

        4. Poll generation:
           `GET {DJASS_BASE_URL}/projects/{project_id}/status`

           Poll until `status` is `ready` or `failed`.
           Recommended cadence: start at 2 seconds, back off to at most 15 seconds.

        5. Download the generated repo ZIP:
           `GET {DJASS_BASE_URL}/projects/{project_id}/download`

           Save the response body as a `.zip` file. If the response is
           `409 artifact_not_ready`, keep polling `/status`.

        6. Unpack and inspect:
           - unzip the artifact into the workspace,
           - inspect `djass-manifest.json`,
           - inspect `project-metadata.json`,
           - then run the generated repo's own setup instructions.

        ## Error Handling

        Non-2xx API responses have this shape:

        ```json
        {
          "error": {
            "code": "machine_readable_code",
            "category": "validation|auth|quota|retryable|internal",
            "message": "Human readable summary",
            "retryable": false,
            "details": {}
          }
        }
        ```

        Retry only when `retryable` is true or the failure is a transient
        network/server failure.
        Do not retry validation, auth, subscription, quota, or insufficient-scope errors
        without user input.

        ## Minimal curl Flow

        This is an HTTP fallback example. Prefer MCP tools when available.

        ```bash
        export DJASS_BASE_URL="__DJASS_API_BASE_URL__"
        export DJASS_API_KEY="replace-with-user-key"

        curl -sS "$DJASS_BASE_URL/project-options"

        curl -sS -X POST "$DJASS_BASE_URL/projects" \\
          -H "Content-Type: application/json" \\
          -H "X-API-Key: $DJASS_API_KEY" \\
          --data '{
            "project_name": "Acme CRM",
            "project_slug": "acme_crm",
            "caprover_app_name": "acme-crm",
            "project_description": "Internal CRM for support and sales",
            "repo_url": "https://github.com/acme/acme-crm",
            "author_name": "Acme",
            "author_email": "team@acme.test",
            "author_url": "https://acme.test",
            "project_main_color": "green",
            "use_posthog": "y",
            "use_chatwoot": "n",
            "use_s3": "y",
            "use_stripe": "y",
            "use_sentry": "y",
            "generate_blog": "y",
            "generate_docs": "y",
            "use_mjml": "y",
            "use_keyboard_shortcuts": "y",
            "use_ai": "y",
            "use_logfire": "y",
            "use_healthchecks": "y",
            "use_apprise": "n",
            "use_mcp": "y",
            "use_ci": "y",
            "use_digitalocean": "n"
          }'

        PROJECT_ID="123"
        curl -sS "$DJASS_BASE_URL/projects/$PROJECT_ID/status" \\
          -H "X-API-Key: $DJASS_API_KEY"

        curl -L "$DJASS_BASE_URL/projects/$PROJECT_ID/download" \\
          -H "X-API-Key: $DJASS_API_KEY" \\
          -o "acme_crm.zip"
        ```
        """
    ).strip()
    return (
        skill.replace("__DJASS_API_BASE_URL__", DJASS_API_BASE_URL)
        .replace("__DJASS_OPENAPI_DOCS_URL__", DJASS_OPENAPI_DOCS_URL)
        .replace("__DJASS_MCP_DOCS_URL__", DJASS_MCP_DOCS_URL)
    )


def build_djass_agent_prompt(base_url: str, api_key: str, *, skill_url: str) -> str:
    prompt = dedent(
        """\
        Use Djass to generate a new django-saas-starter repo, wait for the ZIP artifact,
        download it, unzip it into the workspace, and continue from the generated repo.

        Read the plain-text Djass skill instructions first:
        __DJASS_SKILL_URL__

        Preferred path: use Djass MCP tools if they are available in your tool
        list. Call `get_generator_options`, ask the user which optional features
        and generator options they need and will use, then call `create_project`
        with explicit `"y"`/`"n"` feature flags. Poll with `get_project` or
        `list_projects` until the artifact is ready. Use the HTTP API only if
        Djass MCP is unavailable.

        HTTP fallback runtime:

        ```bash
        export DJASS_BASE_URL="__DJASS_BASE_URL__"
        export DJASS_API_KEY="__DJASS_API_KEY__"
        ```

        Treat `DJASS_API_KEY` as a secret.

        Use the skill workflow: fetch project options, ask for missing
        product-specific values, ask the user to confirm optional features and
        generator options, create the queued project, retrieve/download the
        artifact, inspect `djass-manifest.json` and `project-metadata.json`, then
        follow the generated repo's setup instructions.
        """
    ).strip()
    return (
        prompt.replace("__DJASS_BASE_URL__", base_url)
        .replace("__DJASS_API_KEY__", api_key)
        .replace("__DJASS_SKILL_URL__", skill_url)
    )
