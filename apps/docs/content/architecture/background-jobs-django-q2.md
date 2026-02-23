---
title: Background Jobs with Django Q2
description: How asynchronous tasks are queued, processed, and monitored in generated Djass projects.
keywords: Djass, django q2, background jobs, async tasks
author: Rasul
---

Generated projects use **Django Q2** for asynchronous work.

## Why Django Q2 is used

Django Q2 is simple to operate inside a Django-first stack and works well for tasks like:

- project artifact generation,
- analytics/event processing,
- webhook side effects,
- email and non-blocking integrations.

## Current pattern in this codebase

Tasks are queued from request code using `async_task`, for example:

- `apps.core.views.create_project` queues project generation
- worker process runs `python manage.py qcluster`

Core queue settings are in `djass/settings.py` under `Q_CLUSTER`.

## Running workers locally

Workers run as part of `make serve` (Docker Compose).

If needed, restart only workers:

```bash
make restart-worker
```

## Adding a new background task

1. Create a pure function in `apps/core/tasks.py` (or a focused task module).
2. Keep inputs serializable (ids, strings, dicts).
3. Queue with `async_task("path.to.function", ...)` from views/services.
4. Log key context (entity id, action, error path).
5. Record user-facing status when task state matters.

## Reliability guidelines

- Make tasks idempotent where possible.
- Validate records exist before processing.
- Store failure details on model fields when users need visibility.
- Prefer retryable operations and defensive exception handling.

## Debug checklist

If tasks are not processing:

- confirm Redis is reachable,
- check worker container/process logs,
- verify task path string matches import path,
- verify env/config parity between web and worker services.
