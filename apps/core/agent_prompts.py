from textwrap import dedent

DJASS_API_BASE_URL = "https://djass.dev/api/v1"


def build_djass_agent_skill_md() -> str:
    return dedent(
        """\
        ---
        name: djass-project-generator
        description: >
          Generate Djass project repositories through the Djass Projects API, poll
          generation status, and download ZIP artifacts. Use when a user asks to
          create a new Djass/django-saas-starter project, retrieve generated repo
          ZIPs, or automate Djass project setup.
        ---

        # Djass Project Generator

        ## Runtime Inputs

        Expect these values from the user, environment, or calling prompt:

        - `DJASS_BASE_URL`: base API URL ending in `/api/v1`, for example
          `__DJASS_API_BASE_URL__`.
        - `DJASS_API_KEY`: Djass API key. Treat it as a secret. Prefer the
          `X-API-Key` header.

        ## API Authentication

        Send one of:

        - `X-API-Key: <DJASS_API_KEY>`
        - `Authorization: Bearer <DJASS_API_KEY>`

        A key needs `projects:create` to create projects and `projects:read` to list,
        inspect, poll, or download project artifacts.

        ## API Workflow

        1. Discover current generator options:
           `GET {DJASS_BASE_URL}/project-options`

           This endpoint is public and returns:
           - `defaults`: every supported cookiecutter field and default value.
           - `groups`: feature flag options grouped for UI, API, and MCP clients.

        2. Create a project:
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

        3. Poll generation:
           `GET {DJASS_BASE_URL}/projects/{project_id}/status`

           Poll until `status` is `ready` or `failed`.
           Recommended cadence: start at 2 seconds, back off to at most 15 seconds.

        4. Download the generated repo ZIP:
           `GET {DJASS_BASE_URL}/projects/{project_id}/download`

           Save the response body as a `.zip` file. If the response is
           `409 artifact_not_ready`, keep polling `/status`.

        5. Unpack and inspect:
           - unzip the artifact into the workspace,
           - inspect `djass-manifest.json`,
           - inspect `project-metadata.json`,
           - then run the generated repo's own setup instructions.

        ## Status Model

        Project statuses are:

        - `queued`
        - `generating`
        - `ready`
        - `failed`

        `artifact_ready: true` means the ZIP download endpoint should be available.

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

        ## MCP Guidance

        If Djass MCP tools are available in your tool list, prefer them over raw HTTP.
        Expected Djass MCP capabilities should mirror the HTTP API:

        - get project options with the same `defaults` and `groups` shape as `GET /project-options`,
        - create a project with the same payload as `POST /projects`,
        - list/get/poll projects with the same project and status objects,
        - download the project artifact when ready.

        If no Djass MCP tools are available, do not invent tool calls. Use the HTTP API above.

        The generator option `use_mcp` controls whether the generated project includes
        Model Context Protocol support for agent workflows. Set `use_mcp` to `"y"` only
        when the resulting repository should include MCP server/tooling scaffolding.

        ## Minimal curl Flow

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
            "project_description": "Internal CRM for support and sales",
            "repo_url": "https://github.com/acme/acme-crm",
            "author_name": "Acme",
            "author_email": "team@acme.test",
            "author_url": "https://acme.test",
            "project_main_color": "green",
            "use_posthog": "y",
            "use_chatwoot": "n",
            "use_buttondown": "y",
            "use_s3": "y",
            "use_stripe": "y",
            "use_sentry": "y",
            "generate_blog": "y",
            "generate_docs": "y",
            "use_mjml": "y",
            "use_ai": "y",
            "use_logfire": "y",
            "use_healthchecks": "y",
            "use_mcp": "y",
            "use_ci": "y"
          }'

        PROJECT_ID="123"
        curl -sS "$DJASS_BASE_URL/projects/$PROJECT_ID/status" \\
          -H "X-API-Key: $DJASS_API_KEY"

        curl -L "$DJASS_BASE_URL/projects/$PROJECT_ID/download" \\
          -H "X-API-Key: $DJASS_API_KEY" \\
          -o "acme_crm.zip"
        ```
        """
    ).strip().replace("__DJASS_API_BASE_URL__", DJASS_API_BASE_URL)


def build_djass_agent_prompt(base_url: str, api_key: str, *, skill_url: str) -> str:
    prompt = dedent(
        """\
        Use Djass to generate a new django-saas-starter repo, wait for the ZIP artifact,
        download it, unzip it into the workspace, and continue from the generated repo.

        Read the Djass skill instructions first:
        __DJASS_SKILL_URL__

        Runtime:

        ```bash
        export DJASS_BASE_URL="__DJASS_BASE_URL__"
        export DJASS_API_KEY="__DJASS_API_KEY__"
        ```

        Treat `DJASS_API_KEY` as a secret.

        Use the skill workflow: fetch project options, ask only for missing
        product-specific values, create the project, poll status, download the artifact,
        inspect `djass-manifest.json` and `project-metadata.json`, then follow the
        generated repo's setup instructions. Prefer Djass MCP tools when available;
        otherwise use the HTTP API.
        """
    ).strip()
    return (
        prompt.replace("__DJASS_BASE_URL__", base_url)
        .replace("__DJASS_API_KEY__", api_key)
        .replace("__DJASS_SKILL_URL__", skill_url)
    )
