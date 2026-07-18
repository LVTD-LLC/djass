# Djass CLI

The Go-based `djass` command generates a Django SaaS repository through the
hosted Djass API. It exposes every Projects API v1 operation and prints JSON by
default so people and AI agents can use the same interface.

## Install

Install the latest release archive from the repository's GitHub Releases page,
or install from source with Go 1.24 or later:

```bash
go install github.com/LVTD-LLC/djass/cli/cmd/djass@latest
```

Set your API key before using project commands:

```bash
export DJASS_API_KEY="replace-with-your-key"
```

## Generate a repository

```bash
djass generate \
  --name "Acme CRM" \
  --slug acme_crm \
  --set use_mcp=y \
  --set use_posthog=y \
  --output ./acme_crm
```

The command queues generation on `https://djass.dev`, polls until the artifact
is ready, downloads it, validates every ZIP path, and extracts it into a new or
empty directory. It never overwrites an existing repository.

Use a JSON payload when an agent already has the complete API request:

```bash
djass generate --payload project.json --output ./acme_crm
```

Run `djass options` to retrieve the live generator catalog before choosing
feature flags.

## API parity commands

```bash
djass options
djass projects create --name "Acme CRM" --slug acme_crm --set use_mcp=y
djass projects list --status ready
djass projects get 123
djass projects status 123
djass projects download 123 --output acme_crm.zip
```

Use `DJASS_BASE_URL` or global `--base-url` only for staging or local Djass
instances. Non-local HTTP URLs are rejected so API keys are not sent over
unencrypted connections.
