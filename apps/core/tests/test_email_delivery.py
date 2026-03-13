from types import SimpleNamespace

import pytest

from djass.adapters import CustomAccountAdapter


class _FakeMailgunError(Exception):
    def __init__(self, message, status_code=401, response_text="Forbidden"):
        super().__init__(message)
        self.status_code = status_code
        self.response = SimpleNamespace(text=response_text)


def test_send_confirmation_mail_logs_actionable_provider_error(monkeypatch):
    adapter = CustomAccountAdapter()

    user = SimpleNamespace(id=123, profile=SimpleNamespace())
    email_confirmation = SimpleNamespace(
        email_address=SimpleNamespace(
            email="testuser@example.com",
            user=user,
        )
    )

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
        adapter.send_confirmation_mail(request=None, emailconfirmation=email_confirmation, signup=True)

    assert logged_payload["event"] == "[Send Confirmation Mail] Failed to send email"
    assert logged_payload["status_code"] == 401
    assert logged_payload["response_text"] == "Forbidden"
    assert logged_payload["error_type"] == "_FakeMailgunError"
