# Spec 001 — Agent Project API Contract (v1)

**Status:** Finalized  
**Version:** `spec-001`  
**Base path:** `/api/v1`  
**Scope:** project create/list/get/status endpoints for agent integrations.

## Authentication

All endpoints in this spec require API key auth.

Accepted formats:
- `X-API-Key: <profile_api_key_or_scoped_key>`
- `Authorization: Bearer <profile_api_key_or_scoped_key>`
- Query fallback: `?api_key=<profile_api_key_or_scoped_key>` (kept for compatibility)

Scoped key permissions:
- `projects:create` for `POST /api/v1/projects`
- `projects:read` for `GET` list/get/status endpoints

Legacy profile API keys keep full access to maintain backward compatibility.

If auth is missing/invalid, response is:
- `401 Unauthorized`
- Error schema from [Error Contract](#error-contract)

## Error Contract

All non-2xx responses for Spec 001 follow this schema:

```json
{
  "error": {
    "code": "machine_readable_code",
    "category": "validation|auth|quota|retryable|internal",
    "message": "Human readable summary",
    "retryable": false,
    "details": {}
  }
}
```

Common codes in this spec:
- `auth_required`
- `insufficient_scope`
- `subscription_required`
- `quota_exceeded`
- `invalid_project_slug`
- `project_not_found`
- `retryable_error`
- `internal_error`

Retry guidance is provided in `error.details.retry_guidance` where relevant.

## Endpoint: Create Project

`POST /api/v1/projects`

### Request body

```json
{
  "project_name": "My Awesome Project",
  "project_slug": "my_awesome_project",
  "project_description": "Optional",
  "repo_url": "",
  "author_name": "",
  "author_email": "",
  "author_url": "",
  "project_main_color": "green",
  "use_posthog": "y",
  "use_buttondown": "y",
  "use_s3": "y",
  "use_stripe": "y",
  "use_sentry": "y",
  "generate_blog": "y",
  "generate_docs": "y",
  "use_mjml": "y",
  "use_ai": "y",
  "use_logfire": "y",
  "use_healthchecks": "y",
  "use_ci": "y"
}
```

### Responses
- `201 Created`: returns `{ "project": <Project> }`
- `400 Bad Request`: invalid payload (for example non-normalizable `project_slug`)
- `401 Unauthorized`: auth required
- `403 Forbidden`: active subscription required
- `429 Too Many Requests`: per-identity project quota reached (`quota_exceeded`)
- `503 Service Unavailable`: temporary queue/generation dispatch failure (`retryable_error`)
- `500 Internal Server Error`: unexpected server error (`internal_error`)

## Endpoint: List Projects

`GET /api/v1/projects`

### Query parameters
- `limit` (default `20`, max `100`)
- `offset` (default `0`)
- `status` (optional: `queued|generating|ready|failed`)

### Responses
- `200 OK`

```json
{
  "projects": ["<Project>"],
  "total": 1,
  "limit": 20,
  "offset": 0,
  "has_next": false,
  "filters": {
    "status": "ready"
  }
}
```

List is scoped to authenticated user only.

## Endpoint: Get Project

`GET /api/v1/projects/{project_id}`

### Responses
- `200 OK`: `<Project>`
- `401 Unauthorized`
- `404 Not Found` (`project_not_found`)

## Endpoint: Get Project Status

`GET /api/v1/projects/{project_id}/status`

### Responses
- `200 OK`

```json
{
  "id": 123,
  "status": "queued",
  "error_message": "",
  "artifact_ready": false,
  "started_at": null,
  "finished_at": null,
  "updated_at": "2026-03-10T16:00:00Z"
}
```

- `401 Unauthorized`
- `404 Not Found` (`project_not_found`)

## Canonical `Project` response object

```json
{
  "id": 123,
  "name": "My Awesome Project",
  "slug": "my_awesome_project",
  "status": "queued",
  "error_message": "",
  "created_at": "2026-03-10T16:00:00Z",
  "updated_at": "2026-03-10T16:00:00Z",
  "started_at": null,
  "finished_at": null,
  "artifact_ready": false,
  "input_payload": {}
}
```

`status` enum:
- `queued`
- `generating`
- `ready`
- `failed`

## Contract assumptions (Spec 001 decisions)

- Ownership boundary is strict: project resources are only visible to the authenticated user who owns them.
- `project_slug` is normalized to snake_case (`slugify + '-' -> '_'`) and must contain alphanumeric characters after normalization.
- Background generation is asynchronous and starts after successful create.
- `artifact_ready` is the canonical boolean for download availability.
- `input_payload` is echoed in project responses for deterministic agent-side replay/debugging.
