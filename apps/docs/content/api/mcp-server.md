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

## Run locally

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
want the SDK HTTP transport.

## Client configuration example

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

## Tools

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
infer services such as analytics, payments, storage, support chat, CI, or MCP
scaffolding from a vague app idea. If the user asks for Djass defaults, treat
that as explicit confirmation.

Use `create_project` to create a queued generation job, then poll `get_project`
or `list_projects` until the status is `ready` or `failed`.

When `artifact_ready` is true, retrieve the generated repository ZIP from the
`djass://projects/{project_id}/artifact.zip` resource or from the artifact URL
returned by `get_project`. Hosted MCP servers cannot write into the agent's
local workspace, so the MCP client should save and unzip the artifact on the
client side.

For local stdio MCP servers that share a filesystem with the agent, agents can
call `export_project_artifact` with `extract=true` to write and unpack the ZIP.
Set `overwrite=true` only when replacing an existing generated zip or extract
directory is intentional.

`use_apprise` and `use_mcp` are available as normal `"y"|"n"` generator flags on
`create_project`. `use_apprise` controls the generated admin notification helper
and docs; `use_mcp` controls whether the generated repository includes MCP
scaffolding and does not control whether the Djass MCP server itself is used.
