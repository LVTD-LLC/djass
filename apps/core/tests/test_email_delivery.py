from types import SimpleNamespace

import pytest
from django.test import RequestFactory

from djass.adapters import CustomAccountAdapter


class _FakeMailgunError(Exception):
    def __init__(self, message, status_code=401, response_text="Forbidden"):
        super().__init__(message)
        self.status_code = status_code
        self.response = SimpleNamespace(text=response_text)


@pytest.fixture
def adapter():
    return CustomAccountAdapter()


@pytest.fixture
def email_confirmation():
    user = SimpleNamespace(id=123, profile=SimpleNamespace())
    return SimpleNamespace(
        email_address=SimpleNamespace(
            email="testuser@example.com",
            user=user,
        )
    )


def test_signup_confirmation_mail_failure_logs_and_does_not_raise(adapter, email_confirmation, monkeypatch):
    logged_payload = {}
    request = RequestFactory().get("/")

    def _fake_logger_error(event, **kwargs):
        logged_payload["event"] = event
        logged_payload.update(kwargs)

    def _raise_mailgun_error(*args, **kwargs):
        raise _FakeMailgunError("Mailgun API response 401: Forbidden")

    monkeypatch.setattr("djass.adapters.logger.error", _fake_logger_error)
    monkeypatch.setattr(
        "allauth.account.adapter.DefaultAccountAdapter.send_confirmation_mail",
        _raise_mailgun_error,
    )

    result = adapter.send_confirmation_mail(request=request, emailconfirmation=email_confirmation, signup=True)

    assert result is None
    assert logged_payload["event"] == "[Send Confirmation Mail] Failed to send email"
    assert logged_payload["status_code"] == 401
    assert logged_payload["response_text"] == "Forbidden"
    assert logged_payload["error_type"] == "_FakeMailgunError"
    assert logged_payload["signup"] is True


def test_resend_confirmation_mail_failure_still_raises(adapter, email_confirmation, monkeypatch):
    logged_payload = {}

    def _fake_logger_error(event, **kwargs):
        logged_payload["event"] = event
        logged_payload.update(kwargs)

    def _raise_mailgun_error(*args, **kwargs):
        raise _FakeMailgunError("Mailgun API response 401: Forbidden")

    monkeypatch.setattr("djass.adapters.logger.error", _fake_logger_error)
    monkeypatch.setattr(
        "allauth.account.adapter.DefaultAccountAdapter.send_confirmation_mail",
        _raise_mailgun_error,
    )

    with pytest.raises(_FakeMailgunError):
        adapter.send_confirmation_mail(request=None, emailconfirmation=email_confirmation, signup=False)

    assert logged_payload["event"] == "[Send Confirmation Mail] Failed to send email"
    assert logged_payload["status_code"] == 401
    assert logged_payload["response_text"] == "Forbidden"
    assert logged_payload["error_type"] == "_FakeMailgunError"
    assert logged_payload["signup"] is False
