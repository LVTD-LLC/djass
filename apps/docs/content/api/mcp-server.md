---
title: MCP Server
description: Model Context Protocol server for agent-driven Djass project generation.
keywords: Djass, MCP, Model Context Protocol, AI agents, project generation
author: Rasul
---

# Djass MCP Server

Djass ships an MCP server that exposes the project generator directly to AI
agents. It uses the same Django models and queued Cookiecutter generation task
as the web app and Projects API.

Hosted Djass also exposes an authenticated FastMCP Streamable HTTP endpoint at
`/mcp`. Use a Djass API key in the `Authorization: Bearer <key>` header.

## Hosted endpoint

- Endpoint: `https://djass.dev/mcp`
- Setup prompt: `https://djass.dev/mcp/prompt`
- ZIP download route: `https://djass.dev/mcp/projects/{project_id}/download`

Remote agents should call `get_generator_options`, then `create_project`, poll
`get_project_status`, and finally call `get_project_download`. The download
response includes a URL plus the checksum; fetch that URL with the same API-key
header.

For a copy-ready setup prompt, see
[Generate a Project With an AI Agent](/docs/workflows/generate-project-with-ai-agent/).

### Codex setup

Djass hosted MCP is authenticated. Adding only the URL lets Codex reach the
server, but it does not send a Djass API key, so the MCP initialization request
is rejected with `401 invalid_token`.

1. Create a Djass API key with `projects:create` and `projects:read`.
   Expected outcome: you have a key that can create projects and read generated
   project artifacts.

2. Save the key in your shell environment:

   ```bash
   export DJASS_API_KEY="..."
   ```

   Expected outcome: `DJASS_API_KEY` is available to Codex as a secret
   environment variable.

3. Add the hosted Djass MCP server to Codex:

   ```bash
   codex mcp add djass --url https://djass.dev/mcp --bearer-token-env-var DJASS_API_KEY
   ```

   Expected outcome: Codex stores a `djass` MCP server that sends
   `Authorization: Bearer <DJASS_API_KEY>` to the hosted endpoint.

4. Verify the server configuration:

   ```bash
   codex mcp list
   ```

   Expected outcome: `djass` appears in the configured MCP server list.

5. Restart Codex after updating the environment.
   Expected outcome: the configured MCP server can read `DJASS_API_KEY`, and MCP
   initialization no longer fails with `401 invalid_token`.

## Hosted tools

- `get_generator_options` returns supported Cookiecutter fields, defaults,
  grouped feature flags with labels and descriptions, and the active template path.
- `create_project` queues a project generation job for the authenticated Djass user.
- `list_projects` lists projects for the authenticated Djass user.
- `get_project_status` fetches one project and includes download metadata when
  the artifact is ready.
- `get_project_download` returns the authenticated ZIP download URL and checksum
  for a ready project.

## Local development

Use local stdio only when you are developing Djass itself or intentionally need
the MCP server and agent to share a filesystem.

From the repository root:

```bash
uv run python -m apps.mcp.server
```

Installed environments can also use:

```bash
djass-mcp
```

The default transport is `stdio`, which is the normal mode for local MCP
clients. Set `DJASS_MCP_TRANSPORT=streamable-http` only when you intentionally
want the SDK HTTP transport for a separate local MCP process. Hosted Djass uses
FastMCP's Streamable HTTP ASGI app mounted at `/mcp`, with Django-owned prompt
and ZIP download endpoints beside it.

## Local client configuration example

```json
{
  "mcpServers": {
    "djass": {
      "command": "uv",
      "args": ["run", "python", "-m", "apps.mcp.server"],
      "env": {
        "DJANGO_SETTINGS_MODULE": "djass.settings",
        "DJASS_MCP_USER_EMAIL": "agent@example.local"
      }
    }
  }
}
```

## Local stdio tools

- `get_generator_options` returns supported Cookiecutter fields, defaults,
  grouped feature flags with labels and descriptions, and the active template path.
- `create_project` creates a `Project` row and queues background generation
  through Django Q2.
- `get_project` fetches one project by id.
- `list_projects` lists projects, optionally scoped by user email and status.
- `export_project_artifact` writes a ready artifact zip to the MCP server
  filesystem and optionally extracts it. Use this only when the MCP server and
  agent share a filesystem, such as local stdio MCP.

## Resources

- `djass://generator/options`
- `djass://projects/{project_id}`
- `djass://projects/{project_id}/artifact.zip`

## Automation identity

If `user_email` is omitted in tool calls, the MCP service uses
`DJASS_MCP_USER_EMAIL`, falling back to `djass-agent@example.local`. Missing MCP
users are created with an unusable password and granted project generation
access so local agents can operate without a manual signup flow.

## Queued generation and artifacts

Agents should call `get_generator_options` first, then ask the user which
optional feature flags and generator options they need and will use. Do not
infer services such as analytics, payments, storage, support chat, keyboard
shortcuts, CI, or MCP scaffolding from a vague app idea. If the user asks for
Djass defaults, treat that as explicit confirmation.

Use `create_project` to create a queued generation job, then poll
`get_project_status` until the status is `ready` or `failed`.

When `artifact_ready` is true, retrieve the generated repository ZIP from the
download URL returned by `get_project_download`. Hosted MCP servers cannot write
into the agent's local workspace, so the MCP client should save and unzip the
artifact on the client side.

For local stdio MCP servers that share a filesystem with the agent, agents can
call `export_project_artifact` with `extract=true` to write and unpack the ZIP.
Set `overwrite=true` only when replacing an existing generated zip or extract
directory is intentional.

`use_apprise` and `use_mcp` are available as normal `"y"|"n"` generator flags on
`create_project`. `use_apprise` controls the generated admin notification helper
and docs; `use_mcp` controls whether the generated repository includes MCP
scaffolding and does not control whether the hosted Djass MCP server itself is
used.
