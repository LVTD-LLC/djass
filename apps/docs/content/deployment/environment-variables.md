---
title: Environment Variables
description: Complete guide to configuring Djass environment variables.
keywords: Djass, environment variables, configuration, API keys
author: Rasul
---

This guide covers all environment variables needed to configure Djass.

## Required variables

These variables are essential for Djass to function:

### Core Django settings

**ENVIRONMENT**
- Environment mode for the application
- Values: `dev` or `prod`
- Set to `prod` for production deployments
- Set to `dev` for local development

**SECRET_KEY**
- Secret key for Django security features
- Must be kept confidential in production
- Generate one with: `python -c "import secrets; print(secrets.token_urlsafe(50))"`

**DEBUG**
- Set to `False` in production
- Set to `True` only for local development
- Never deploy to production with DEBUG=True

**SITE_URL**
- Full URL where your Djass instance is accessible
- Example: `https://yourdomain.com`
- Used for generating absolute URLs in emails and notifications

**ALLOWED_HOSTS**
- Comma-separated list of domains that can access your application
- Example: `yourdomain.com,www.yourdomain.com`
- Use `*` for testing only (not secure for production)

### Database configuration

**POSTGRES_DB**
- Name of the PostgreSQL database
- Example: `djass_db`

**POSTGRES_USER**
- PostgreSQL username
- Example: `djass_user`

**POSTGRES_PASSWORD**
- Password for your PostgreSQL database
- Use a strong, randomly generated password
- Generate one with: `openssl rand -base64 32`

**POSTGRES_HOST**
- PostgreSQL server hostname
- Example: `localhost` (for local), `db` (for Docker)

**POSTGRES_PORT**
- PostgreSQL server port
- Default: `5432`
- Optional - defaults to 5432 if not specified

### Redis configuration

**REDIS_HOST**
- Redis server hostname
- Example: `localhost` (for local), `redis` (for Docker)
- Default: `localhost`

**REDIS_PORT**
- Redis server port
- Default: `6379`

**REDIS_PASSWORD**
- Password for your Redis instance
- Use a strong, randomly generated password
- Generate one with: `openssl rand -base64 32`

**REDIS_DB**
- Redis database number
- Default: `0`

## Optional variables

These variables enhance functionality but aren't required:

### Logfire (Monitoring)

**LOGFIRE_TOKEN**
- Token for Logfire monitoring service
- Get your token from [Logfire](https://logfire.dev/)
- Used for application monitoring and logging
- Leave empty to disable Logfire

### Sentry (Error Tracking)

**SENTRY_DSN**
- DSN for Sentry error tracking
- Get your DSN from [Sentry](https://sentry.io/)
- Used for error monitoring and reporting
- Leave empty to disable Sentry

### PostHog (Analytics)

**POSTHOG_API_KEY**
- API key for PostHog analytics
- Get your key from [PostHog](https://posthog.com/)
- Used for product analytics and feature flags
- Leave empty to disable PostHog

### Buttondown (Email Newsletter)

**BUTTONDOWN_API_KEY**
- API key for Buttondown email service
- Get your key from [Buttondown](https://buttondown.email/)
- Used for managing email newsletters
- Leave empty to disable Buttondown integration

### Stripe (Payments)

**STRIPE_LIVE_SECRET_KEY**
- Stripe secret key for live/production mode
- Get from [Stripe Dashboard](https://dashboard.stripe.com/)
- Used for processing real payments
- Leave empty if only using test mode

**STRIPE_TEST_SECRET_KEY**
- Stripe secret key for test mode
- Get from [Stripe Dashboard](https://dashboard.stripe.com/)
- Used for testing payment flows
- Required for development

**DJSTRIPE_WEBHOOK_SECRET**
- Webhook signing secret from Stripe
- Get from Stripe webhook configuration
- Used to verify webhook authenticity
- Required for handling Stripe events

### Email configuration

Configure these to send emails from Djass (for notifications, password resets, etc.):

**MAILGUN_API_KEY**
- API key for Mailgun email service
- Get your key from [Mailgun](https://www.mailgun.com/)
- Used for sending transactional emails
- Leave empty to use console email backend (emails printed to console)

### OAuth/Social Authentication

**GITHUB_CLIENT_ID**
- GitHub OAuth application client ID
- Get from [GitHub Developer Settings](https://github.com/settings/developers)
- Used for GitHub social login
- Leave empty to disable GitHub authentication

**GITHUB_CLIENT_SECRET**
- GitHub OAuth application client secret
- Get from [GitHub Developer Settings](https://github.com/settings/developers)
- Required if GITHUB_CLIENT_ID is set

### Storage configuration

Configure these to use cloud storage for media files:

**AWS_ACCESS_KEY_ID**
- Your AWS access key ID
- Get from AWS IAM console
- Required for S3 storage

**AWS_SECRET_ACCESS_KEY**
- Your AWS secret access key
- Get from AWS IAM console
- Required for S3 storage

**AWS_STORAGE_BUCKET_NAME**
- Name of your S3 bucket
- Create bucket in AWS S3 console

**AWS_S3_REGION_NAME**
- AWS region for your S3 bucket
- Example: `us-east-1`

**AWS_S3_ENDPOINT_URL**
- Custom S3 endpoint URL (optional)
- Used for S3-compatible services (DigitalOcean Spaces, Wasabi, etc.)
- Leave empty for standard AWS S3

### MJML (Email Templates)

**MJML_URL**
- URL for MJML HTTP server
- Used for rendering MJML email templates to HTML
- Leave empty to use MJML command-line tool

### Logging

**DJANGO_LOG_LEVEL**
- Django logging level for production
- Values: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- Default: `INFO`
- Only applies when ENVIRONMENT=prod

## Getting the .env.example file

The complete `.env.example` file with all variables and detailed comments is available in the Djass repository.

Download it directly:

```bash
wget https://github.com/rasulkireev/djass/raw/main/.env.example -O .env
```

Or with curl:

```bash
curl -o .env https://github.com/rasulkireev/djass/raw/main/.env.example
```

This file includes all available options with explanations and example values.

## Security best practices

Follow these guidelines to keep your Djass installation secure:

**Never commit .env files**
- Add `.env` to your `.gitignore`
- Use environment variables or secret management systems for production

**Use strong passwords**
- Generate random passwords for database and Redis
- Use at least 32 characters for production passwords

**Keep secrets confidential**
- Don't share your SECRET_KEY or API keys
- Rotate keys immediately if exposed

**Use HTTPS in production**
- Set ALLOWED_HOSTS to specific domains only
- Configure SSL/TLS certificates for your domain
- Never set DEBUG=True in production

**Limit access**
- Use firewall rules to restrict database and Redis access
- Only expose necessary ports to the internet
- Use strong authentication for all services
