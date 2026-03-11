---
title: PostHog Funnel Analytics
description: Djass PostHog funnel event mapping, setup, and verification runbook.
keywords: Djass, PostHog, analytics, funnel, checkout
author: Rasul
---

## Goal

Track core funnel behavior reliably in PostHog:

1. page view
2. signup/auth
3. project create
4. checkout start / success / fail

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
| Auth/login | `user_authenticated` | `apps/core/signals.py` (`track_user_login`) | `auth_method`, `funnel_step=auth_completed` |
| Project create | `project_created` | `apps/core/views.py` (`create_project`) | `project_id`, `project_name`, `project_slug`, `funnel_step=project_created` |
| Checkout start | `checkout_started` | `apps/core/views.py` (`create_checkout_session`) | `plan`, `price_id`, `checkout_id`, `funnel_step=checkout_started` |
| Checkout success | `checkout_succeeded` | `apps/core/stripe_webhooks.py` (`handle_checkout_completed`) | `checkout_id`, `payment_intent`, `amount`, `currency`, `price_id`, `plan`, `funnel_step=checkout_succeeded`, `stripe_event_id` |
| Checkout fail | `checkout_failed` | `apps/pages/views.py` (canceled/failed return), `apps/core/views.py` (Stripe setup/session exceptions) | `reason`, optional `error_type`, `plan`, `funnel_step=checkout_failed` |

## Verification checklist

1. Start app with valid `POSTHOG_API_KEY` + `POSTHOG_HOST`.
2. Complete one test funnel flow in local or staging:
   - open landing/home (page view)
   - sign up or log in
   - create a project
   - start checkout (and either cancel or complete with Stripe test card)
3. In PostHog UI, filter recent events by your test user `distinct_id` and confirm all expected event names appear.
4. Confirm checkout success is only emitted on Stripe webhook `checkout.session.completed` with paid status.

## Local validation evidence (automated)

Run targeted tests:

```bash
pytest apps/pages/tests.py apps/core/tests/test_checkout_session.py apps/core/tests/test_projects.py apps/core/tests/test_stripe_webhooks.py apps/core/tests/test_signals.py
```

These tests assert event names/properties for signup, auth, project creation, checkout start, checkout success, and checkout failure paths.

## Verification evidence (2026-03-11)

PostHog project `djass` (`id=339080`) was validated via API by emitting test funnel events and then reading event definitions.

Observed `last_seen_at` values:

- `user_signed_up` — `2026-03-11T14:17:31.782029Z`
- `user_authenticated` — `2026-03-11T14:17:34.027492Z`
- `project_created` — `2026-03-11T14:17:31.782029Z`
- `checkout_started` — `2026-03-11T14:17:32.933335Z`
- `checkout_failed` — `2026-03-11T14:17:30.706677Z`
- `checkout_succeeded` — `2026-03-11T14:17:34.457525Z`
