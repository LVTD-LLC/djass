import json
from collections import OrderedDict
from pathlib import Path
from typing import Any

COOKIECUTTER_OPTIONS_SOURCE_URL = (
    "https://raw.githubusercontent.com/LVTD-LLC/django-saas-starter/main/cookiecutter.json"
)
COOKIECUTTER_OPTIONS_PATH = Path(__file__).resolve().parent / "data" / "cookiecutter-options.json"

CORE_FIELD_KEYS = [
    "project_name",
    "project_slug",
    "repo_url",
    "project_description",
    "author_name",
    "author_email",
    "author_url",
    "project_main_color",
]

OPTION_CATEGORY_LABELS = OrderedDict(
    [
        ("monitoring", "Monitoring"),
        ("cx", "CX"),
        ("payments", "Payments"),
        ("storage", "Storage"),
        ("content", "Content"),
        ("ai", "AI"),
        ("delivery", "Delivery"),
        ("other", "Other"),
    ]
)

OPTION_METADATA = {
    "use_posthog": {"label": "Use PostHog", "category": "monitoring"},
    "use_sentry": {"label": "Use Sentry", "category": "monitoring"},
    "use_logfire": {"label": "Use Logfire", "category": "monitoring"},
    "use_healthchecks": {"label": "Use Healthchecks", "category": "monitoring"},
    "use_chatwoot": {"label": "Use Chatwoot", "category": "cx"},
    "use_buttondown": {"label": "Use Buttondown", "category": "cx"},
    "use_mjml": {"label": "Use MJML", "category": "cx"},
    "use_stripe": {"label": "Use Stripe", "category": "payments"},
    "use_s3": {"label": "Use S3", "category": "storage"},
    "generate_blog": {"label": "Generate Blog", "category": "content"},
    "generate_docs": {"label": "Generate Docs", "category": "content"},
    "use_ai": {"label": "Use AI", "category": "ai"},
    "use_mcp": {"label": "Use MCP", "category": "ai"},
    "use_ci": {"label": "Use CI", "category": "delivery"},
}


def _load_cookiecutter_defaults() -> OrderedDict[str, Any]:
    try:
        raw_options = json.loads(
            COOKIECUTTER_OPTIONS_PATH.read_text(encoding="utf-8"),
            object_pairs_hook=OrderedDict,
        )
    except OSError as exc:
        raise RuntimeError(f"Cookiecutter option snapshot is missing: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Cookiecutter option snapshot is invalid JSON: {exc}") from exc

    if not isinstance(raw_options, OrderedDict):
        raise RuntimeError("Cookiecutter option snapshot must be a JSON object.")
    return raw_options


def serialize_cookiecutter_defaults(defaults: dict[str, Any]) -> str:
    return json.dumps(defaults, indent=2) + "\n"


def _humanize_option_key(key: str) -> str:
    words = key.removeprefix("use_").removeprefix("generate_").split("_")
    prefix = "Generate" if key.startswith("generate_") else "Use"
    label = " ".join(word.upper() if len(word) <= 3 else word.title() for word in words)
    return f"{prefix} {label}"


def get_option_label(key: str) -> str:
    return OPTION_METADATA.get(key, {}).get("label", _humanize_option_key(key))


def get_option_category_key(key: str) -> str:
    category = OPTION_METADATA.get(key, {}).get("category", "other")
    if category not in OPTION_CATEGORY_LABELS:
        return "other"
    return category


def get_generator_options() -> list[dict[str, str]]:
    return [
        {
            "key": key,
            "label": get_option_label(key),
            "default": COOKIECUTTER_FIELD_DEFAULTS[key],
            "category": get_option_category_key(key),
        }
        for key in MODULE_FLAG_KEYS
    ]


def get_generator_option_groups() -> list[dict[str, Any]]:
    groups = OrderedDict(
        (
            key,
            {
                "key": key,
                "label": label,
                "options": [],
            },
        )
        for key, label in OPTION_CATEGORY_LABELS.items()
    )
    for option in get_generator_options():
        groups[option["category"]]["options"].append(option)
    return [group for group in groups.values() if group["options"]]


COOKIECUTTER_FIELD_DEFAULTS = _load_cookiecutter_defaults()
MODULE_FLAG_KEYS = [
    key
    for key, value in COOKIECUTTER_FIELD_DEFAULTS.items()
    if key not in CORE_FIELD_KEYS and value in {"y", "n"}
]
