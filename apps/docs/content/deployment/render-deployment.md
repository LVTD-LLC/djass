---
title: Render Deployment
description: Deploy Djass on Render using the included render.yaml blueprint.
keywords: Djass, Render, deployment, django
author: Rasul
---

Djass includes a `render.yaml` blueprint for deploying web, workers, PostgreSQL, and Redis.

## Quick start

Use the deploy button:

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/gregagi/djass)

## What Render creates

From `render.yaml`, Render provisions:

- `djass-web` (Django web service)
- `djass-workers` (Django Q2 worker process)
- `djass-db` (PostgreSQL)
- `djass-redis` (Redis)
- shared env var group (`app-env`)

## Required setup after provisioning

1. Open env vars and confirm required values from the [Environment Variables](/docs/deployment/environment-variables/) guide.
2. Set `SITE_URL` to the real public URL if auto-generated value is incorrect.
3. Add API keys/integrations only if you need them.
4. Trigger a deploy for both web and worker services.

## Important production notes

- Worker service is implemented as a web service on free tiers (with a lightweight HTTP server for health checks).
- If you keep local filesystem media storage, uploaded/generated files are ephemeral.
  - Prefer S3-compatible storage for persistent artifacts.
- Run on paid plans for better stability if you process heavy background workloads.

## Post-deploy checklist

- App loads at `/`
- Signup/login flow works
- Background generation jobs transition from queued → ready
- Artifact download works
- Worker logs show task execution

If any of these fail, compare web vs worker env values first (especially DB/Redis/auth keys).
