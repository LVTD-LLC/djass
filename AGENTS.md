# AGENTS.md

Repo-wide instructions for AI coding agents working on Djass.

## Project Snapshot

Djass is a managed Django SaaS app that generates production-ready Django SaaS repositories from `django-saas-starter`. Users create a project through the UI, API, or MCP server; Djass queues generation with Django Q2, runs Cookiecutter, stores a deterministic ZIP artifact, and exposes the artifact for download.

Canonical context files:

- Product context: `PRODUCT.md`
- Stack and commands: `TECH.md`
- Directory placement rules: `STRUCTURE.md`
- UI design rules: `DESIGN.md`
- Docs-writing rules: `apps/docs/AGENTS.md`

## Local Workflow

Use the executable config as truth. `.python-version` is `3.14.5`; `.nvmrc` is `24.15.0`.

Setup and run the Dockerized local stack:

```bash
cp .env.example .env
make serve
```

Useful local commands:

```bash
make restart-worker
make manage migrate
make manage createsuperuser
make shell
make test
```

Host-side CI-equivalent checks:

```bash
uv sync
npm ci
npm run build
npm run lint
uv run python manage.py check
uv run python manage.py sync_cookiecutter_options --check --skip-on-network-error
uv run pytest -q
```

Additional targeted checks:

```bash
uv run ruff check .
uv run ruff format .
uv run djlint frontend/templates
make test apps/core/tests/test_generator_options.py
make test apps/api/test_spec_001_contract.py
make test apps/mcp/tests.py
```

## Implementation Rules

- Keep the three generation entrypoints aligned: web UI in `apps/core/views.py` and `ProjectCreateForm`, API v1 in `apps/api`, and MCP in `apps/mcp`.
- Treat `apps/core/generator_options.py` as the canonical generator option catalog. When adding, removing, or renaming a generator field, update the form, API schema/contract, MCP tools, docs, and tests in the same change.
- Keep project generation asynchronous. Web/API/MCP paths should create `Project(status=queued)` and enqueue `apps.core.tasks.generate_project_artifact` instead of running Cookiecutter inline.
- Preserve artifact safety and determinism in `apps/core/tasks.py`: normalized payloads, sorted ZIP traversal, fixed ZIP timestamps, SHA-256, size metadata, and persisted failure diagnostics.
- Keep API responses inside the existing error taxonomy in `apps/api/views.py`; project API keys require explicit scopes from `apps/api/models.py`.
- Do not put secrets or user-specific API keys into public prompt endpoints, docs pages, generated skill text, logs, or test fixtures.
- Use structured logging through `djass.utils.get_djass_logger`; avoid ad hoc `print` in application code.
- Use Django forms and server validation as the source of truth for UI submissions. Browser JavaScript may improve ergonomics but must not be the only validation.
- For docs content under `apps/docs/content`, follow `apps/docs/AGENTS.md`: write for users, with clear outcomes and step-by-step actions.

## Frontend Rules

- Django templates are the UI layer. Do not introduce React, Vue, a bundler, or SPA routing unless the product intentionally changes frontend architecture.
- Use HTMX for fresh server-rendered HTML and Alpine.js for local browser state only.
- Reuse `.dj-*` primitives and CSS variables from `frontend/src/styles/index.css` before adding new component CSS.
- Build static assets with `npm run build` after changing `frontend/src/styles`, `frontend/src/js`, vendor-copy scripts, or templates that depend on generated static files.

## Test Expectations

- Model, generation, payment, auth, API, MCP, and docs behavior should have focused pytest coverage.
- Generator option changes need at least:
  - `apps/core/tests/test_generator_options.py`
  - `apps/api/test_spec_001_contract.py`
  - `apps/mcp/tests.py`
  - relevant docs updates under `apps/docs/content`
- UI/template changes should include tests when they affect copy contracts, workflow copy, permissions, or rendered state. Existing examples include `apps/pages/test_marketing_copy.py`, `apps/docs/test_workflow_copy.py`, and `apps/docs/test_mcp_workflow_copy.py`.
- If a check cannot run locally because Docker, network, or external services are unavailable, state that explicitly in the handoff.

## Deployment Notes

- Pull requests run `.github/workflows/ci.yml`: frontend build, Django checks, cookiecutter option coverage, and pytest against Postgres and Redis.
- Pushes to `main` run `.github/workflows/deploy.yml`, building `deployment/Dockerfile` and deploying server and worker apps to CapRover.
- `render.yaml` and `fly.toml` exist, but the GitHub deployment workflow currently targets CapRover/GHCR.

## Risky Changes

Get explicit human confirmation before:

- Rotating or exposing API keys, Stripe secrets, Sentry DSNs, PostHog keys, Mailgun credentials, or AWS/S3 credentials.
- Changing payment entitlement logic, launch price tier behavior, or Stripe webhook handling.
- Deleting generated artifacts, project rows, user profiles, API audit logs, or migration files.
- Replacing the Cookiecutter template source or changing artifact export overwrite behavior.
