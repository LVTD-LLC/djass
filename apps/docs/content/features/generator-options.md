---
title: Generator Options
description: What each project creation option changes in the generated repository.
keywords: Djass, generator options, cookiecutter, scaffolding
author: Rasul
---

When creating a project in Djass, each option toggles concrete code/config in the generated repository.

Djass keeps the supported starter template fields in the typed catalog at
`apps/core/generator_options.py`. That catalog feeds the UI, API, and MCP payload shape so
all entrypoints expose the same options and category metadata.

Run:

```bash
python manage.py sync_cookiecutter_options --check
```

to detect upstream drift after `django-saas-starter` changes. If the command fails, update
the catalog defaults, labels, and categories intentionally instead of copying raw
`cookiecutter.json` values into the UI.

CI runs this check with `--skip-on-network-error` so a temporary upstream fetch failure does
not block unrelated PRs.

## Core fields

- **Project Name / Slug**: naming used in generated files and package metadata.
- **CapRover App Name**: deployment app name used by CapRover-specific template files.
- **Repo URL / Description / Author fields**: metadata used in templates and defaults.
- **Project Main Color**: controls primary Tailwind color references used in templates.

## Integration toggles

### Monitoring

- **Use PostHog**: analytics wiring and related config.
- **Use Sentry**: error monitoring setup.
- **Use Logfire**: observability configuration for Logfire.
- **Use Healthchecks**: health-check related setup when enabled.

### CX

- **Use Chatwoot**: customer support/chat integration scaffolding.
- **Use Buttondown**: newsletter integration scaffolding.
- **Use MJML**: email templating/rendering support.

### Commerce

- **Use Stripe**: Stripe integration scaffold pieces.

### Storage

- **Use S3**: storage configuration paths for media assets.

### AI

- **Use AI**: AI-related service/config scaffolding.
- **Use MCP**: Model Context Protocol server/tooling support for agent workflows.

## Content toggles

- **Generate Blog**: includes `apps/blog` and related routes/templates.
- **Generate Docs**: includes `apps/docs` and markdown-driven docs pages.

## Delivery toggles

- **Use CI**: includes GitHub Actions CI workflow.
- **Use DigitalOcean**: includes DigitalOcean deployment scaffolding.

## Recommendation

Keep your first generation conservative. Enable only what you plan to use in the next 2–4 weeks.

It is usually easier to add one integration intentionally later than to maintain several unused integrations from day one.
