# TECH.md

Technical context for AI agents working on Djass.

## Runtime

- Python: `3.14.5` from `.python-version`
- Node: `24.15.0` from `.nvmrc` and `package.json` engines
- Go: `1.24` from `cli/go.mod` for the `djass` CLI
- Python dependency manager: `uv`
- Node package manager: npm with `package-lock.json`
- Database: PostgreSQL, using custom Postgres 18 in CI and local Docker
- Cache and queue broker: Redis

## Backend Stack

- Django 6
- django-allauth with email/password, GitHub social auth, MFA/passkeys, and recovery codes
- Django Ninja for API routes under `/api/`
- Django Q2 for background jobs
- Cookiecutter for repository generation
- django-storages / S3-compatible storage when `AWS_S3_ENDPOINT_URL` is configured
- WhiteNoise for static file serving
- Sentry, Logfire, django-structlog, and structlog for observability
- PostHog and Plausible for product analytics
- Stripe for one-time payment / launch price flows
- Mailgun via Anymail for email when configured
- FastMCP / MCP SDK for local and hosted agent workflows

## Frontend Stack

- Django templates in `frontend/templates`
- Tailwind CSS 4 compiled from `frontend/src/styles/index.css`
- HTMX copied to `frontend/static/vendors/js/`
- Alpine.js copied to `frontend/static/vendors/js/`
- Small browser modules copied from `frontend/src/js` to `frontend/static/js`
- No JavaScript bundler; `scripts/copy-app-js.mjs` copies browser modules directly

## Commands

Dockerized local development:

```bash
cp .env.example .env
make serve
make restart-worker
make manage migrate
make test
make shell
```

Host-side dependency and checks:

```bash
uv sync
npm ci
npm run build
npm run lint
uv run python manage.py check
uv run python manage.py sync_cookiecutter_options --check --skip-on-network-error
uv run pytest -q
```

MCP server:

```bash
uv run python -m apps.mcp.server
djass-mcp
```

Go CLI:

```bash
cd cli
go test ./...
go vet ./...
go build ./cmd/djass
```

Frontend:

```bash
npm run build
npm run watch
npm run lint
```

Formatting and linting:

```bash
uv run ruff check .
uv run ruff format .
uv run djlint frontend/templates
pre-commit run --all-files
```

## Important Settings

Settings live in `djass/settings.py` and read `.env`.

- `ENVIRONMENT`: `dev`, `test`, or `prod`
- `SITE_URL`: used for allowed hosts, CSRF trusted origins, and absolute URLs
- `COOKIECUTTER_TEMPLATE_PATH`: defaults to `https://github.com/LVTD-LLC/django-saas-starter.git`
- `DATABASE_URL` or `POSTGRES_*`: database configuration
- `REDIS_URL` or `REDIS_*`: Redis cache and Q2 broker
- `MEDIA_ROOT` / `AWS_S3_ENDPOINT_URL`: artifact storage
- `PAYMENTS_ENABLED`: generation entitlement gate
- `STRIPE_*`: checkout and webhook behavior
- `POSTHOG_API_KEY` / `POSTHOG_HOST`: analytics and aliasing
- `CHATWOOT_BASE_URL` / `CHATWOOT_WEBSITE_TOKEN`: support widget
- `SENTRY_*` and `LOGFIRE_TOKEN`: observability

## API and MCP Contracts

- API v1 endpoints live in `apps/api/views.py` and schemas in `apps/api/schemas.py`.
- The Go CLI lives in `cli/` and maps Projects API v1 operations to `djass` commands.
- API auth is in `apps/api/auth.py`; scoped keys use `ProjectAPIKeyScope`.
- API audit logs are `ProjectAPIAuditLog` rows.
- MCP tool implementations are split between `apps/mcp/server.py`, `apps/mcp/hosted.py`, and `apps/mcp/services.py`.
- Local MCP uses stdio by default. Hosted MCP uses Streamable HTTP mounted at `/mcp`.
- Artifact export must keep path traversal protections in `apps/mcp/services.py`.

## Generator Contract

`apps/core/generator_options.py` is the source of truth for:

- Cookiecutter defaults
- Feature flag keys
- Labels and user-facing descriptions
- Option grouping for UI/API/MCP
- Drift checks against upstream `cookiecutter.json`

When the upstream template changes, run:

```bash
uv run python manage.py sync_cookiecutter_options --check --skip-on-network-error
```

Update local defaults, UI/API/MCP contracts, docs, and tests together.
