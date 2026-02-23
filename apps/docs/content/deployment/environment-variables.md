---
title: Environment Variables
description: Practical guide to configuring generated Djass projects using .env.
keywords: Djass, environment variables, configuration, .env
author: Rasul
---

Use `.env.example` as the source of truth and copy it to `.env` before running the app.

```bash
cp .env.example .env
```

## Required for all environments

These values should always be set intentionally.

### Runtime and security

- `ENVIRONMENT` — `dev` or `prod`
- `DEBUG` — keep `off`/`False` in production
- `SECRET_KEY` — Django secret key
- `SITE_URL` — full external URL (e.g. `https://yourdomain.com`)

### Database

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`

### Redis / background jobs

- `REDIS_HOST`
- `REDIS_PORT`
- `REDIS_PASSWORD`
- `REDIS_DB` (default `0`)

Django Q2 uses Redis for queueing and worker communication.

## Recommended base variables

- `MEDIA_ROOT` — path for uploaded/generated artifacts (persist this in production)
- `COOKIECUTTER_TEMPLATE_PATH` — template source used for project generation

If not set, a default template path is used.

## Optional integrations

Enable only what you actively use.

### Auth and identity

- `GITHUB_CLIENT_ID`
- `GITHUB_CLIENT_SECRET`

### Storage

- `AWS_S3_ENDPOINT_URL`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_S3_BUCKET_NAME`

If `AWS_S3_ENDPOINT_URL` is empty, filesystem storage is used.

### Email and notifications

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

### AI provider config

- `OPENAI_API_KEY`

Optional model overrides:

- `OPENAI_MODEL_FAST`, `OPENAI_MODEL_BALANCED`, `OPENAI_MODEL_SMART`
- `ANTHROPIC_MODEL_FAST`, `ANTHROPIC_MODEL_BALANCED`, `ANTHROPIC_MODEL_SMART`
- `GEMINI_MODEL_FAST`, `GEMINI_MODEL_BALANCED`, `GEMINI_MODEL_SMART`

## Validation checklist before deploy

- `DEBUG` is off
- `SITE_URL` matches production domain
- DB/Redis credentials are not defaults
- secrets are stored in deployment secret manager (not committed)
- `MEDIA_ROOT` (or S3 config) is persistent

## Security notes

- Never commit `.env`.
- Rotate keys immediately if exposed.
- Prefer platform secret stores over plaintext files where possible.
