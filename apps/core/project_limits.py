from django.conf import settings


def project_create_quota() -> int:
    return int(getattr(settings, "PROJECT_API_MAX_PROJECTS_PER_USER", 200))
