# Frontend assets

This directory contains Webpack/Tailwind assets and Django template integrations used by Djass.

## Available commands

### `npm run start`

Starts the frontend dev server with live reloading (default port `9091`).

### `npm run watch`

Runs Webpack in watch mode.

### `npm run build`

Builds production frontend assets.

## Typical workflow

For full local development, use the repo root command:

```bash
make serve
```

This starts backend, workers, and frontend together with the expected local stack.
