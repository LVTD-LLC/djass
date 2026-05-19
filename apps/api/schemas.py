from datetime import datetime
from typing import Any, Literal

from ninja import Schema
from pydantic import ConfigDict, Field

from apps.blog.choices import BlogPostStatus
from apps.core.generator_options import COOKIECUTTER_FIELD_DEFAULTS


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
    has_pro_subscription: bool


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


class ProjectCreateIn(Schema):
    model_config = ConfigDict(extra="allow")

    project_name: str
    project_slug: str
    project_description: str = ""
    repo_url: str = ""
    author_name: str = ""
    author_email: str = ""
    author_url: str = ""
    project_main_color: str = "green"
    use_posthog: YNFlag = COOKIECUTTER_FIELD_DEFAULTS["use_posthog"]
    use_chatwoot: YNFlag = COOKIECUTTER_FIELD_DEFAULTS["use_chatwoot"]
    use_buttondown: YNFlag = COOKIECUTTER_FIELD_DEFAULTS["use_buttondown"]
    use_s3: YNFlag = COOKIECUTTER_FIELD_DEFAULTS["use_s3"]
    use_stripe: YNFlag = COOKIECUTTER_FIELD_DEFAULTS["use_stripe"]
    use_sentry: YNFlag = COOKIECUTTER_FIELD_DEFAULTS["use_sentry"]
    generate_blog: YNFlag = COOKIECUTTER_FIELD_DEFAULTS["generate_blog"]
    generate_docs: YNFlag = COOKIECUTTER_FIELD_DEFAULTS["generate_docs"]
    use_mjml: YNFlag = COOKIECUTTER_FIELD_DEFAULTS["use_mjml"]
    use_ai: YNFlag = COOKIECUTTER_FIELD_DEFAULTS["use_ai"]
    use_logfire: YNFlag = COOKIECUTTER_FIELD_DEFAULTS["use_logfire"]
    use_healthchecks: YNFlag = COOKIECUTTER_FIELD_DEFAULTS["use_healthchecks"]
    use_mcp: YNFlag = COOKIECUTTER_FIELD_DEFAULTS["use_mcp"]
    use_ci: YNFlag = COOKIECUTTER_FIELD_DEFAULTS["use_ci"]


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
