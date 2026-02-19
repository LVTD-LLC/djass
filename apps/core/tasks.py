import hashlib
import json
import os
import subprocess
import tempfile
import zipfile

from cookiecutter.main import cookiecutter
from pathlib import Path
from urllib.parse import unquote

import posthog
import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from apps.core.models import Profile, Project, ProjectArtifact, ProjectStatus
from djass.utils import get_djass_logger

logger = get_djass_logger(__name__)

def add_email_to_buttondown(email, tag):
    if not settings.BUTTONDOWN_API_KEY:
        return "Buttondown API key not found."

    data = {
        "email_address": str(email),
        "metadata": {"source": tag},
        "tags": [tag],
        "referrer_url": "https://djass.com",
        "type": "regular",
    }

    r = requests.post(
        "https://api.buttondown.email/v1/subscribers",
        headers={"Authorization": f"Token {settings.BUTTONDOWN_API_KEY}"},
        json=data,
    )

    return r.json()


def try_create_posthog_alias(profile_id: int, cookies: dict, source_function: str = None) -> str:
    if not settings.POSTHOG_API_KEY:
        return "PostHog API key not found."

    base_log_data = {
        "profile_id": profile_id,
        "cookies": cookies,
        "source_function": source_function,
    }

    profile = Profile.objects.get(id=profile_id)
    email = profile.user.email

    base_log_data["email"] = email
    base_log_data["profile_id"] = profile_id

    posthog_cookie = cookies.get(f"ph_{settings.POSTHOG_API_KEY}_posthog")
    if not posthog_cookie:
        logger.warning("[Try Create Posthog Alias] No PostHog cookie found.", **base_log_data)
        return f"No PostHog cookie found for profile {profile_id}."
    base_log_data["posthog_cookie"] = posthog_cookie

    logger.info("[Try Create Posthog Alias] Setting PostHog alias", **base_log_data)

    cookie_dict = json.loads(unquote(posthog_cookie))
    frontend_distinct_id = cookie_dict.get("distinct_id")

    if frontend_distinct_id:
        posthog.alias(frontend_distinct_id, email)
        posthog.alias(frontend_distinct_id, str(profile_id))

    logger.info("[Try Create Posthog Alias] Set PostHog alias", **base_log_data)


def track_event(
    profile_id: int, event_name: str, properties: dict, source_function: str = None
) -> str:
    if not settings.POSTHOG_API_KEY:
        return "PostHog API key not found."

    base_log_data = {
        "profile_id": profile_id,
        "event_name": event_name,
        "properties": properties,
        "source_function": source_function,
    }

    try:
        profile = Profile.objects.get(id=profile_id)
    except Profile.DoesNotExist:
        logger.error("[TrackEvent] Profile not found.", **base_log_data)
        return f"Profile with id {profile_id} not found."

    posthog.capture(
        profile.user.email,
        event=event_name,
        properties={
            "profile_id": profile.id,
            "email": profile.user.email,
            "current_state": profile.state,
            **properties,
        },
    )

    logger.info("[TrackEvent] Tracked event", **base_log_data)

    return f"Tracked event {event_name} for profile {profile_id}"



def track_state_change(
    profile_id: int,
    from_state: str,
    to_state: str,
    metadata: dict = None,
    source_function: str = None
) -> None:
    from apps.core.models import Profile, ProfileStateTransition

    base_log_data = {
        "profile_id": profile_id,
        "from_state": from_state,
        "to_state": to_state,
        "metadata": metadata,
        "source_function": source_function,
    }

    try:
        profile = Profile.objects.get(id=profile_id)
    except Profile.DoesNotExist:
        logger.error("[TrackStateChange] Profile not found.", **base_log_data)
        return f"Profile with id {profile_id} not found."

    if from_state != to_state:
        logger.info("[TrackStateChange] Tracking state change", **base_log_data)
        ProfileStateTransition.objects.create(
            profile=profile,
            from_state=from_state,
            to_state=to_state,
            backup_profile_id=profile_id,
            metadata=metadata,
        )
        profile.state = to_state
        profile.save(update_fields=["state"])

    return f"Tracked state change from {from_state} to {to_state} for profile {profile_id}"


def _zip_directory(source_dir: Path, output_zip: Path) -> None:
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(source_dir):
            for file_name in files:
                full_path = Path(root) / file_name
                zipf.write(full_path, full_path.relative_to(source_dir))


def _compute_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate_project_artifact(project_id: int) -> str:
    project = Project.objects.get(id=project_id)
    if project.status == ProjectStatus.GENERATING:
        return "Project is already generating"

    project.status = ProjectStatus.GENERATING
    project.started_at = timezone.now()
    project.error_message = ""
    project.save(update_fields=["status", "started_at", "error_message", "updated_at"])

    template_path = settings.COOKIECUTTER_TEMPLATE_PATH

    try:
        with tempfile.TemporaryDirectory(prefix="djass-gen-") as tmp_dir:
            tmp_dir_path = Path(tmp_dir)
            output_root = tmp_dir_path / "output"
            output_root.mkdir(parents=True, exist_ok=True)

            generated_dir_path = None

            try:
                generated_dir = cookiecutter(
                    str(template_path),
                    no_input=True,
                    output_dir=str(output_root),
                    extra_context=project.input_payload,
                )
                generated_dir_path = Path(generated_dir)
            except Exception as python_api_exc:
                logger.warning(
                    "Cookiecutter Python API failed, falling back to CLI",
                    project_id=project.id,
                    error=str(python_api_exc),
                )
                command = [
                    "cookiecutter",
                    str(template_path),
                    "--no-input",
                    "--output-dir",
                    str(output_root),
                ]
                for key, value in project.input_payload.items():
                    command.append(f"{key}={value}")

                subprocess.run(command, check=True, capture_output=True, text=True)
                generated_items = [path for path in output_root.iterdir() if path.is_dir()]
                if not generated_items:
                    raise RuntimeError("No generated project directory found")
                generated_dir_path = generated_items[0]

            generated_dir = generated_dir_path
            zip_path = tmp_dir_path / f"{project.slug or 'project'}.zip"
            _zip_directory(generated_dir, zip_path)

            zip_bytes = zip_path.read_bytes()
            size_bytes = zip_path.stat().st_size
            sha256 = _compute_sha256(zip_path)

            artifact, _ = ProjectArtifact.objects.get_or_create(project=project)
            if artifact.zip_file:
                artifact.zip_file.delete(save=False)

            artifact_name = f"{project.slug or 'project'}.zip"
            artifact.zip_file.save(artifact_name, ContentFile(zip_bytes), save=False)
            artifact.size_bytes = size_bytes
            artifact.sha256 = sha256
            artifact.save()

        project.status = ProjectStatus.READY
        project.finished_at = timezone.now()
        project.error_message = ""
        project.save(update_fields=["status", "finished_at", "error_message", "updated_at"])
        return "Project artifact generated"

    except Exception as exc:
        project.status = ProjectStatus.FAILED
        project.finished_at = timezone.now()
        project.error_message = str(exc)[:1000]
        project.save(update_fields=["status", "finished_at", "error_message", "updated_at"])
        logger.error("Project generation failed", project_id=project.id, error=str(exc), exc_info=True)
        raise
