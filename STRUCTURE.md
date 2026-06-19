# STRUCTURE.md

Repository structure and placement rules for AI agents working on Djass.

## Top-Level Layout

- `djass/`: Django project settings, URL root, ASGI/WSGI, storage, sitemap, logging, Sentry helpers
- `apps/core/`: shared business logic, core models, forms, views, tasks, pricing, generator catalog, prompts, management commands
- `apps/api/`: Django Ninja API schemas, auth, views, audit logging, API models, API tests
- `apps/mcp/`: MCP server, hosted MCP integration, service layer, MCP tests
- `apps/pages/`: landing, pricing, legal, signup tracking, marketing/admin page views
- `apps/blog/`: blog models, admin, routes, and views
- `apps/docs/`: markdown-backed documentation app and documentation tests
- `apps/docs/content/`: user-facing markdown docs
- `frontend/templates/`: Django templates
- `frontend/src/styles/`: source CSS and Pygments CSS
- `frontend/src/js/`: browser modules copied to static output
- `frontend/static/`: generated/copied static assets and vendor images
- `scripts/`: Node scripts that copy vendor assets, copy app JS, and watch frontend assets
- `deployment/`: production Dockerfile and entrypoint
- `.github/workflows/`: CI and deployment workflows

## Placement Rules

- Put domain models, cross-entrypoint services, generator behavior, background jobs, and pricing logic in `apps/core`.
- Put HTTP API-specific request/response schemas, auth, error contracts, and audit logging in `apps/api`.
- Put MCP tool/service behavior in `apps/mcp`. Shared validation should call core forms/catalogs rather than duplicating rules.
- Put product/marketing/legal page views in `apps/pages`.
- Put docs rendering logic in `apps/docs`; put docs content under `apps/docs/content/<category>/<page>.md`.
- Put reusable page chrome and shared snippets in `frontend/templates/components`.
- Put authenticated app pages in `frontend/templates/pages` unless they belong to account, MFA, blog, docs, or component-specific folders.
- Put browser behavior in `frontend/src/js/modules` and initialize it from `frontend/src/js/app.js`.
- Put reusable styling primitives in `frontend/src/styles/index.css`; prefer existing `.dj-*` classes before adding new CSS.

## Cross-Cutting Feature Pattern

For a new generated-project feature or generator flag, update a vertical slice:

- `apps/core/generator_options.py`
- `apps/core/forms.py`
- `apps/core/views.py` if the dashboard or create flow changes
- `apps/api/schemas.py` and `apps/api/views.py`
- `apps/mcp/server.py` and `apps/mcp/services.py`
- `frontend/templates/pages/project-create.html` and `project-detail.html` when UI display changes
- docs under `apps/docs/content`
- tests in `apps/core/tests`, `apps/api`, and `apps/mcp`

For a new API capability:

- Add schema in `apps/api/schemas.py`
- Add auth/scope behavior in `apps/api/auth.py` or `apps/api/models.py` if needed
- Add endpoint in `apps/api/views.py`
- Add audit action in `apps/api/audit.py` / `ProjectAPIAuditLog` if it is project-related
- Add contract tests near `apps/api/test_spec_001_contract.py`

For a new background job:

- Add task function in `apps/core/tasks.py` or a closely owned app task module
- Enqueue by dotted path through Django Q2
- Persist job state on a model when user-visible
- Test the enqueue path by monkeypatching `async_task`

## Migration Rules

- Create Django migrations for model changes.
- Do not edit existing migrations unless the change is explicitly pre-merge migration cleanup and coordinated with the maintainer.
- Keep migration files out of formatting churn beyond what Django generates.

## Docs Rules

- Existing docs-writing guidance is scoped in `apps/docs/AGENTS.md`.
- Keep docs frontmatter fields consistent: `title`, `description`, `keywords`, `author`.
- When changing setup, architecture, API, MCP, or generator behavior, update docs in the same change.
