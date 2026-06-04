---
title: Generate a Project With an AI Agent
description: Configure the Djass MCP server and give your coding agent a safe starter prompt.
keywords: Djass, MCP, AI agent, project generation, prompt
author: Rasul
---

# Generate a Project With an AI Agent

Use this workflow when you want a coding agent to create and export a Djass
project without clicking through the web UI.

The agent will connect to the Djass MCP server, inspect the available generator
options, ask you to confirm important choices, queue the project, and retrieve
the generated ZIP when it is ready.

## 1) Choose hosted or local Djass

Use hosted Djass when you want the agent to create projects through your Djass
account without running the app locally.

- Endpoint: `https://djass.dev/mcp`
- Setup prompt: `https://djass.dev/mcp/prompt`
- Authentication: `Authorization: Bearer <your Djass API key>`

Use local Djass when you are developing Djass itself or need the agent and MCP
server to share a filesystem for artifact export.

## 2) Prepare local Djass

For local development, run the normal stack first:

```bash
make serve
```

This gives Djass the database, Redis, and background worker it needs to process
queued project generation jobs.

Skip this step when you use hosted Djass.

## 3) Configure the MCP server

For hosted Djass, configure your MCP client to use `https://djass.dev/mcp` with
your Djass API key in the `Authorization` header. If your agent supports setup
prompts, open `https://djass.dev/mcp/prompt` and follow the generated client
instructions.

For local Djass, most coding agents that support MCP can use this server
configuration:

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

Add it to the MCP settings file or settings screen your agent uses. Keep the
working directory pointed at the Djass repository root so `uv` can resolve the
project.

## 4) Give your agent this prompt

Copy this prompt into your coding agent and replace the app idea with your own.

```text
You have access to the Djass MCP server named "djass".

Use Djass to generate a new Django SaaS project for this app idea:

[Describe the app, users, core workflow, and any integrations you already know you need.]

First call the generator options tool: use get_generator_options for a local stdio Djass MCP server, or djass_generation_options for hosted Djass. Summarize the project fields, defaults, and optional feature flags I need to decide.

Ask me before enabling optional services such as analytics, payments, storage, support chat, keyboard shortcuts, CI, Apprise, or generated MCP scaffolding. Do not infer those from a vague app idea.

After I confirm the choices, call the Djass project creation tool with an explicit project_name, Python-safe project_slug, short project_description, repository URL if known, author fields if known, and every feature flag as "y" or "n".

Poll the Djass project status tool until the project is ready or failed.

When artifact_ready is true, retrieve the generated ZIP from the artifact resource, artifact URL, or Djass download tool. If you and the MCP server share a local filesystem, ask me before using export_project_artifact with extract=true. Never overwrite an existing export unless I explicitly approve it.
```

## 5) Review the choices before generation

The agent should stop and ask before it enables optional services. Confirm only
the tools the project will actually use.

Use Djass defaults when you want the standard baseline. Be explicit if you want
features such as payments, analytics, generated MCP scaffolding, or background
notification helpers.

## 6) Retrieve the generated project

When generation finishes, the agent should fetch the artifact ZIP.

For hosted or HTTP MCP setups, the agent should save the ZIP on the client side.
For local `stdio` MCP setups where the agent and server share a filesystem, the
agent can export and extract the artifact locally after you approve the target
directory.

## What the agent should not do

- Do not skip `get_generator_options`.
- Do not enable optional integrations without confirmation.
- Do not treat `use_mcp` as the switch for using the Djass MCP server. It only
  controls whether the generated project includes MCP scaffolding.
- Do not overwrite an existing generated project without explicit approval.

## When a plugin makes sense later

This prompt-first workflow is enough for early use. A plugin becomes useful when
you want one-click installation, bundled agent skills, marketplace
discoverability, or consistent setup across Claude Code, Codex, Cursor, Gemini,
and OpenClaw-compatible environments.
