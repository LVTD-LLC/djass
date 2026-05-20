---
title: PostHog Funnel Analytics
description: Djass PostHog funnel event mapping, setup, and verification runbook.
keywords: Djass, PostHog, analytics, funnel, feedback
author: Rasul
---

## Goal

Track core funnel behavior reliably in PostHog:

1. page view
2. signup/auth
3. project create

## Configuration

Required env vars:

- `POSTHOG_API_KEY` — **PostHog project API key** (`phc_...`) for capture
- `POSTHOG_HOST` — ingest host (`https://us.i.posthog.com` or `https://eu.i.posthog.com`)

Djass wires both frontend and backend capture through these settings. No PostHog secret is hardcoded in source.

## Event mapping

| Funnel Step | Event Name | Where Emitted | Key Properties |
|---|---|---|---|
| Page view | `$pageview` | PostHog JS snippet (`capture_pageview: true`) in `base_landing.html` / `base_app.html` | standard PostHog page properties |
| Signup | `user_signed_up` | `apps/pages/views.py` (`SignupTrackingMixin._track_signup`) | `signup_method`, `funnel_step=signup_completed` |
| Auth/login | `user_authenticated` | `apps/core/signals.py` (`track_user_login`) | `auth_method`, `funnel_step=auth_completed`, `entrypoint=ui` |
| Auth failure | `user_auth_failed` | `apps/core/signals.py` (`track_user_login_failed`), `apps/api/views.py` (`create_project_v1` insufficient scope) | `reason`, `auth_method` (UI only), `required_scope` (API scope fail), `funnel_step=auth_failed`, `entrypoint` |
| Project create | `project_created` | `apps/core/views.py` (`create_project`), `apps/api/views.py` (`create_project_v1`) | `project_id`, `project_name`, `project_slug`, `funnel_step=project_created`, `entrypoint` |
| Project create fail | `project_create_failed` | `apps/core/views.py` (validation), `apps/api/views.py` (quota, slug, queue/internal failures) | `reason`, optional `validation_fields`, optional `error_type`, `funnel_step=project_create_failed`, `entrypoint` |

## Verification checklist

1. Start app with valid `POSTHOG_API_KEY` + `POSTHOG_HOST`.
2. Complete one test funnel flow in local or staging:
   - open landing/home (page view)
   - sign up or log in
   - create a project
3. In PostHog UI, filter recent events by your test user `distinct_id` and confirm all expected event names appear.

## Local validation evidence (automated)

Run targeted tests:

```bash
pytest apps/pages/tests.py apps/core/tests/test_projects.py apps/core/tests/test_signals.py apps/api/test_spec_001_contract.py
```

These tests assert event names/properties for signup, auth success/failure, and project creation success/failure (UI + API).

## Known gaps

- API requests that fail before principal resolution (missing/invalid API key) cannot be attributed to a user `profile_id`, so they are audited in `ProjectAPIAuditLog` but are not emitted as PostHog user events.

## Verification evidence (2026-03-11)

PostHog project `djass` (`id=339080`) was validated via API by emitting test funnel events and then reading event definitions.

Observed `last_seen_at` values:

- `user_signed_up` — `2026-03-11T14:17:31.782029Z`
- `user_authenticated` — `2026-03-11T14:17:34.027492Z`
- `project_created` — `2026-03-11T14:17:31.782029Z`
