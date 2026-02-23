---
title: Repository Structure
description: How generated Djass projects are organized and where new code should live.
keywords: Djass, architecture, django apps, project structure
author: Rasul
---

Generated projects intentionally separate responsibilities by app to keep code discoverable for humans and AI tools.

## High-level layout

- `apps/core` — core business models, shared services, auth/profile logic
- `apps/api` — Django Ninja API routers, schemas, API-specific logic
- `apps/pages` — landing and product-facing page views/templates
- `apps/blog` — optional blog functionality
- `apps/docs` — optional documentation app and markdown content
- `frontend/` — webpack/tailwind assets and Django templates
- `deployment/` — container entrypoints and runtime infrastructure files

## Why this split matters

This structure reduces "where should this code go?" ambiguity.

- New domain logic usually belongs in `apps/core`.
- API endpoints should stay in `apps/api` instead of being mixed into page views.
- Marketing/legal pages stay in `apps/pages`.
- Presentation assets stay in `frontend/`.

That separation keeps reviews cleaner and makes AI-generated patches easier to validate.

## URL routing conventions

In `djass/urls.py`, app routes are mounted explicitly:

- `/api/` → `apps.api.urls`
- `/blog/` → `apps.blog.urls`
- `/docs/` → `apps.docs.urls`
- app pages/core routes mounted at root

Keep this predictable. New top-level product surfaces should have clear URL namespaces.

## Styling conventions

Tailwind is the default styling system. Prefer existing utility patterns before adding custom CSS.

When introducing design changes:

1. Reuse the established spacing/typography scale.
2. Keep color decisions centralized and consistent.
3. Avoid one-off CSS classes unless absolutely necessary.

## Practical rule for new features

When adding functionality, ship it as a vertical slice:

- model/service in `apps/core`
- endpoint in `apps/api` (if needed)
- page/update in `apps/pages` + templates
- background work via Django Q2 task (if asynchronous)

This keeps architecture coherent as the project grows.
