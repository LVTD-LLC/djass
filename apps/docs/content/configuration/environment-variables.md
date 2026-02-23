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
- `BUTTONDOWN_API_KEY`

### Billing

- `STRIPE_PUBLISHABLE_KEY`
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRICE_ID_MONTHLY`
- `STRIPE_PRICE_ID_YEARLY`

### Observability

- `SENTRY_DSN`
- `LOGFIRE_TOKEN`
- `POSTHOG_API_KEY`

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
