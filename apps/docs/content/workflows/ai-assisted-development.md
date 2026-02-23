---
title: AI-Assisted Development
description: How to use AI tools productively and safely with generated Djass projects.
keywords: Djass, AI coding assistant, workflow, code quality
author: Rasul
---

AI tools can accelerate implementation, but they need project context and boundaries.

## Give AI high-quality context

Before asking for code, provide:

- the exact files to touch,
- architectural constraints (app boundaries under `apps/`),
- the expected user outcome,
- and non-goals.

Better context produces smaller, safer patches.

## Preferred prompt shape

Use prompts like:

1. **Goal:** what user job should work after the change.
2. **Scope:** allowed files/folders.
3. **Constraints:** coding style, architecture, no breaking changes.
4. **Acceptance criteria:** what must be true when done.

## Guardrails to enforce

- Keep business logic out of templates.
- Don’t mix API and page concerns in the same module.
- Use background tasks for long-running work.
- Preserve existing env variable names unless migration is explicit.
- Avoid speculative dependency additions.

## Review checklist for AI-generated patches

- Does code follow the repository boundaries?
- Are failure paths handled and logged?
- Are new settings/config documented?
- Are migrations/tests included when required?
- Can another dev understand the change without extra context?

## Practical workflow

1. Ask AI for a small first patch.
2. Review and run checks.
3. Iterate in narrow increments.
4. Update docs before merge.

Small iterations beat one giant AI-generated diff every time.
