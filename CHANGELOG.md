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
- Project dashboard flow for generated codebases: create project, queued generation status, retry, and ZIP download actions.
- New `Project` and `ProjectArtifact` models for persisted generation history and downloadable artifacts.
- Background generation task scaffold (`django-q2`) for cookiecutter execution and artifact packaging.
- Initial tests for project creation queueing, dashboard history rendering, and download authorization.

### Changed
- Home page converted from placeholder to a functional project dashboard with generation status/actions.
- Added `COOKIECUTTER_TEMPLATE_PATH` setting for configurable template source path.
- Generation now uses Cookiecutter Python API first with CLI fallback for resilience.
- Media/artifact storage path is now configurable via `MEDIA_ROOT` and defaults to `/data/media` in production for persistent volumes.
