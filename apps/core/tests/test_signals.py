from django.test import RequestFactory

from apps.core import signals


def test_track_user_login_queues_auth_event(monkeypatch, user):
    calls = []

    def fake_async_task(*args, **kwargs):
        calls.append((args, kwargs))
        return "task-id"

    monkeypatch.setattr("apps.core.signals.async_task", fake_async_task)

    request = RequestFactory().post("/accounts/login/")
    request.COOKIES = {}

    signals.track_user_login(sender=None, request=request, user=user)

    alias_call, auth_call = calls
    assert alias_call[0][0] == "apps.core.tasks.try_create_posthog_alias"
    assert alias_call[1]["profile_id"] == user.profile.id
    assert auth_call[0][0] == "apps.core.tasks.track_event"
    assert auth_call[1]["event_name"] == "user_authenticated"
    assert auth_call[1]["properties"]["funnel_step"] == "auth_completed"
    assert auth_call[1]["properties"]["entrypoint"] == "ui"


def test_track_user_login_passkey_method(monkeypatch, user):
    calls = []

    def fake_async_task(*args, **kwargs):
        calls.append((args, kwargs))
        return "task-id"

    monkeypatch.setattr("apps.core.signals.async_task", fake_async_task)

    request = RequestFactory().post("/accounts/passkey/login/")
    request.COOKIES = {}

    signals.track_user_login(sender=None, request=request, user=user)

    auth_call = calls[1]
    assert auth_call[1]["properties"]["auth_method"] == "passkey"


def test_track_user_login_failed_queues_auth_failed_event(monkeypatch, user):
    calls = []

    def fake_async_task(*args, **kwargs):
        calls.append((args, kwargs))
        return "task-id"

    monkeypatch.setattr("apps.core.signals.async_task", fake_async_task)

    request = RequestFactory().post("/accounts/login/")
    signals.track_user_login_failed(
        sender=None,
        credentials={"email": user.email},
        request=request,
    )

    assert len(calls) == 1
    auth_failed_call = calls[0]
    assert auth_failed_call[0][0] == "apps.core.tasks.track_event"
    assert auth_failed_call[1]["event_name"] == "user_auth_failed"
    assert auth_failed_call[1]["properties"]["funnel_step"] == "auth_failed"
    assert auth_failed_call[1]["properties"]["reason"] == "invalid_credentials"


def test_track_user_login_failed_queues_auth_failure_event(monkeypatch, user):
    calls = []

    def fake_async_task(*args, **kwargs):
        calls.append((args, kwargs))
        return "task-id"

    monkeypatch.setattr("apps.core.signals.async_task", fake_async_task)

    request = RequestFactory().post("/accounts/passkey/login/")
    signals.track_user_login_failed(
        sender=None,
        credentials={"email": user.email},
        request=request,
    )

    assert len(calls) == 1
    failure_call = calls[0]
    assert failure_call[0][0] == "apps.core.tasks.track_event"
    assert failure_call[1]["event_name"] == "user_auth_failed"
    assert failure_call[1]["properties"]["auth_method"] == "passkey"
    assert failure_call[1]["properties"]["reason"] == "invalid_credentials"
    assert failure_call[1]["properties"]["funnel_step"] == "auth_failed"
