from django.conf import settings

from djass.sentry_utils import before_send, before_send_transaction


def test_sentry_observability_defaults_are_configurable():
    assert settings.SENTRY_ENABLED is False
    assert settings.SENTRY_TRACES_SAMPLE_RATE == 1.0
    assert settings.SENTRY_PROFILE_SESSION_SAMPLE_RATE == 1.0
    assert settings.SENTRY_ENABLE_LOGS is True
    assert settings.SENTRY_SEND_DEFAULT_PII is False
    assert settings.SENTRY_AI_INCLUDE_PROMPTS is False
    assert settings.SENTRY_AI_HANDLED_TOOL_CALL_EXCEPTIONS is True


def test_before_send_groups_system_exit_events():
    event = {}

    returned = before_send(event, {"exc_info": (SystemExit, SystemExit(1), None)})

    assert returned is event
    assert returned["fingerprint"] == ["system-exit"]


def test_before_send_transaction_drops_healthcheck_url():
    event = {"request": {"url": "https://djass.dev/api/healthcheck"}}

    assert before_send_transaction(event, {}) is None


def test_before_send_transaction_keeps_application_url():
    event = {"request": {"url": "https://djass.dev/api/v1/projects"}}

    assert before_send_transaction(event, {}) is event
