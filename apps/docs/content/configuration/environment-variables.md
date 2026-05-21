---
title: Environment Variables
description: Configuration reference for Djass runtime, integrations, and background jobs.
keywords: Djass, environment variables, configuration, .env
author: Rasul
---

Use `.env.example` as the source of truth and copy it to `.env`:

```bash
cp .env.example .env
```

## Core runtime variables

These should always be set intentionally.

- `ENVIRONMENT` — `dev` or `prod`
- `DEBUG` — keep `off`/`False` outside local development
- `SECRET_KEY` — Django secret key
- `SITE_URL` — canonical app URL
- `MEDIA_ROOT` — path for generated artifacts and uploaded files

## Database

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`

## Redis + background jobs

- `REDIS_HOST`
- `REDIS_PORT`
- `REDIS_PASSWORD`
- `REDIS_DB`

Django Q2 uses Redis for queueing and worker communication.

## Project generation

- `COOKIECUTTER_TEMPLATE_PATH` — template source used for generated projects

If not set, Djass uses the default template path configured in settings.

## Optional integrations

Enable only what you actively use.

### Authentication

- `GITHUB_CLIENT_ID`
- `GITHUB_CLIENT_SECRET`

### Storage

- `AWS_S3_ENDPOINT_URL`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_S3_BUCKET_NAME`

If `AWS_S3_ENDPOINT_URL` is empty, filesystem storage is used.

### Email and newsletter

- `MAILGUN_API_KEY`
- `MAILGUN_SENDER_DOMAIN` (e.g. `mg.gregagi.com`)
- `MAILGUN_API_URL` (optional, set `https://api.eu.mailgun.net` for EU-region accounts)
- `DEFAULT_FROM_EMAIL` (optional sender override)
- `SERVER_EMAIL` (optional error sender override)
- `BUTTONDOWN_API_KEY`

### Customer support

- `CHATWOOT_BASE_URL` (e.g. `https://chatwoot.example.com`)
- `CHATWOOT_WEBSITE_TOKEN` (public website inbox token)

### Observability

- `SENTRY_DSN`
- `SENTRY_ENABLED` (optional; defaults to enabled only when `SENTRY_DSN` is set in `prod`)
- `SENTRY_ENVIRONMENT` (optional Sentry environment override)
- `SENTRY_RELEASE` (optional release/version, ideally the deployed commit SHA)
- `SENTRY_TRACES_SAMPLE_RATE` (default `1.0`)
- `SENTRY_PROFILE_SESSION_SAMPLE_RATE` (default `1.0`)
- `SENTRY_ENABLE_LOGS` (default `True`)
- `SENTRY_SEND_DEFAULT_PII` (default `False`)
- `SENTRY_INCLUDE_LOCAL_VARIABLES` (default `False`)
- `SENTRY_MAX_BREADCRUMBS` (default `100`)
- `SENTRY_AI_INCLUDE_PROMPTS` (default `False`; set to `True` only if prompt/response capture is acceptable)
- `SENTRY_AI_HANDLED_TOOL_CALL_EXCEPTIONS` (default `True`)
- `LOGFIRE_TOKEN`
- `POSTHOG_API_KEY` (project API key `phc_...` used by Djass capture calls)
- `POSTHOG_HOST` (`https://us.i.posthog.com` or `https://eu.i.posthog.com`)

### Payments

- `PAYMENTS_ENABLED` (default `False`) — when disabled, checkout and customer portal routes stay dormant; when enabled, project generation requires active account access
- `GRANT_PRO_MEMBERSHIP_ON_SIGNUP` (default `True`) — assigns new users subscribed/pro access immediately
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRICE_ID_ONE_TIME`
- `STRIPE_ONE_TIME_AMOUNT_CENTS` (default `99900`)

### AI provider

- `OPENAI_API_KEY`

Optional model overrides:

- `OPENAI_MODEL_FAST`, `OPENAI_MODEL_BALANCED`, `OPENAI_MODEL_SMART`
- `ANTHROPIC_MODEL_FAST`, `ANTHROPIC_MODEL_BALANCED`, `ANTHROPIC_MODEL_SMART`
- `GEMINI_MODEL_FAST`, `GEMINI_MODEL_BALANCED`, `GEMINI_MODEL_SMART`

## Configuration sanity checklist

- `DEBUG` is off outside local development
- DB/Redis credentials are not default placeholders
- secrets are managed securely and never committed
- `MEDIA_ROOT` (or S3 config) is persistent for generated artifacts

## Security notes

- Never commit `.env`.
- Rotate credentials immediately if exposed.
- Prefer secret managers over plaintext files when possible.
- Keep PostHog personal/management API keys out of app runtime config; Djass only needs the project API key for ingestion.
