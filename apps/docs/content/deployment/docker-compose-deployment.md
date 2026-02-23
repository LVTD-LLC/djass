---
title: Docker Compose Deployment
description: Deploy Djass on your own server using docker-compose-prod.yml.
keywords: Djass, docker compose, self-hosting, deployment
author: Rasul
---

Use this path when you want full control over infrastructure.

## Prerequisites

- Linux server with Docker + Docker Compose plugin
- Domain name (recommended)
- Reverse proxy (Nginx, Caddy, or similar)
- `.env` file with production values

## 1) Prepare deployment files

On your server:

```bash
mkdir -p /opt/djass
cd /opt/djass
```

Copy these files from the repo:

- `.env.example` (rename to `.env` and edit)
- `docker-compose-prod.yml`

Then configure `.env` using the [Environment Variables](/docs/deployment/environment-variables/) guide.

## 2) Start services

```bash
docker compose -f docker-compose-prod.yml -p djass up -d --remove-orphans
```

This boots:

- PostgreSQL
- Redis
- Backend container
- Worker container

## 3) Verify health

```bash
docker compose -f docker-compose-prod.yml -p djass ps
docker compose -f docker-compose-prod.yml -p djass logs backend --tail=200
docker compose -f docker-compose-prod.yml -p djass logs workers --tail=200
```

You should see migrations completed and worker ready to process tasks.

## 4) Expose the app

Backend listens on host port `8000` by default (`8000:80`).

Recommended: put a reverse proxy in front and terminate TLS there.

## 5) Persistence and artifacts

- Postgres and Redis data persist through Docker volumes.
- Generated artifacts/media require persistent storage strategy:
  - mount persistent path for `MEDIA_ROOT`, or
  - configure S3-compatible storage variables.

## Updating deployments

Pull latest repo/images, then recreate services:

```bash
docker compose -f docker-compose-prod.yml -p djass pull
docker compose -f docker-compose-prod.yml -p djass up -d --remove-orphans
```

## Common issues

- **Worker idle / tasks not running** → verify Redis credentials match across services.
- **500 errors on startup** → check DB env vars and migration logs.
- **Missing uploaded/generated files** → configure persistent media storage.
