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
- **Repo URL / Description / Author fields**: metadata used in templates and defaults.
- **CapRover App Name**: deployment app name derived from the project slug.
- **Project Main Color**: controls primary Tailwind color references used in templates.

## Integration toggles

### Monitoring

- **Use PostHog**: product analytics. Backend logs use standard Python logging, so
  PostHog Logs can read the same structured fields when its handler is attached.
- **Use Sentry**: error monitoring plus breadcrumbs, events, and optional logs
  from standard Python logging records.
- **Use Healthchecks**: health-check related setup when enabled.
- **Use Apprise**: Apprise-backed admin notification helper, config, deployment docs, and tests.

### CX

- **Use Chatwoot**: customer support/chat integration scaffolding.
- **Use MJML**: email templating/rendering support.

### UX

- **Use Keyboard Shortcuts**: keyboard shortcut helpers, data attributes, and
  visible shortcut hints for command-oriented UI controls.

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
