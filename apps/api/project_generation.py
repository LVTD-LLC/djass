from functools import lru_cache
from typing import Any

from apps.core.generator_options import get_generator_option_catalog

PROJECT_CREATE_DISCOVERY_PROMPT = """
Before calling Djass to generate a project, collect the project basics and every current
Djass generation option. Ask concise follow-up questions for any option the user did not
specify. If the user explicitly says to decide for them, choose sensible defaults and
state those choices before generating.
""".strip()

FIELD_DESCRIPTIONS = {
    "project_name": "Human-readable name for the generated Django SaaS project.",
    "project_slug": "Lowercase package/repo slug. Djass normalizes it to a Python-safe slug.",
    "caprover_app_name": "Optional CapRover app name for deployment metadata.",
    "project_description": "One-sentence description used in generated metadata and docs.",
    "repo_url": "Optional repository URL to place in generated metadata.",
    "author_name": "Person or organization that owns the project.",
    "author_email": "Contact email. Defaults to the authenticated Djass user's email when omitted.",
    "author_url": "Optional website for the author or organization.",
    "project_main_color": (
        "Tailwind/brand color name used by the template, for example green, blue, purple, or slate."
    ),
}


@lru_cache(maxsize=1)
def project_generation_options() -> dict[str, Any]:
    catalog = get_generator_option_catalog()
    fields = []
    for field in catalog.fields:
        fields.append(
            {
                "name": field.key,
                "label": field.label,
                "description": FIELD_DESCRIPTIONS.get(
                    field.key, f"Whether to include {field.label} in the generated project."
                ),
                "required": field.key in {"project_name", "project_slug"},
                "default": field.default,
                "choices": ["y", "n"] if field.is_feature_flag else [],
                "type": "choice" if field.is_feature_flag else "string",
                "category": field.category or "other",
            }
        )
    return {
        "schema_version": "djass.project_create.v1",
        "discovery_prompt": PROJECT_CREATE_DISCOVERY_PROMPT,
        "fields": fields,
        "required_fields": [field["name"] for field in fields if field["required"]],
        "defaults": catalog.defaults,
        "groups": catalog.get_option_groups(),
        "recommended_flow": [
            "Call djass_generation_options first so your prompt stays current as Djass evolves.",
            (
                "Ask the user for every required field and every y/n option they have "
                "not already specified."
            ),
            (
                "If the user explicitly delegates choices, use defaults and summarize "
                "them before generation."
            ),
            "Call djass_create_project only after the project intent and options are clear.",
        ],
    }


@lru_cache(maxsize=1)
def project_create_json_schema() -> dict[str, Any]:
    properties = {}
    required = []
    for field in project_generation_options()["fields"]:
        schema: dict[str, Any] = {
            "type": "string",
            "description": field["description"],
        }
        if field["choices"]:
            schema["enum"] = field["choices"]
        if field["default"] is not None:
            schema["default"] = field["default"]
        if field["required"]:
            required.append(field["name"])
        properties[field["name"]] = schema

    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }
