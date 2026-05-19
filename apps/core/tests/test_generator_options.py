import json
from collections import OrderedDict

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.core.generator_options import (
    COOKIECUTTER_FIELD_DEFAULTS,
    get_generator_option_groups,
    serialize_cookiecutter_defaults,
)


def test_generator_options_are_grouped_by_category():
    groups = {group["key"]: group for group in get_generator_option_groups()}

    assert "monitoring" in groups
    assert "cx" in groups
    assert "ai" in groups
    assert {option["key"] for option in groups["monitoring"]["options"]} >= {
        "use_posthog",
        "use_sentry",
        "use_logfire",
        "use_healthchecks",
    }
    assert {option["key"] for option in groups["cx"]["options"]} >= {
        "use_chatwoot",
        "use_buttondown",
        "use_mjml",
    }
    assert {option["key"] for option in groups["ai"]["options"]} >= {"use_ai", "use_mcp"}


def test_sync_cookiecutter_options_check_passes_when_snapshot_matches(tmp_path):
    source_path = tmp_path / "cookiecutter.json"
    source_path.write_text(
        serialize_cookiecutter_defaults(COOKIECUTTER_FIELD_DEFAULTS),
        encoding="utf-8",
    )

    call_command("sync_cookiecutter_options", "--source", str(source_path), "--check")


def test_sync_cookiecutter_options_check_detects_drift(tmp_path):
    source_defaults = OrderedDict(COOKIECUTTER_FIELD_DEFAULTS)
    source_defaults["use_future_feature"] = "n"
    source_path = tmp_path / "cookiecutter.json"
    source_path.write_text(json.dumps(source_defaults, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(CommandError, match="Added upstream: use_future_feature"):
        call_command("sync_cookiecutter_options", "--source", str(source_path), "--check")
