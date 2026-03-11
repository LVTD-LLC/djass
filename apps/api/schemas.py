from datetime import datetime
from typing import Any, Literal

from ninja import Schema
from pydantic import Field

from apps.blog.choices import BlogPostStatus


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
    project_name: str
    project_slug: str
    project_description: str = ""
    repo_url: str = ""
    author_name: str = ""
    author_email: str = ""
    author_url: str = ""
    project_main_color: str = "green"
    use_posthog: YNFlag = "y"
    use_buttondown: YNFlag = "y"
    use_s3: YNFlag = "y"
    use_stripe: YNFlag = "y"
    use_sentry: YNFlag = "y"
    generate_blog: YNFlag = "y"
    generate_docs: YNFlag = "y"
    use_mjml: YNFlag = "y"
    use_ai: YNFlag = "y"
    use_logfire: YNFlag = "y"
    use_healthchecks: YNFlag = "y"
    use_ci: YNFlag = "y"


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
