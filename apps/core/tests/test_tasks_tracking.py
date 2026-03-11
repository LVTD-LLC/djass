from types import SimpleNamespace
from unittest.mock import patch

from apps.core.tasks import track_event


def test_track_event_skips_when_posthog_key_missing(settings):
    settings.POSTHOG_API_KEY = ""

    with patch("apps.core.tasks.posthog.capture") as capture:
        result = track_event(profile_id=42, event_name="project_created", properties={})

    assert result == "PostHog API key not found."
    capture.assert_not_called()


def test_track_event_captures_expected_properties(settings):
    settings.POSTHOG_API_KEY = "phc_test"
    fake_profile = SimpleNamespace(
        id=7,
        state="signed_up",
        user=SimpleNamespace(email="agent@example.com"),
    )

    with (
        patch("apps.core.tasks.Profile.objects.get", return_value=fake_profile),
        patch("apps.core.tasks.posthog.capture") as capture,
    ):
        result = track_event(
            profile_id=7,
            event_name="project_created",
            properties={"funnel_step": "project_created", "project_slug": "demo"},
        )

    assert result == "Tracked event project_created for profile 7"
    capture.assert_called_once_with(
        "agent@example.com",
        event="project_created",
        properties={
            "profile_id": 7,
            "email": "agent@example.com",
            "current_state": "signed_up",
            "funnel_step": "project_created",
            "project_slug": "demo",
        },
    )
