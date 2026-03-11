from django.contrib import admin

from apps.api.models import ProjectAPIAuditLog, ProjectAPIKey


@admin.register(ProjectAPIKey)
class ProjectAPIKeyAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "profile",
        "is_active",
        "expires_at",
        "last_used_at",
        "created_at",
    )
    list_filter = ("is_active",)
    search_fields = ("name", "profile__user__email", "profile__user__username", "key")


@admin.register(ProjectAPIAuditLog)
class ProjectAPIAuditLogAdmin(admin.ModelAdmin):
    list_display = ("id", "action", "status_code", "profile", "api_key", "project", "created_at")
    list_filter = ("action", "status_code", "key_type")
    search_fields = ("path", "profile__user__email", "profile__user__username")
