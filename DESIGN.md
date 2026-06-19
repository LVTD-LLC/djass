# DESIGN.md

UI and design guidance for AI agents working on Djass.

## Design Direction

Djass is a compact operational SaaS tool for generating and managing project artifacts. The UI should feel clear, dense, and work-focused rather than like a marketing-only landing page. Default to fast scanning, predictable controls, and visible system state.

## Architecture

- Use Django templates as the primary UI layer.
- Use Tailwind utilities and the `.dj-*` primitives already defined in `frontend/src/styles/index.css`.
- Use HTMX only for fresh server-rendered HTML.
- Use Alpine.js or existing browser modules only for local UI state such as dropdowns, theme toggles, copy buttons, modals, feedback, and settings cache.
- Do not add a frontend framework, bundler, or SPA route layer.

## Tokens and Primitives

Design tokens live in `frontend/src/styles/index.css`.

Use CSS variables:

- Background and panels: `--dj-bg`, `--dj-bg-muted`, `--dj-panel`, `--dj-panel-solid`, `--dj-panel-elevated`
- Text: `--dj-text`, `--dj-heading`, `--dj-muted`, `--dj-soft`
- Borders: `--dj-border`, `--dj-border-strong`
- Accent and state: `--dj-accent`, `--dj-accent-strong`, `--dj-accent-soft`, `--dj-success`, `--dj-warning`, `--dj-danger`

Use existing primitives:

- Layout: `.dj-page-shell`, `.dj-main`, `.dj-container`, `.dj-container-narrow`, `.dj-container-wide`
- Navigation: `.dj-nav`, `.dj-brand`, `.dj-nav-link`, `.dj-nav-link-active`, `.dj-icon-button`, `.dj-menu-button`
- Buttons: `.dj-button`, `.dj-button-primary`, `.dj-button-secondary`, `.dj-button-subtle`, `.dj-button-danger`, `.dj-button-warning`
- Status: `.dj-pill`, `.dj-pill-accent`, `.dj-pill-success`, `.dj-pill-warning`, `.dj-pill-danger`
- Surfaces: `.dj-panel`, `.dj-panel-solid`, `.dj-feature-card`, `.dj-alert`
- Content: `.dj-kicker`, `.dj-section-title`, `.dj-section-copy`, `.dj-prose`, `.dj-table`, `.dj-tag-list`, `.dj-stack-tag`

## Visual Rules

- Keep border radius at `4px`, matching the existing system.
- Keep letter spacing at `0`; `index.css` explicitly normalizes Tailwind tracking utilities.
- Prefer panels, tables, dense grids, pills, and action rows for app pages.
- Avoid nested cards. A page section can be a panel; repeated items inside it should be simple rows or grid cells.
- Avoid decorative gradient blobs, orbs, and large stock-like hero imagery.
- Preserve light/dark theme support. Add both normal and `.dark` token behavior when a new global color is needed.
- Keep states explicit: queued/generating uses warning, ready uses success, failed/destructive uses danger.
- Make long project names, slugs, artifact paths, and SHA-256 values wrap safely with `break-all` or constrained monospace blocks.

## Interaction Rules

- Form submissions must work without relying on JavaScript-only validation.
- Buttons and interactive icons need visible focus states.
- Copy interactions should use the existing clipboard patterns in `frontend/src/js/modules/copy.js`.
- Theme behavior should stay in `frontend/src/js/modules/theme.js`.
- User settings cache behavior should stay in `frontend/src/js/modules/user-settings.js`.
- Destructive actions should require clear confirmation, following the delete account modal pattern in `frontend/templates/pages/user-settings.html`.

## Page Patterns

- Dashboard: status-first artifact management, compact action clusters, table/list views for generated projects.
- Project create: grouped fieldsets from `ProjectCreateForm.generator_option_groups`; do not hard-code generator flag groups in templates.
- Project detail: show saved payload, status, artifact metadata, failure details, and retry/download actions.
- Docs: markdown content rendered through `.dj-prose`, navigation from `apps/docs/navigation.yaml`, user-first writing per `apps/docs/AGENTS.md`.
- Marketing/landing: product promise can be more expressive, but the first viewport should still make "Djass generates agent-ready Django SaaS repos" obvious.

## Verification

After frontend changes:

```bash
npm run build
npm run lint
uv run python manage.py check
```

For template or copy changes, run targeted pytest files that cover the affected page or docs workflow.
