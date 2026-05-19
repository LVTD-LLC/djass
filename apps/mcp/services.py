import io
import os
import shutil
import zipfile
from pathlib import Path
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.text import slugify
from django_q.tasks import async_task

from apps.core.choices import ProfileStates
from apps.core.forms import ProjectCreateForm
from apps.core.models import Profile, Project, ProjectStatus
from apps.core.tasks import COOKIECUTTER_FIELD_DEFAULTS, MODULE_FLAG_KEYS, generate_project_artifact

DEFAULT_MCP_USER_EMAIL = "djass-agent@example.local"
DEFAULT_MCP_USERNAME = "djass-agent"
PROJECT_ACCESS_STATES = {
    ProfileStates.TRIAL_STARTED,
    ProfileStates.SUBSCRIBED,
    ProfileStates.CANCELLED,
}


class MCPServiceError(RuntimeError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


def _isoformat(value) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _clean_optional(value: str | None) -> str:
    return (value or "").strip()


def _default_user_email() -> str:
    return _clean_optional(os.environ.get("DJASS_MCP_USER_EMAIL")) or DEFAULT_MCP_USER_EMAIL


def default_mcp_user_email() -> str:
    return _default_user_email()


def _default_username(email: str) -> str:
    configured = _clean_optional(os.environ.get("DJASS_MCP_USERNAME"))
    if configured:
        return configured
    local_part = email.split("@", maxsplit=1)[0]
    return slugify(local_part).replace("-", "_") or DEFAULT_MCP_USERNAME


def _unique_username(base_username: str) -> str:
    UserModel = get_user_model()
    normalized = slugify(base_username).replace("-", "_") or DEFAULT_MCP_USERNAME
    candidate = normalized[:150]
    suffix = 2
    while UserModel.objects.filter(username=candidate).exists():
        suffix_text = f"_{suffix}"
        candidate = f"{normalized[: 150 - len(suffix_text)]}{suffix_text}"
        suffix += 1
    return candidate


@transaction.atomic
def ensure_mcp_user(
    *,
    user_email: str | None = None,
    username: str | None = None,
    create_if_missing: bool = True,
    grant_project_access: bool = True,
):
    email = _clean_optional(user_email) or _default_user_email()
    explicit_username = _clean_optional(username)
    resolved_username = explicit_username or _default_username(email)
    UserModel = get_user_model()

    user = UserModel.objects.filter(email__iexact=email).order_by("id").first()
    if user is None and explicit_username:
        user = UserModel.objects.filter(username=resolved_username).order_by("id").first()

    if user is None:
        if not create_if_missing:
            raise MCPServiceError(
                "user_not_found",
                "No Djass user matched the MCP request.",
                {"email": email, "username": resolved_username},
            )
        user = UserModel(username=_unique_username(resolved_username), email=email)
        user.set_unusable_password()
        user.save()

    profile, _ = Profile.objects.get_or_create(user=user)
    if grant_project_access and profile.state not in PROJECT_ACCESS_STATES:
        profile.state = ProfileStates.SUBSCRIBED
        profile.save(update_fields=["state", "updated_at"])

    return user


def get_generator_options() -> dict[str, Any]:
    fields = []
    for name, default in COOKIECUTTER_FIELD_DEFAULTS.items():
        field: dict[str, Any] = {
            "name": name,
            "default": default,
            "required": name in {"project_name", "project_slug"},
        }
        if name in MODULE_FLAG_KEYS:
            field["choices"] = ["y", "n"]
        fields.append(field)

    return {
        "template_path": str(settings.COOKIECUTTER_TEMPLATE_PATH),
        "fields": fields,
        "defaults": dict(COOKIECUTTER_FIELD_DEFAULTS),
        "module_flags": list(MODULE_FLAG_KEYS),
    }


def build_project_payload(
    raw_payload: dict[str, Any],
    *,
    user,
    extra_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    known_payload = dict(COOKIECUTTER_FIELD_DEFAULTS)
    known_payload.update(
        {
            key: value
            for key, value in raw_payload.items()
            if key in COOKIECUTTER_FIELD_DEFAULTS and value is not None
        }
    )

    form = ProjectCreateForm(known_payload, user=user)
    if not form.is_valid():
        raise MCPServiceError(
            "validation_error",
            "Project payload validation failed.",
            {"fields": form.errors.get_json_data()},
        )

    payload = form.get_cookiecutter_payload()
    for source in (raw_payload, extra_context or {}):
        for key, value in source.items():
            if key not in COOKIECUTTER_FIELD_DEFAULTS and value is not None:
                payload[key] = value
    return payload


def _create_project(user, payload: dict[str, Any]) -> Project:
    project_slug = slugify(payload["project_slug"]).replace("-", "_")
    if not project_slug:
        raise MCPServiceError(
            "invalid_project_slug",
            "project_slug must contain letters or numbers.",
            {"project_slug": payload.get("project_slug", "")},
        )

    return Project.objects.create(
        user=user,
        name=payload["project_name"],
        slug=project_slug[:255],
        input_payload=payload,
        status=ProjectStatus.QUEUED,
    )


def _artifact_payload(project: Project) -> dict[str, Any] | None:
    if not hasattr(project, "artifact"):
        return None

    artifact = project.artifact
    payload = {
        "storage_name": artifact.zip_file.name,
        "size_bytes": artifact.size_bytes,
        "sha256": artifact.sha256,
    }
    try:
        payload["url"] = artifact.zip_file.url
    except Exception:
        payload["url"] = ""
    return payload


def serialize_project(project: Project) -> dict[str, Any]:
    return {
        "id": project.id,
        "name": project.name,
        "slug": project.slug,
        "status": project.status,
        "error_message": project.error_message,
        "created_at": _isoformat(project.created_at),
        "updated_at": _isoformat(project.updated_at),
        "started_at": _isoformat(project.started_at),
        "finished_at": _isoformat(project.finished_at),
        "artifact_ready": hasattr(project, "artifact"),
        "artifact": _artifact_payload(project),
        "input_payload": project.input_payload,
        "user": {
            "id": project.user_id,
            "email": project.user.email,
            "username": project.user.username,
        },
    }


def queue_project_generation(
    raw_payload: dict[str, Any],
    *,
    user_email: str | None = None,
    username: str | None = None,
    create_user: bool = True,
    grant_project_access: bool = True,
    extra_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    user = ensure_mcp_user(
        user_email=user_email,
        username=username,
        create_if_missing=create_user,
        grant_project_access=grant_project_access,
    )
    payload = build_project_payload(raw_payload, user=user, extra_context=extra_context)
    project = _create_project(user, payload)

    async_task(
        "apps.core.tasks.generate_project_artifact",
        project_id=project.id,
        group="Generate Project",
    )

    return {
        "project": serialize_project(project),
        "queued": True,
    }


def generate_project_now(
    raw_payload: dict[str, Any],
    *,
    user_email: str | None = None,
    username: str | None = None,
    create_user: bool = True,
    grant_project_access: bool = True,
    extra_context: dict[str, Any] | None = None,
    output_dir: str | None = None,
    extract: bool = True,
    overwrite: bool = False,
) -> dict[str, Any]:
    user = ensure_mcp_user(
        user_email=user_email,
        username=username,
        create_if_missing=create_user,
        grant_project_access=grant_project_access,
    )
    payload = build_project_payload(raw_payload, user=user, extra_context=extra_context)
    project = _create_project(user, payload)

    try:
        generate_project_artifact(project.id)
    except Exception as exc:
        project.refresh_from_db()
        raise MCPServiceError(
            "generation_failed",
            f"Project generation failed: {exc}",
            {
                "project_id": project.id,
                "status": project.status,
                "error_message": project.error_message,
            },
        ) from exc
    project = Project.objects.select_related("user", "artifact").get(id=project.id)

    result = {
        "project": serialize_project(project),
        "queued": False,
        "generated": project.status == ProjectStatus.READY,
    }
    if output_dir:
        result["export"] = export_project_artifact(
            project.id,
            output_dir=output_dir,
            user_email=user.email,
            extract=extract,
            overwrite=overwrite,
        )
    return result


def _project_queryset(user_email: str | None = None):
    queryset = Project.objects.select_related("user", "artifact").order_by("id")
    if user_email:
        queryset = queryset.filter(user__email__iexact=user_email)
    return queryset


def get_project(project_id: int, *, user_email: str | None = None) -> dict[str, Any]:
    project = _project_queryset(user_email).filter(id=project_id).first()
    if project is None:
        raise MCPServiceError(
            "project_not_found",
            "Project not found.",
            {"project_id": project_id, "user_email": user_email or ""},
        )
    return serialize_project(project)


def list_projects(
    *,
    user_email: str | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    if limit < 1 or limit > 100:
        raise MCPServiceError("invalid_limit", "limit must be between 1 and 100.", {"limit": limit})
    if offset < 0:
        raise MCPServiceError("invalid_offset", "offset must be greater than or equal to 0.")
    if status and status not in ProjectStatus.values:
        raise MCPServiceError(
            "invalid_status",
            "status must be one of queued, generating, ready, or failed.",
            {"status": status},
        )

    queryset = _project_queryset(user_email)
    filters: dict[str, Any] = {}
    if status:
        queryset = queryset.filter(status=status)
        filters["status"] = status

    total = queryset.count()
    rows = list(queryset[offset : offset + limit])
    return {
        "projects": [serialize_project(project) for project in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_next": offset + len(rows) < total,
        "filters": filters,
    }


def read_project_artifact_bytes(project_id: int, *, user_email: str | None = None) -> bytes:
    project = _project_queryset(user_email).filter(id=project_id).first()
    if project is None:
        raise MCPServiceError("project_not_found", "Project not found.", {"project_id": project_id})
    if project.status != ProjectStatus.READY or not hasattr(project, "artifact"):
        raise MCPServiceError(
            "artifact_not_ready",
            "Project artifact is not ready yet.",
            {"project_id": project_id, "status": project.status},
        )

    with project.artifact.zip_file.open("rb") as file_obj:
        return file_obj.read()


def _resolve_output_dir(output_dir: str) -> Path:
    path = Path(output_dir).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def _write_bytes(path: Path, content: bytes, *, overwrite: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise MCPServiceError(
            "output_exists",
            "Output file already exists.",
            {"path": str(path), "retry_guidance": "Pass overwrite=true or choose another path."},
        )
    path.write_bytes(content)


def _safe_extract_zip(content: bytes, target_dir: Path, *, overwrite: bool) -> None:
    target_dir = target_dir.resolve()
    if target_dir.exists():
        if not overwrite:
            raise MCPServiceError(
                "output_exists",
                "Extract directory already exists.",
                {
                    "path": str(target_dir),
                    "retry_guidance": "Pass overwrite=true or choose another output directory.",
                },
            )
        if not target_dir.is_dir():
            raise MCPServiceError(
                "output_exists",
                "Extract path exists and is not a directory.",
                {"path": str(target_dir)},
            )
        shutil.rmtree(target_dir)

    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(content), "r") as zip_file:
        for member in zip_file.infolist():
            member_path = (target_dir / member.filename).resolve()
            if not member_path.is_relative_to(target_dir):
                raise MCPServiceError(
                    "unsafe_artifact_path",
                    "Artifact contains a path outside the extract directory.",
                    {"member": member.filename},
                )
        zip_file.extractall(target_dir)


def export_project_artifact(
    project_id: int,
    *,
    output_dir: str,
    user_email: str | None = None,
    extract: bool = True,
    overwrite: bool = False,
) -> dict[str, Any]:
    project = _project_queryset(user_email).filter(id=project_id).first()
    if project is None:
        raise MCPServiceError("project_not_found", "Project not found.", {"project_id": project_id})

    content = read_project_artifact_bytes(project_id, user_email=user_email)
    output_path = _resolve_output_dir(output_dir)
    zip_path = output_path / f"{project.slug or 'project'}.zip"
    _write_bytes(zip_path, content, overwrite=overwrite)

    response: dict[str, Any] = {
        "zip_path": str(zip_path),
        "extracted": False,
        "extract_path": "",
    }
    if extract:
        extract_path = output_path / (project.slug or "project")
        _safe_extract_zip(content, extract_path, overwrite=overwrite)
        response["extracted"] = True
        response["extract_path"] = str(extract_path)

    return response
