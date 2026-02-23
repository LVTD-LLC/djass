---
title: Local Development
description: Run a generated Djass project locally with Docker Compose and the provided Makefile.
keywords: Djass, local setup, docker compose, django
author: Rasul
---

This guide gets a generated project running on your machine with all required services.

## Prerequisites

- Docker + Docker Compose
- `uv` installed for Python dependency management
- Node.js 18+ (if you run frontend commands directly)

## 1) Prepare environment variables

Copy `.env.example` to `.env` and update values you need:

```bash
cp .env.example .env
```

For local development, the defaults are usually enough to boot.

## 2) Start the stack

Use the provided Make target:

```bash
make serve
```

This starts:

- Postgres
- Redis
- Django backend (`:8000`)
- Django Q2 worker
- Frontend dev server (`:9091`)
- Mailhog (`:8025`)

## 3) Open the app

- App: `http://localhost:8000`
- Mail UI: `http://localhost:8025`

If the worker fails to connect to Redis during first boot, restart it:

```bash
make restart-worker
```

## 4) Useful commands

Run management commands via the Dockerized backend:

```bash
make manage migrate
make manage createsuperuser
make test
```

Open Django shell:

```bash
make shell
```

## 5) Sanity check after boot

Before you start feature work, verify:

- User signup/login works
- A project can be queued in Djass
- Worker logs show background tasks processing
- Static assets load correctly on pages

If all four pass, your environment is ready for development.
