from collections import OrderedDict

COOKIECUTTER_FIELD_DEFAULTS = OrderedDict(
    [
        ("project_name", "My Awesome Project"),
        ("project_slug", "my_awesome_project"),
        ("repo_url", "https://github.com/cookiecutter/cookiecutter"),
        ("project_description", "This project will help you be the best in the world"),
        ("author_name", "Jane Doe"),
        ("author_email", "janedoe@example.com"),
        ("author_url", ""),
        ("project_main_color", "green"),
        ("use_posthog", "y"),
        ("use_chatwoot", "n"),
        ("use_buttondown", "y"),
        ("use_s3", "y"),
        ("use_stripe", "y"),
        ("use_sentry", "y"),
        ("generate_blog", "y"),
        ("generate_docs", "y"),
        ("use_mjml", "y"),
        ("use_ai", "y"),
        ("use_logfire", "y"),
        ("use_healthchecks", "y"),
        ("use_mcp", "n"),
        ("use_ci", "y"),
    ]
)

MODULE_FLAG_LABELS = OrderedDict(
    [
        ("use_posthog", "Use PostHog"),
        ("use_chatwoot", "Use Chatwoot"),
        ("use_buttondown", "Use Buttondown"),
        ("use_s3", "Use S3"),
        ("use_stripe", "Use Stripe"),
        ("use_sentry", "Use Sentry"),
        ("generate_blog", "Generate Blog"),
        ("generate_docs", "Generate Docs"),
        ("use_mjml", "Use MJML"),
        ("use_ai", "Use AI"),
        ("use_logfire", "Use Logfire"),
        ("use_healthchecks", "Use Healthchecks"),
        ("use_mcp", "Use MCP"),
        ("use_ci", "Use CI"),
    ]
)

MODULE_FLAG_KEYS = list(MODULE_FLAG_LABELS.keys())
