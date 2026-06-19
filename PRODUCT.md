# PRODUCT.md

Product context for AI agents working on Djass.

## Product

Djass helps users generate agent-ready Django SaaS repositories from `django-saas-starter`. The product is a managed hosted app, not a self-hosted open-source deployment product.

Primary user jobs:

- Create a new Django SaaS starter by choosing project metadata and optional modules.
- Generate the same project through UI, API, or MCP workflows.
- Poll build status and download a ZIP artifact when generation is ready.
- Hand an AI agent a Djass prompt or MCP setup so the agent can create projects without manual UI steps.

## Core Workflows

Project generation:

1. User submits generator options through `ProjectCreateForm`, `/api/v1/projects`, or Djass MCP.
2. Djass validates the payload against the generator catalog.
3. Djass creates a `Project` row with `status=queued`.
4. Django Q2 runs `apps.core.tasks.generate_project_artifact`.
5. Cookiecutter renders `django-saas-starter`.
6. Djass writes `project-metadata.json` and `djass-manifest.json`, zips the generated repo, stores `ProjectArtifact`, and marks the project `ready`.
7. Users download artifacts from the dashboard, API, or MCP download flow.

Access and monetization:

- `PAYMENTS_ENABLED` gates project generation through `Profile.has_active_subscription`.
- Current product copy presents a one-time payment / launch price flow.
- API and MCP generation must respect the same entitlement and quota assumptions as the UI.

Agent workflow:

- Hosted MCP is preferred for remote agents at `https://djass.dev/mcp`.
- HTTP API fallback uses `https://djass.dev/api/v1`.
- Agent prompts are generated in `apps/core/agent_prompts.py`; public skill endpoints must never embed user-specific secrets.

## In Scope

- Managed Djass app features.
- Generator option catalog, validation, docs, and tests.
- Project artifact creation, metadata, manifest, checksums, and downloads.
- API key authentication, scoped project API keys, audit logging, and MCP access.
- Product docs under `apps/docs/content`.

## Out of Scope

- Official self-hosting support for Djass itself.
- Public deployment guides for running Djass as an open-source app.
- Replacing the generated repository template without a deliberate product decision.
- Adding a separate SPA frontend architecture.

## Product Constraints

- UI, API, and MCP must expose consistent generator defaults and feature flags.
- Do not infer optional generated modules for users. The product asks users or agents to choose flags such as analytics, payments, storage, support chat, AI, MCP scaffolding, CI, and deployment provider support.
- Generation failures should be persisted and actionable through `Project.error_message`.
- Artifact downloads should be scoped to the owner and should include integrity metadata where available.
- Documentation should help users accomplish tasks, not describe implementation internals first.
