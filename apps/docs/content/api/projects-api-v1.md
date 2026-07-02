---
title: Projects API v1
description: Create, poll, and download Djass project artifacts through the Projects API.
keywords: Djass, Projects API, project generation, API keys, agent workflow
author: Rasul
---

# Djass Projects API (v1)

**Base URL:** `https://djass.dev/api/v1`
**Coverage:** `create`, `list`, `get`, `status`, and `download` endpoints for project generation.

---

## 1) What this API does

This API lets an agent:
1. inspect the current generator option catalog,
2. create a new Djass project generation job,
3. list the caller's projects,
4. fetch one project by id,
5. poll status until generation is complete,
6. download the generated project ZIP artifact.

All data access is **owner-scoped**: keys can only see projects for their own profile.

---

## 2) Authentication and key scoping

Project mutation and project history endpoints require an API key. The generator option catalog is public.

### Accepted auth formats (in lookup order)
1. `X-API-Key: <key>`
2. `Authorization: Bearer <key>` (also accepts `Api-Key`, `apikey`, `token` schemes)
3. Query fallback: `?api_key=<key>` (legacy compatibility)

### Key types
- **Legacy profile key**: full access to `projects:create` + `projects:read`
- **Scoped API key** (`ProjectAPIKey`): only granted scopes

### Required scopes
- `POST /projects` requires `projects:create`
- `GET /projects`, `GET /projects/{id}`, `GET /projects/{id}/status`, and `GET /projects/{id}/download` require `projects:read`
- `GET /project-options` does not require authentication

If scope is missing: `403` with `error.code = "insufficient_scope"`.

---

## 3) Error contract (all non-2xx)

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

### Common codes used by this API
- `auth_required`
- `insufficient_scope`
- `invalid_project_slug`
- `quota_exceeded`
- `project_not_found`
- `artifact_not_ready`
- `retryable_error`
- `internal_error`

Retry guidance may appear in `error.details.retry_guidance`.

---

## 4) Endpoint reference

### 4.1 Project options

**Method/Path:** `GET /project-options`
**Purpose:** return the current generator option catalog grouped for UI/API clients.

#### Success response (`200`)

```json
{
  "defaults": {
    "project_name": "My Awesome Project",
    "project_slug": "{{ cookiecutter.project_name.lower()|replace(' ', '_')|replace('-', '_')|replace('.', '_')|trim() }}",
    "caprover_app_name": "{{ cookiecutter.project_slug|replace('_', '-') }}",
    "repo_url": "https://github.com/cookiecutter/cookiecutter",
    "use_posthog": "y",
    "use_chatwoot": "n",
    "use_apprise": "n",
    "use_mcp": "n",
    "use_digitalocean": "n"
  },
  "groups": [
    {
      "key": "monitoring",
      "label": "Monitoring",
      "options": [
        {
          "key": "use_posthog",
          "label": "Use PostHog",
          "description": "Adds product analytics. Backend logs use standard Python logging so PostHog Logs can read the same structured fields when its handler is attached.",
          "default": "y",
          "category": "monitoring"
        }
      ]
    }
  ]
}
```

Notes:
- `defaults` mirrors the typed generator option catalog used by Djass.
- `groups` contains feature flags only, with labels and descriptions for UI/API clients.
- Identity and metadata fields stay in the create payload.
- create requests use the same flat option keys shown in `groups[].options[]`.

### 4.2 Create project

**Method/Path:** `POST /projects`  
**Purpose:** queue project generation from template settings.

#### Request body

```json
{
  "project_name": "Acme CRM",
  "project_slug": "acme_crm",
  "caprover_app_name": "acme-crm",
  "project_description": "Internal CRM for support and sales",
  "repo_url": "https://github.com/acme/acme-crm",
  "author_name": "Acme Bot",
  "author_email": "bot@acme.test",
  "author_url": "https://acme.test",
  "project_main_color": "green",
  "use_posthog": "y",
  "use_chatwoot": "n",
  "use_s3": "y",
  "use_stripe": "y",
  "use_sentry": "y",
  "generate_blog": "y",
  "generate_docs": "y",
  "use_mjml": "y",
  "use_ai": "y",
  "use_healthchecks": "y",
  "use_apprise": "n",
  "use_mcp": "n",
  "use_ci": "y",
  "use_digitalocean": "n"
}
```

Notes:
- all feature flags are `"y"|"n"`
- use `GET /project-options` to discover the current supported generator flags
- `project_slug` is normalized (`slugify`, then `-` -> `_`)
- if `author_email` is empty, backend fills it from profile email

#### Success response (`201`)

```json
{
  "project": {
    "id": 123,
    "name": "Acme CRM",
    "slug": "acme_crm",
    "status": "queued",
    "error_message": "",
    "created_at": "2026-03-11T12:00:00Z",
    "updated_at": "2026-03-11T12:00:00Z",
    "started_at": null,
    "finished_at": null,
    "artifact_ready": false,
    "input_payload": {
      "project_name": "Acme CRM",
      "project_slug": "acme_crm",
      "caprover_app_name": "acme-crm",
      "project_description": "Internal CRM for support and sales",
      "repo_url": "https://github.com/acme/acme-crm",
      "author_name": "Acme Bot",
      "author_email": "bot@acme.test",
      "author_url": "https://acme.test",
      "project_main_color": "green",
      "use_posthog": "y",
      "use_chatwoot": "n",
      "use_s3": "y",
      "use_stripe": "y",
      "use_sentry": "y",
      "generate_blog": "y",
      "generate_docs": "y",
      "use_mjml": "y",
      "use_ai": "y",
      "use_healthchecks": "y",
      "use_apprise": "n",
      "use_mcp": "n",
      "use_ci": "y",
      "use_digitalocean": "n"
    }
  }
}
```

#### Error statuses
- `400` invalid payload / invalid slug
- `401` missing or invalid key
- `403` insufficient scope
- `429` project quota exceeded
- `503` temporary queueing failure (retryable)
- `500` internal error

---

### 4.3 List projects

**Method/Path:** `GET /projects`  
**Purpose:** list caller-owned projects with pagination and optional status filter.

#### Query params
- `limit` (default `20`, min `1`, max `100`)
- `offset` (default `0`, min `0`)
- `status` (`queued|generating|ready|failed`)

#### Success response (`200`)

```json
{
  "projects": [
    {
      "id": 123,
      "name": "Acme CRM",
      "slug": "acme_crm",
      "status": "ready",
      "error_message": "",
      "created_at": "2026-03-11T12:00:00Z",
      "updated_at": "2026-03-11T12:02:40Z",
      "started_at": "2026-03-11T12:00:05Z",
      "finished_at": "2026-03-11T12:02:39Z",
      "artifact_ready": true,
      "input_payload": {
        "project_name": "Acme CRM",
        "project_slug": "acme_crm"
      }
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0,
  "has_next": false,
  "filters": {
    "status": "ready"
  }
}
```

#### Error statuses
- `401` missing or invalid key
- `403` insufficient scope
- `422` invalid query params (`limit/offset/status`)
- `500` internal error

---

### 4.4 Get project

**Method/Path:** `GET /projects/{project_id}`  
**Purpose:** fetch one full project object.

#### Success response (`200`)
Returns full `Project` object (same shape as `project` in create response).

#### Error statuses
- `401` missing/invalid key
- `403` insufficient scope
- `404` project not found
- `500` internal error

---

### 4.5 Get project status

**Method/Path:** `GET /projects/{project_id}/status`  
**Purpose:** lightweight polling endpoint.

#### Success response (`200`)

```json
{
  "id": 123,
  "status": "generating",
  "error_message": "",
  "artifact_ready": false,
  "started_at": "2026-03-11T12:00:05Z",
  "finished_at": null,
  "updated_at": "2026-03-11T12:00:20Z"
}
```

#### Error statuses
- `401` missing/invalid key
- `403` insufficient scope
- `404` project not found
- `500` internal error

---

### 4.6 Download project artifact

**Method/Path:** `GET /projects/{project_id}/download`  
**Purpose:** download the generated repository ZIP after project generation is ready.

#### Success response (`200`)

Returns a binary ZIP stream with:

- `Content-Type: application/zip`
- `Content-Disposition: attachment; filename="<project_slug>-YYYYMMDD.zip"`

#### Error statuses
- `401` missing/invalid key
- `403` insufficient scope
- `404` project not found
- `409` artifact is not ready yet
- `500` internal error

When the artifact is not ready, poll `GET /projects/{project_id}/status` until
`artifact_ready` is `true`.

---

## 5) Agent quickstart (copy-paste)

```bash
# 0) Set runtime values
export DJASS_BASE_URL="https://djass.dev/api/v1"
export DJASS_API_KEY="replace-with-key"

# 1) Create project
curl -sS -X POST "$DJASS_BASE_URL/projects" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $DJASS_API_KEY" \
  --data '{
    "project_name": "Acme CRM",
    "project_slug": "acme_crm",
    "caprover_app_name": "acme-crm",
    "project_description": "Internal CRM for support and sales",
    "repo_url": "https://github.com/acme/acme-crm",
    "author_name": "Acme Bot",
    "author_email": "bot@acme.test",
    "author_url": "https://acme.test",
    "project_main_color": "green",
    "use_posthog": "y",
    "use_chatwoot": "n",
    "use_s3": "y",
    "use_stripe": "y",
    "use_sentry": "y",
    "generate_blog": "y",
    "generate_docs": "y",
    "use_mjml": "y",
    "use_ai": "y",
    "use_healthchecks": "y",
    "use_apprise": "n",
    "use_mcp": "n",
    "use_ci": "y",
    "use_digitalocean": "n"
  }'

# 2) Get latest project (or parse ID from create response)
curl -sS "$DJASS_BASE_URL/projects?limit=1&offset=0" \
  -H "X-API-Key: $DJASS_API_KEY"

# 3) Poll status until ready/failed
PROJECT_ID="123"
curl -sS "$DJASS_BASE_URL/projects/$PROJECT_ID/status" \
  -H "X-API-Key: $DJASS_API_KEY"

# 4) Fetch full project object
curl -sS "$DJASS_BASE_URL/projects/$PROJECT_ID" \
  -H "X-API-Key: $DJASS_API_KEY"

# 5) Download generated repo ZIP when ready
curl -L "$DJASS_BASE_URL/projects/$PROJECT_ID/download" \
  -H "X-API-Key: $DJASS_API_KEY" \
  -o "acme_crm.zip"
```

Polling recommendation:
- start at 2s interval
- back off to max 15s
- stop on `status in {"ready", "failed"}`

---

## 6) Common failure cases (with real payload shapes)

### Missing/invalid auth (`401`)
```json
{
  "error": {
    "code": "auth_required",
    "category": "auth",
    "message": "Authentication required.",
    "retryable": false,
    "details": {}
  }
}
```

### Missing scope (`403`)
```json
{
  "error": {
    "code": "insufficient_scope",
    "category": "auth",
    "message": "API key is missing required scope: projects:create",
    "retryable": false,
    "details": {
      "required_scope": "projects:create"
    }
  }
}
```

### Invalid slug (`400`)
```json
{
  "error": {
    "code": "invalid_project_slug",
    "category": "validation",
    "message": "project_slug must contain letters or numbers.",
    "retryable": false,
    "details": {
      "field": "project_slug"
    }
  }
}
```

### Quota exceeded (`429`)
```json
{
  "error": {
    "code": "quota_exceeded",
    "category": "quota",
    "message": "Project quota exceeded for this API identity.",
    "retryable": false,
    "details": {
      "quota": 200,
      "retry_guidance": "Delete old projects or request limit bump."
    }
  }
}
```

### Temporary queue failure (`503`, retryable)
```json
{
  "error": {
    "code": "retryable_error",
    "category": "retryable",
    "message": "Temporary failure while queueing project generation.",
    "retryable": true,
    "details": {
      "retry_guidance": "Retry with exponential backoff."
    }
  }
}
```

### Not found (`404`)
```json
{
  "error": {
    "code": "project_not_found",
    "category": "validation",
    "message": "Project not found.",
    "retryable": false,
    "details": {
      "project_id": 999999
    }
  }
}
```

### Artifact not ready (`409`, retryable)
```json
{
  "error": {
    "code": "artifact_not_ready",
    "category": "retryable",
    "message": "Project artifact is not ready yet.",
    "retryable": true,
    "details": {
      "project_id": 123,
      "status": "generating",
      "retry_guidance": "Poll the status endpoint until artifact_ready is true."
    }
  }
}
```

---

## 7) Implementation references

This API reference is aligned with backend implementation and tests:
- endpoint logic: `apps/api/views.py`
- schema definitions: `apps/api/schemas.py`
- auth parsing/scoping: `apps/api/auth.py`, `apps/api/utils.py`
- API tests: `apps/api/test_spec_001_contract.py`

Local execution note:
- running API tests in this environment requires PostgreSQL with pgvector migration support (`CREATE EXTENSION vector`)
- sqlite fallback test run fails by design on that migration

---

## 8) Known limitations / TODO

1. **No idempotency key on create**: repeated `POST /projects` can create duplicates.
2. **No callback/webhook** for completion: clients must poll `/status`.
3. **Legacy query-string auth remains enabled** for compatibility; should eventually be deprecated for security hygiene.
4. **No server-provided request ID** in response body for cross-system tracing.
