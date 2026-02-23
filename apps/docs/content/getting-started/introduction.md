---
title: Introduction
description: What Djass generates, who this documentation is for, and how to use it.
keywords: Djass, django-saas-starter, getting started
author: Rasul
---

Djass helps you generate a production-ready Django SaaS codebase from `django-saas-starter`.

The goal of this documentation is simple: help you understand the generated repository quickly, ship features safely, and avoid architecture drift.

## Who this documentation is for

Use these docs if you are:

- building a product with a generated Djass project,
- joining an existing generated codebase,
- extending the starter with custom business logic,
- or using AI tools to accelerate development.

## What you get from a generated project

By default, generated projects are opinionated around:

- **Django + PostgreSQL + Redis** for backend and data
- **Django Q2** for background jobs
- **Tailwind CSS** via the frontend build pipeline
- **App boundaries** under `apps/` (`core`, `api`, `pages`, optional `blog`, optional `docs`)
- **Configuration-first setup** through explicit environment variables and clear app boundaries

## Suggested reading path

1. **Local Development** — run the project end-to-end.
2. **Repository Structure** — understand where code should go.
3. **Background Jobs with Django Q2** — learn async execution patterns.
4. **Generator Options** — know what each scaffold toggle changes.
5. **Workflows** — add features safely and use AI effectively.

## Scope note

This documentation focuses on the generated project and the architecture choices Djass applies. It is intentionally practical and implementation-oriented.
