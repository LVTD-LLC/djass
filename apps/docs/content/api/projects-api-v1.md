# Djass Projects API (v1)

**Base URL:** `https://<your-djass-host>/api/v1`  
**Coverage:** `create`, `list`, `get`, `status` endpoints for project generation.

---

## 1) What this API does

This API lets an agent:
1. create a new Djass project generation job,
2. list the caller's projects,
3. fetch one project by id,
4. poll status until generation is complete.

All data access is **owner-scoped**: keys can only see projects for their own profile.

---

## 2) Authentication and key scoping

All endpoints require an API key.

### Accepted auth formats (in lookup order)
1. `X-API-Key: <key>`
2. `Authorization: Bearer <key>` (also accepts `Api-Key`, `apikey`, `token` schemes)
3. Query fallback: `?api_key=<key>` (legacy compatibility)

### Key types
- **Legacy profile key**: full access to `projects:create` + `projects:read`
- **Scoped API key** (`ProjectAPIKey`): only granted scopes

### Required scopes
- `POST /projects` requires `projects:create`
- `GET /projects`, `GET /projects/{id}`, `GET /projects/{id}/status` require `projects:read`

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
- `subscription_required`
- `invalid_project_slug`
- `quota_exceeded`
- `project_not_found`
- `retryable_error`
- `internal_error`

Retry guidance may appear in `error.details.retry_guidance`.

---

## 4) Endpoint reference

### 4.1 Create project

**Method/Path:** `POST /projects`  
**Purpose:** queue project generation from template settings.

#### Request body

```json
{
  "project_name": "Acme CRM",
  "project_slug": "acme_crm",
  "project_description": "Internal CRM for support and sales",
  "repo_url": "https://github.com/acme/acme-crm",
  "author_name": "Acme Bot",
  "author_email": "bot@acme.test",
  "author_url": "https://acme.test",
  "project_main_color": "green",
  "use_posthog": "y",
  "use_chatwoot": "n",
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
  "use_mcp": "n",
  "use_ci": "y"
}
```

Notes:
- all feature flags are `"y"|"n"`
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
      "project_description": "Internal CRM for support and sales",
      "repo_url": "https://github.com/acme/acme-crm",
      "author_name": "Acme Bot",
      "author_email": "bot@acme.test",
      "author_url": "https://acme.test",
      "project_main_color": "green",
      "use_posthog": "y",
      "use_chatwoot": "n",
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
      "use_mcp": "n",
      "use_ci": "y"
    }
  }
}
```

#### Error statuses
- `400` invalid payload / invalid slug
- `401` missing or invalid key
- `403` subscription required or insufficient scope
- `429` project quota exceeded
- `503` temporary queueing failure (retryable)
- `500` internal error

---

### 4.2 List projects

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

### 4.3 Get project

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

### 4.4 Get project status

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

## 5) Agent quickstart (copy-paste)

```bash
# 0) Set runtime values
export DJASS_BASE_URL="https://your-djass-host/api/v1"
export DJASS_API_KEY="replace-with-key"

# 1) Create project
curl -sS -X POST "$DJASS_BASE_URL/projects" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $DJASS_API_KEY" \
  --data '{
    "project_name": "Acme CRM",
    "project_slug": "acme_crm",
    "project_description": "Internal CRM for support and sales",
    "repo_url": "https://github.com/acme/acme-crm",
    "author_name": "Acme Bot",
    "author_email": "bot@acme.test",
    "author_url": "https://acme.test",
    "project_main_color": "green",
    "use_posthog": "y",
    "use_chatwoot": "n",
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
    "use_mcp": "n",
    "use_ci": "y"
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
3. **No artifact download endpoint in this spec**: clients need another API/surface to fetch ZIP output.
4. **Legacy query-string auth remains enabled** for compatibility; should eventually be deprecated for security hygiene.
5. **No server-provided request ID** in response body for cross-system tracing.
