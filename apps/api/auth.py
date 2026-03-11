from dataclasses import dataclass

from django.http import HttpRequest
from django.utils import timezone
from ninja.security import APIKeyQuery

from apps.api.models import ProjectAPIKey
from apps.api.utils import _get_api_key_from_headers
from apps.core.models import Profile
from djass.utils import get_djass_logger

logger = get_djass_logger(__name__)


@dataclass(frozen=True)
class APIAuthPrincipal:
    profile: Profile
    key_type: str
    scopes: set[str]
    project_api_key: ProjectAPIKey | None = None

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes


def _resolve_api_principal(key: str) -> APIAuthPrincipal | None:
    project_key = (
        ProjectAPIKey.objects.select_related("profile", "profile__user")
        .filter(key=key, is_active=True)
        .first()
    )
    if project_key:
        if project_key.is_expired():
            return None

        ProjectAPIKey.objects.filter(pk=project_key.pk).update(last_used_at=timezone.now())
        return APIAuthPrincipal(
            profile=project_key.profile,
            key_type="scoped",
            scopes=set(project_key.scopes or []),
            project_api_key=project_key,
        )

    try:
        profile = Profile.objects.select_related("user").get(key=key)
    except Profile.DoesNotExist:
        return None

    return APIAuthPrincipal(
        profile=profile,
        key_type="legacy",
        scopes={"projects:create", "projects:read"},
    )


class APIKeyAuth(APIKeyQuery):
    param_name = "api_key"

    def authenticate(self, request: HttpRequest, key: str) -> Profile | None:
        logger.info(
            "[Django Ninja Auth] API Request with key",
            key=key,
        )
        try:
            return Profile.objects.get(key=key)
        except Profile.DoesNotExist:
            logger.warning("[Django Ninja Auth] Invalid API key", key=key)
            return None


class HeaderOrQueryAPIKeyAuth:
    """Authenticate with X-API-Key/Authorization header or ?api_key= query param."""

    def authenticate(self, request: HttpRequest) -> APIAuthPrincipal | None:
        key = _get_api_key_from_headers(request) or request.GET.get("api_key")
        request.api_key_attempt = key

        if not key:
            return None

        principal = _resolve_api_principal(key)
        if not principal:
            logger.warning("[Django Ninja Auth] Invalid API key", key=key)
            return None

        return principal

    def __call__(self, request: HttpRequest):
        return self.authenticate(request)


class SessionAuth:
    """Authentication via Django session"""

    def authenticate(self, request: HttpRequest) -> Profile | None:
        if hasattr(request, "user") and request.user.is_authenticated:
            logger.info(
                "[Django Ninja Auth] API Request with authenticated user",
                user_id=request.user.id,
            )
            try:
                return request.user.profile
            except Profile.DoesNotExist:
                logger.warning("[Django Ninja Auth] No profile for user", user_id=request.user.id)
                return None
        return None

    def __call__(self, request: HttpRequest):
        return self.authenticate(request)


class SuperuserAPIKeyAuth(APIKeyQuery):
    param_name = "api_key"

    def authenticate(self, request: HttpRequest, key: str) -> Profile | None:
        try:
            profile = Profile.objects.get(key=key)
            if profile.user.is_superuser:
                return profile
            logger.warning(
                "[Django Ninja Auth] Non-superuser attempted admin access",
                profile_id=profile.user.id,
            )
            return None
        except Profile.DoesNotExist:
            logger.warning("[Django Ninja Auth] Profile does not exist", key=key)
            return None


api_key_auth = APIKeyAuth()
header_or_query_api_key_auth = HeaderOrQueryAPIKeyAuth()
session_auth = SessionAuth()
superuser_api_auth = SuperuserAPIKeyAuth()
