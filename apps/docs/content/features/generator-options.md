---
title: Generator Options
description: What each project creation option changes in the generated repository.
keywords: Djass, generator options, cookiecutter, scaffolding
author: Rasul
---

When creating a project in Djass, each option toggles concrete code/config in the generated repository.

## Core fields

- **Project Name / Slug**: naming used in generated files and package metadata.
- **Repo URL / Description / Author fields**: metadata used in templates and defaults.
- **Project Main Color**: controls primary Tailwind color references used in templates.

## Integration toggles

- **Use PostHog**: analytics wiring and related config.
- **Use Buttondown**: newsletter integration scaffolding.
- **Use S3**: storage configuration paths for media assets.
- **Use Stripe**: subscription billing/webhook-related scaffold pieces.
- **Use Sentry**: error monitoring setup.
- **Use MJML**: email templating/rendering support.
- **Use AI**: AI-related service/config scaffolding.
- **Use Logfire**: observability configuration for Logfire.
- **Use Healthchecks**: health-check related setup when enabled.

## Content toggles

- **Generate Blog**: includes `apps/blog` and related routes/templates.
- **Generate Docs**: includes `apps/docs` and markdown-driven docs pages.
- **Use CI**: includes GitHub Actions CI workflow.

## Recommendation

Keep your first generation conservative. Enable only what you plan to use in the next 2–4 weeks.

It is usually easier to add one integration intentionally later than to maintain several unused integrations from day one.
