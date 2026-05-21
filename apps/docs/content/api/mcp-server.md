---
title: MCP Server
description: Local Model Context Protocol server for agent-driven Djass project generation.
keywords: Djass, MCP, Model Context Protocol, AI agents, project generation
author: Rasul
---

# Djass MCP Server

Djass ships a local MCP server that exposes the project generator directly to AI
agents. It uses the same Django models and Cookiecutter generation task as the
web app and Projects API.

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
  feature flags, and the active template path.
- `create_project` creates a `Project` row and queues background generation
  through Django Q2.
- `generate_project` creates a `Project`, runs generation synchronously, and
  can export/extract the artifact to a local directory.
- `get_project` fetches one project by id.
- `list_projects` lists projects, optionally scoped by user email and status.
- `export_project_artifact` writes a ready artifact zip to disk and optionally
  extracts it.

## Resources

- `djass://generator/options`
- `djass://projects/{project_id}`
- `djass://projects/{project_id}/artifact.zip`

## Automation identity

If `user_email` is omitted in tool calls, the MCP service uses
`DJASS_MCP_USER_EMAIL`, falling back to `djass-agent@example.local`. Missing MCP
users are created with an unusable password and granted project generation
access so local agents can operate without a manual signup flow.

## Synchronous generation

For fully automated repo creation, prefer `generate_project` with `output_dir`.
The tool persists the Djass `Project` and `ProjectArtifact`, then writes
`<project_slug>.zip` under `output_dir`. With `extract=true`, it extracts the
repository into `output_dir/<project_slug>/`.

Set `overwrite=true` only when replacing an existing generated zip or extract
directory is intentional.

`use_mcp` is available as a normal `"y"|"n"` generator flag on `create_project`
and `generate_project`. It controls whether the generated repository includes
MCP scaffolding; it does not control whether the Djass MCP server itself is used.
