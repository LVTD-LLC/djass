from datetime import datetime
from typing import Any

from ninja import Schema

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
