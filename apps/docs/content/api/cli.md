---
title: Djass CLI
description: Generate and download a production-ready Django SaaS repository with the djass command.
keywords: Djass CLI, Go CLI, Django SaaS generator, AI agents
author: Rasul
---

# Generate repositories with the Djass CLI

Use the `djass` command to create a project on hosted Djass and receive the
generated repository in your local workspace. The CLI covers every Projects API
v1 operation and returns JSON that AI agents can consume directly.

## Install the CLI

Download the archive for your operating system from the Djass GitHub Releases
page, or install from source with Go 1.24 or later:

```bash
go install github.com/LVTD-LLC/djass/cli/cmd/djass@latest
```

Copy your Agent API key from [Account settings](https://djass.dev/settings),
then add it to your shell environment:

```bash
export DJASS_API_KEY="replace-with-your-key"
```

Treat this value as a secret. The CLI uses `https://djass.dev/api/v1` by
default and never prints the key.

## Generate a repository

Run one command to create, wait for, download, and extract a project:

```bash
djass generate \
  --name "Acme CRM" \
  --slug acme_crm \
  --set use_mcp=y \
  --set use_posthog=y \
  --output ./acme_crm
```

The output directory must be new or empty. The CLI refuses path traversal,
symbolic links, and other unsafe entries in downloaded ZIP files, and it does
not overwrite an existing repository.

Successful output is JSON:

```json
{
  "output": "/workspace/acme_crm",
  "project_id": 123,
  "size_bytes": 48291,
  "status": "ready"
}
```

## Discover current options

Fetch the live generator catalog before choosing feature flags:

```bash
djass options
```

Pass any supported option with repeatable `--set key=value` flags. This keeps
the CLI aligned when Djass adds generator options without requiring a new CLI
release.

For complete or generated request bodies, save the same JSON accepted by
`POST /projects` and pass it directly:

```bash
djass generate --payload project.json --output ./acme_crm
```

`--name`, `--slug`, and `--set` values override fields from the payload file.

## Use individual API operations

Each Projects API v1 operation has a direct command:

```bash
djass projects create --name "Acme CRM" --slug acme_crm --set use_mcp=y
djass projects list --status ready --limit 20
djass projects get 123
djass projects status 123
djass projects download 123 --output acme_crm.zip
```

Use these commands when an agent needs control over polling, artifact placement,
or a later download. Read [Projects API v1](/docs/api/projects-api-v1/) for the
response and error contracts.

## Configure staging or local Djass

Set a different API base URL when testing another deployment:

```bash
export DJASS_BASE_URL="https://staging.example.com/api/v1"
```

The CLI permits plain HTTP only for `localhost` and `127.0.0.1`, preventing an
API key from being sent to a remote server without transport encryption.
