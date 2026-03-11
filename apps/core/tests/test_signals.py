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
