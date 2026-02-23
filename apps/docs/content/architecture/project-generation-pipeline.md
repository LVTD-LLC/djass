---
title: Project Generation Pipeline
description: End-to-end flow from form submission to downloadable generated project artifact.
keywords: Djass, cookiecutter, project generation, architecture
author: Rasul
---

This page explains how Djass turns user input into a generated project zip.

## End-to-end flow

1. User submits the project creation form.
2. Backend validates input via `ProjectCreateForm`.
3. A `Project` row is created with `status=queued` and saved payload.
4. Background task `generate_project_artifact` is enqueued.
5. Worker runs Cookiecutter using `COOKIECUTTER_TEMPLATE_PATH`.
6. Generated directory is zipped and stored as `ProjectArtifact`.
7. Project status becomes `ready` (or `failed` with error details).
8. User downloads artifact from the dashboard.

## Key models

- `Project` tracks generation status and input payload.
- `ProjectArtifact` stores generated zip metadata and file.

Both live in `apps/core/models.py`.

## Key implementation points

- Generation is asynchronous by design to avoid blocking web requests.
- Cookiecutter Python API is attempted first, then CLI fallback is used.
- Artifacts include SHA-256 and size for integrity and traceability.
- Failures are persisted on `Project.error_message` for user feedback.

## Configuration knobs

- `COOKIECUTTER_TEMPLATE_PATH` controls which template is used.
- `MEDIA_ROOT` and storage backend determine where artifacts are stored.
- Redis + Q2 config control background execution.

## Extension points

Common customizations:

- add more form fields and include them in payload mapping,
- add validation rules for product-specific constraints,
- post-process generated projects before zipping,
- run security/quality checks on generated output before marking ready.
