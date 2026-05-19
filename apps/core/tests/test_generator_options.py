import json
from collections import OrderedDict

import pytest
import requests
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.api.schemas import ProjectCreateIn
from apps.core.forms import ProjectCreateForm
from apps.core.generator_options import (
    COOKIECUTTER_FIELD_DEFAULTS,
    get_generator_option_catalog,
    get_generator_option_groups,
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


def test_api_and_mcp_catalog_payloads_match():
    catalog = get_generator_option_catalog()

    assert catalog.as_api_payload() == catalog.as_mcp_payload()
    assert catalog.as_api_payload()["groups"] == get_generator_option_groups()


def test_catalog_feature_flags_feed_ui_api_and_mcp():
    catalog = get_generator_option_catalog()
    feature_flag_keys = {field.key for field in catalog.feature_flags}

    assert feature_flag_keys.issubset(ProjectCreateForm().fields)
    assert feature_flag_keys.issubset(ProjectCreateIn.model_fields)
    assert {
        option["key"]
        for group in catalog.as_mcp_payload()["groups"]
        for option in group["options"]
    } == feature_flag_keys


def test_sync_cookiecutter_options_check_passes_when_catalog_matches(tmp_path):
    source_path = tmp_path / "cookiecutter.json"
    source_path.write_text(
        json.dumps(COOKIECUTTER_FIELD_DEFAULTS, indent=2) + "\n",
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


def test_sync_cookiecutter_options_can_skip_remote_network_errors(monkeypatch):
    def raise_timeout(*args, **kwargs):
        raise requests.Timeout("timed out")

    monkeypatch.setattr(requests, "get", raise_timeout)

    call_command(
        "sync_cookiecutter_options",
        "--source",
        "https://example.com/cookiecutter.json",
        "--check",
        "--skip-on-network-error",
    )


def test_sync_cookiecutter_options_reports_remote_network_errors(monkeypatch):
    def raise_timeout(*args, **kwargs):
        raise requests.Timeout("timed out")

    monkeypatch.setattr(requests, "get", raise_timeout)

    with pytest.raises(CommandError, match="network or source availability failure"):
        call_command(
            "sync_cookiecutter_options",
            "--source",
            "https://example.com/cookiecutter.json",
            "--check",
        )


def test_sync_cookiecutter_options_does_not_skip_missing_remote_source(monkeypatch):
    class NotFoundResponse:
        status_code = 404

        def raise_for_status(self):
            raise requests.HTTPError("not found", response=self)

    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: NotFoundResponse())

    with pytest.raises(CommandError, match="Could not fetch remote cookiecutter options"):
        call_command(
            "sync_cookiecutter_options",
            "--source",
            "https://example.com/missing-cookiecutter.json",
            "--check",
            "--skip-on-network-error",
        )
