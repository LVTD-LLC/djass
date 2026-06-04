# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project tries to adhere to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Types of changes

**Added** for new features.
**Changed** for changes in existing functionality.
**Deprecated** for soon-to-be removed features.
**Removed** for now removed features.
**Fixed** for any bug fixes.
**Security** in case of vulnerabilities.


## [Unreleased]

### Added
- Djass SVG logo assets with refreshed PNG and favicon fallbacks.
- Login now accepts either username or email address.
- Copyable Agent API key section on the user settings page so users can give their key to coding agents.
- Production Sentry observability configuration for Djass errors, logs, traces, profiles, Django/Redis/cache spans, and AI-agent spans via Pydantic AI/OpenAI/Anthropic/Google GenAI integrations.
- Project dashboard flow for generated codebases: create project, queued generation status, retry, and ZIP download actions.
- New `Project` and `ProjectArtifact` models for persisted generation history and downloadable artifacts.
- Background generation task scaffold (`django-q2`) for cookiecutter execution and artifact packaging.
- Initial tests for project creation queueing, dashboard history rendering, and download authorization.
- Passkey authentication support (signup + login) using `django-allauth` MFA/WebAuthn.
- Spec 001 (`/api/v1/projects`) contract implementation for agent-operable create/list/get/status endpoints with canonical response fields.
- Spec 001 agent artifact download endpoint at `GET /api/v1/projects/{project_id}/download` for retrieving generated ZIPs with API keys.
- Contract test suite for Spec 001 covering auth, happy path creation, pagination/filtering, and representative failure modes (`quota_exceeded`, `retryable_error`).
- Versioned API contract documentation: `apps/docs/content/api/spec-001-agent-project-api-contract.md`.
- Stable error taxonomy fields in API responses: `error.category` (`validation|auth|quota|retryable|internal`) and `error.retryable`.
- Hosted `/mcp` endpoint with authenticated MCP-style tools for generation options, project creation, status polling, and generated ZIP download links.

### Fixed
- Deployment workflows now use lowercase GHCR image names after the repository move to `LVTD-LLC`.
- Temporarily disabled passkey-based signup and login paths while passkey auth is unstable; auth pages now hide passkey actions and `/accounts/signup/passkey/` is no longer exposed.
- Signup now uses a single password field while preserving django-allauth password validation and updated coverage for the streamlined flow.
- Mailgun sender-domain default now matches the verified Djass Mailgun domain (`mg.djass.dev`) to prevent `401 Forbidden` during signup confirmation sends when env overrides are not set.

### Changed
- Signup/email verification flow now allows immediate post-signup dashboard access (`ACCOUNT_EMAIL_VERIFICATION=optional`) while still sending verification emails.
- Switched email verification to link-based confirmation (`ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED=False`) with one-click confirm on GET.
- Added a branded `account/verification_sent.html` so fallback verification-sent UX matches Djass styling instead of the default allauth page.

### Changed
- Free access page copy now frames Djass as a feedback-led Django SaaS starter workflow for founders, builders, and teams.
- Blog list/detail pages no longer render top tag chips in the page header/card metadata, reducing visual clutter while keeping layout spacing intact.
- API key authentication for v1 project endpoints now accepts `X-API-Key` and `Authorization` header formats in addition to `?api_key=` query fallback.
- Contract-level error payload for Spec 001 standardized to `{ "error": { "code", "message", "details" } }`.
- Spec 001 keeps async generation behavior (create returns queued project; status endpoint is canonical poll target).
- Spec 001 returns 404 when project id is not found for the authenticated owner scope.
- Project generation now normalizes cookiecutter payloads against deterministic defaults before render.
- Generated repositories now include standardized `project-metadata.json` and retrieval-friendly `djass-manifest.json`.
- ZIP artifact creation now uses deterministic file ordering and fixed archive entry timestamps.
- Generation failures now persist more actionable diagnostics in `Project.error_message`.
- Landing page “How it works” section now spells out the UI flow and API flow separately, then explains the background generation and handoff steps in scan-friendly cards.
- Free access page and workflow copy now remove the legacy “Need full control?” bridge in favor of product-first messaging that points builders to the open-source baseline without agency framing.

### Fixed
- Signup no longer fails account creation when welcome/confirmation email delivery errors during registration; the failure is logged, the user gets a retry warning, and explicit resend failures still surface normally.

### Changed
- Home page converted from placeholder to a functional project dashboard with generation status/actions.
- Landing and free access copy now position Djass as a product-first Django SaaS starter workflow for founders and teams instead of agency-focused service language.
- Landing page CTA copy now uses clearer action labels and helper text that explains exactly where each homepage CTA goes.
- Added `COOKIECUTTER_TEMPLATE_PATH` setting for configurable template source path.
- Generation now uses Cookiecutter Python API first with CLI fallback for resilience.
- Media/artifact storage path is now configurable via `MEDIA_ROOT` and defaults to `/data/media` in production for persistent volumes.
- Make shared footer and auth email footer years render dynamically instead of hardcoding 2025.
