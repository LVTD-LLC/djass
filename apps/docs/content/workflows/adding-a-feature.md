---
title: Adding a Feature
description: A practical workflow for shipping new features in generated Djass projects.
keywords: Djass, feature development, workflow, django
author: Rasul
---

Use this workflow when adding product functionality.

## 1) Start with one vertical slice

Define the smallest shippable slice that includes:

- domain logic,
- user/API surface,
- and success/failure states.

Avoid starting with broad refactors.

## 2) Place code in the right app

- Domain models/services → `apps/core`
- API routers/schemas → `apps/api`
- Product pages/templates → `apps/pages` + `frontend/templates`
- Async work → `apps/core/tasks.py` queued through Django Q2

## 3) Implement in this order

1. Model changes and migrations
2. Service/business logic
3. API/view layer
4. Template/UI updates
5. Background task wiring (if needed)
6. Tests and regression checks

## 4) Keep operations safe

If the feature changes background processing or account-access flows:

- add explicit logs for traceability,
- persist failure reasons users can understand,
- keep retry paths available (manual or automated).

## 5) Ship with docs in the same PR

If behavior, architecture, or setup changed, update docs in the same PR.

At minimum, update:

- the relevant docs page,
- any setup instructions affected,
- and examples/commands users rely on.

## Definition of done

A feature is done when:

- users can complete the intended job,
- unhappy paths are handled,
- docs are updated,
- and runtime/config impact is understood.
