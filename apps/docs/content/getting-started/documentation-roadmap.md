---
title: Documentation Roadmap
description: Strategy for documenting generated Djass projects so teams can onboard, ship, and scale faster.
keywords: Djass, documentation strategy, roadmap
author: Rasul
---

This page defines the documentation strategy for generated Djass projects.

## Goals

- Reduce onboarding time for new developers.
- Make architecture decisions explicit and repeatable.
- Provide copy-paste-ready workflows for common product tasks.
- Make AI-assisted development safe and consistent.

## Primary audiences

1. **Founder-developers** shipping quickly with limited ops bandwidth.
2. **Early teammates** joining an existing generated codebase.
3. **AI-assisted builders** using coding agents to move faster.

## Documentation pillars

- **Getting Started:** boot locally and understand the happy path.
- **Architecture:** explain project shape and why decisions were made.
- **Features:** describe what each generator toggle changes.
- **Workflows:** show how to implement and ship changes safely.
- **Configuration:** keep runtime setup explicit and predictable.

## What “good” looks like

Documentation should be:

- task-oriented ("do X"),
- explicit about file locations and commands,
- honest about trade-offs,
- and maintained as part of normal feature delivery.

## Maintenance process

Use this lightweight rule:

- If a PR changes architecture, setup, configuration, or expected workflow, update docs in the same PR.
- Keep pages short and link outward instead of building huge monolith pages.
- Prefer concrete examples from this repository over generic framework advice.

## Next planned expansions

- API conventions and versioning guidance (`apps/api`)
- Testing strategy and CI expectations
- Runtime configuration patterns and secret-management examples
- Contributor playbook for teams using coding agents
