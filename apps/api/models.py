from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.base_models import BaseModel
from apps.core.model_utils import generate_random_key
from apps.core.models import Profile, Project


class ProjectAPIKeyScope(models.TextChoices):
    PROJECTS_CREATE = "projects:create", "Create projects"
    PROJECTS_READ = "projects:read", "Read projects"


class ProjectAPIKey(BaseModel):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="project_api_keys")
    name = models.CharField(max_length=255)
    key = models.CharField(max_length=64, unique=True, default=generate_random_key)
    scopes = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        super().clean()
        allowed = {choice for choice, _ in ProjectAPIKeyScope.choices}
        invalid_scopes = [scope for scope in self.scopes if scope not in allowed]
        if invalid_scopes:
            raise ValidationError({"scopes": f"Invalid scopes: {', '.join(invalid_scopes)}"})

    def is_expired(self) -> bool:
        return bool(self.expires_at and self.expires_at <= timezone.now())

    def allows(self, scope: str) -> bool:
        return scope in set(self.scopes or [])

    def __str__(self):
        return f"{self.name} ({self.profile_id})"


class ProjectAPIAuditLog(BaseModel):
    ACTION_CREATE = "project.create"
    ACTION_LIST = "project.list"
    ACTION_GET = "project.get"
    ACTION_STATUS = "project.status"

    ACTION_CHOICES = (
        (ACTION_CREATE, "Create project"),
        (ACTION_LIST, "List projects"),
        (ACTION_GET, "Get project"),
        (ACTION_STATUS, "Get project status"),
    )

    profile = models.ForeignKey(
        Profile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="project_api_audit_logs",
    )
    api_key = models.ForeignKey(
        ProjectAPIKey,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    project = models.ForeignKey(
        Project,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="api_audit_logs",
    )
    action = models.CharField(max_length=32, choices=ACTION_CHOICES)
    status_code = models.PositiveSmallIntegerField()
    method = models.CharField(max_length=8)
    path = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True, default="")
    key_type = models.CharField(max_length=16, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} [{self.status_code}]"
