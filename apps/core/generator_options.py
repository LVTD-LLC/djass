from collections import OrderedDict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

COOKIECUTTER_OPTIONS_SOURCE_URL = (
    "https://raw.githubusercontent.com/LVTD-LLC/django-saas-starter/main/cookiecutter.json"
)
PROJECT_SLUG_DEFAULT = (
    "{{ cookiecutter.project_name.lower()"
    "|replace(' ', '_')"
    "|replace('-', '_')"
    "|replace('.', '_')"
    "|trim() }}"
)
CAPROVER_APP_NAME_DEFAULT = "{{ cookiecutter.project_slug|replace('_', '-') }}"


@dataclass(frozen=True)
class GeneratorField:
    key: str
    default: Any
    label: str
    category: str | None = None
    is_feature_flag: bool = False

    def as_option_payload(self) -> dict[str, str]:
        return {
            "key": self.key,
            "label": self.label,
            "default": str(self.default),
            "category": self.category or "other",
        }


@dataclass(frozen=True)
class GeneratorOptionCategory:
    key: str
    label: str


@dataclass(frozen=True)
class CookiecutterDrift:
    added: tuple[str, ...]
    removed: tuple[str, ...]
    changed: tuple[str, ...]

    @property
    def has_drift(self) -> bool:
        return bool(self.added or self.removed or self.changed)

    def summary(self) -> str:
        details = ["Cookiecutter option catalog is out of date."]
        if self.added:
            details.append(f"Added upstream: {', '.join(self.added)}")
        if self.removed:
            details.append(f"Removed upstream: {', '.join(self.removed)}")
        if self.changed:
            details.append(f"Changed defaults: {', '.join(self.changed)}")
        return "\n".join(details)


@dataclass(frozen=True)
class GeneratorOptionCatalog:
    fields: tuple[GeneratorField, ...]
    categories: tuple[GeneratorOptionCategory, ...]

    @property
    def defaults(self) -> OrderedDict[str, Any]:
        return OrderedDict((field.key, field.default) for field in self.fields)

    @property
    def feature_flags(self) -> tuple[GeneratorField, ...]:
        return tuple(field for field in self.fields if field.is_feature_flag)

    @property
    def feature_flag_keys(self) -> list[str]:
        return [field.key for field in self.feature_flags]

    @property
    def category_labels(self) -> OrderedDict[str, str]:
        return OrderedDict((category.key, category.label) for category in self.categories)

    def get_field(self, key: str) -> GeneratorField:
        try:
            return next(field for field in self.fields if field.key == key)
        except StopIteration as exc:
            raise KeyError(f"Unknown generator field: {key}") from exc

    def get_option_label(self, key: str) -> str:
        return self.get_field(key).label

    def get_option_category_key(self, key: str) -> str:
        return self.get_field(key).category or "other"

    def get_options(self) -> list[dict[str, str]]:
        return [field.as_option_payload() for field in self.feature_flags]

    def get_option_groups(self) -> list[dict[str, Any]]:
        groups = OrderedDict(
            (
                category.key,
                {
                    "key": category.key,
                    "label": category.label,
                    "options": [],
                },
            )
            for category in self.categories
        )
        for option in self.get_options():
            groups[option["category"]]["options"].append(option)
        return [group for group in groups.values() if group["options"]]

    def as_api_payload(self) -> dict[str, Any]:
        return {
            "defaults": self.defaults,
            "groups": self.get_option_groups(),
        }

    def as_mcp_payload(self) -> dict[str, Any]:
        return self.as_api_payload()

    def drift_from_cookiecutter(self, cookiecutter_defaults: dict[str, Any]) -> CookiecutterDrift:
        local_defaults = OrderedDict(
            (key, value) for key, value in self.defaults.items() if not key.startswith("_")
        )
        cookiecutter_defaults = OrderedDict(
            (key, value) for key, value in cookiecutter_defaults.items() if not key.startswith("_")
        )
        local_keys = set(local_defaults)
        source_keys = set(cookiecutter_defaults)
        return CookiecutterDrift(
            added=tuple(sorted(source_keys - local_keys)),
            removed=tuple(sorted(local_keys - source_keys)),
            changed=tuple(
                sorted(
                    key
                    for key in local_keys & source_keys
                    if local_defaults[key] != cookiecutter_defaults[key]
                )
            ),
        )


GENERATOR_OPTION_CATALOG = GeneratorOptionCatalog(
    fields=(
        GeneratorField("project_name", "My Awesome Project", "Project Name"),
        GeneratorField(
            "project_slug",
            PROJECT_SLUG_DEFAULT,
            "Project Slug",
        ),
        GeneratorField(
            "caprover_app_name",
            CAPROVER_APP_NAME_DEFAULT,
            "CapRover App Name",
        ),
        GeneratorField("repo_url", "https://github.com/cookiecutter/cookiecutter", "Repo URL"),
        GeneratorField(
            "project_description",
            "This project will help you be the best in the world",
            "Project Description",
        ),
        GeneratorField("author_name", "Jane Doe", "Author Name"),
        GeneratorField("author_email", "janedoe@example.com", "Author Email"),
        GeneratorField("author_url", "", "Author URL"),
        GeneratorField("project_main_color", "green", "Project Main Color"),
        GeneratorField("use_posthog", "y", "Use PostHog", "monitoring", True),
        GeneratorField("use_chatwoot", "n", "Use Chatwoot", "cx", True),
        GeneratorField("use_s3", "y", "Use S3", "storage", True),
        GeneratorField("use_stripe", "y", "Use Stripe", "commerce", True),
        GeneratorField("use_sentry", "y", "Use Sentry", "monitoring", True),
        GeneratorField("generate_blog", "y", "Generate Blog", "content", True),
        GeneratorField("generate_docs", "y", "Generate Docs", "content", True),
        GeneratorField("use_mjml", "y", "Use MJML", "cx", True),
        GeneratorField("use_ai", "y", "Use AI", "ai", True),
        GeneratorField("use_logfire", "y", "Use Logfire", "monitoring", True),
        GeneratorField("use_healthchecks", "y", "Use Healthchecks", "monitoring", True),
        GeneratorField("use_apprise", "n", "Use Apprise", "monitoring", True),
        GeneratorField("use_mcp", "n", "Use MCP", "ai", True),
        GeneratorField("use_ci", "y", "Use CI", "delivery", True),
        GeneratorField("use_digitalocean", "n", "Use DigitalOcean", "delivery", True),
    ),
    categories=(
        GeneratorOptionCategory("monitoring", "Monitoring"),
        GeneratorOptionCategory("cx", "CX"),
        GeneratorOptionCategory("commerce", "Commerce"),
        GeneratorOptionCategory("storage", "Storage"),
        GeneratorOptionCategory("content", "Content"),
        GeneratorOptionCategory("ai", "AI"),
        GeneratorOptionCategory("delivery", "Delivery"),
        GeneratorOptionCategory("other", "Other"),
    ),
)


def get_generator_option_catalog() -> GeneratorOptionCatalog:
    return GENERATOR_OPTION_CATALOG


def get_generator_options() -> list[dict[str, str]]:
    return GENERATOR_OPTION_CATALOG.get_options()


def get_generator_option_groups() -> list[dict[str, Any]]:
    return GENERATOR_OPTION_CATALOG.get_option_groups()


def get_option_label(key: str) -> str:
    return GENERATOR_OPTION_CATALOG.get_option_label(key)


def get_option_category_key(key: str) -> str:
    return GENERATOR_OPTION_CATALOG.get_option_category_key(key)


def diff_cookiecutter_defaults(cookiecutter_defaults: dict[str, Any]) -> CookiecutterDrift:
    return GENERATOR_OPTION_CATALOG.drift_from_cookiecutter(cookiecutter_defaults)


def iter_cookiecutter_defaults() -> Iterable[tuple[str, Any]]:
    return GENERATOR_OPTION_CATALOG.defaults.items()


COOKIECUTTER_FIELD_DEFAULTS = GENERATOR_OPTION_CATALOG.defaults
MODULE_FLAG_KEYS = GENERATOR_OPTION_CATALOG.feature_flag_keys
