from datetime import datetime
from typing import Any, Literal

from ninja import Schema
from pydantic import ConfigDict, Field, create_model

from apps.blog.choices import BlogPostStatus
from apps.core.generator_options import COOKIECUTTER_FIELD_DEFAULTS, get_generator_option_catalog


class SubmitFeedbackIn(Schema):
    feedback: str
    page: str


class SubmitFeedbackOut(Schema):
    success: bool
    message: str


class BlogPostIn(Schema):
    title: str
    description: str = ""
    slug: str
    tags: str = ""
    content: str
    icon: str | None = None  # URL or base64 string
    image: str | None = None  # URL or base64 string
    status: BlogPostStatus = BlogPostStatus.DRAFT


class BlogPostOut(Schema):
    status: str  # API response status: 'success' or 'failure'
    message: str


class ProfileSettingsOut(Schema):
    can_generate_projects: bool


class UserSettingsOut(Schema):
    profile: ProfileSettingsOut


class ApiErrorBody(Schema):
    code: str
    category: Literal["validation", "auth", "quota", "retryable", "internal"]
    message: str
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class ApiError(Schema):
    error: ApiErrorBody


YNFlag = Literal["y", "n"]


class ProjectCreateBase(Schema):
    model_config = ConfigDict(extra="allow")


def _project_create_fields() -> dict[str, tuple[Any, Any]]:
    fields = {
        "project_name": (str, ...),
        "project_slug": (str, ...),
        "caprover_app_name": (str, COOKIECUTTER_FIELD_DEFAULTS["caprover_app_name"]),
        "project_description": (str, COOKIECUTTER_FIELD_DEFAULTS["project_description"]),
        "repo_url": (str, COOKIECUTTER_FIELD_DEFAULTS["repo_url"]),
        "author_name": (str, COOKIECUTTER_FIELD_DEFAULTS["author_name"]),
        "author_email": (str, ""),
        "author_url": (str, COOKIECUTTER_FIELD_DEFAULTS["author_url"]),
        "project_main_color": (str, COOKIECUTTER_FIELD_DEFAULTS["project_main_color"]),
    }
    for option in get_generator_option_catalog().feature_flags:
        fields[option.key] = (YNFlag, option.default)
    return fields


ProjectCreateIn = create_model(
    "ProjectCreateIn",
    __base__=ProjectCreateBase,
    **_project_create_fields(),
)


class ProjectGeneratorOptionOut(Schema):
    key: str
    label: str
    default: str
    category: str


class ProjectGeneratorOptionGroupOut(Schema):
    key: str
    label: str
    options: list[ProjectGeneratorOptionOut]


class ProjectGeneratorOptionsOut(Schema):
    defaults: dict[str, Any]
    groups: list[ProjectGeneratorOptionGroupOut]


class ProjectOut(Schema):
    id: int
    name: str
    slug: str
    status: Literal["queued", "generating", "ready", "failed"]
    error_message: str
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    artifact_ready: bool
    input_payload: dict[str, Any]


class ProjectStatusOut(Schema):
    id: int
    status: Literal["queued", "generating", "ready", "failed"]
    error_message: str
    artifact_ready: bool
    started_at: datetime | None = None
    finished_at: datetime | None = None
    updated_at: datetime


class ProjectListOut(Schema):
    projects: list[ProjectOut]
    total: int
    limit: int
    offset: int
    has_next: bool
    filters: dict[str, Any] = Field(default_factory=dict)


class ProjectCreateOut(Schema):
    project: ProjectOut


class ProjectArtifactOut(Schema):
    size_bytes: int
    sha256: str
    zip_file: str


class ProjectInspectOut(Schema):
    id: int
    name: str
    slug: str
    status: str
    error_message: str
    input_payload: dict[str, Any]
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime
    artifact: ProjectArtifactOut | None = None
