from allauth.socialaccount.models import SocialApp
from django.conf import settings

from apps.core.choices import ProfileStates
from apps.core.models import Profile

from djass.utils import get_djass_logger

logger = get_djass_logger(__name__)


def current_state(request):
    if request.user.is_authenticated:
        try:
            return {"current_state": request.user.profile.current_state}
        except Profile.DoesNotExist:
            logger.warning("Authenticated user is missing a profile", user_id=request.user.id)
    return {"current_state": ProfileStates.STRANGER}


def posthog_api_key(request):
    return {
        "posthog_api_key": settings.POSTHOG_API_KEY,
        "posthog_host": settings.POSTHOG_HOST,
    }


def chatwoot_settings(request):
    return {
        "chatwoot_base_url": settings.CHATWOOT_BASE_URL,
        "chatwoot_website_token": settings.CHATWOOT_WEBSITE_TOKEN,
    }


def mjml_url(request):
    return {"mjml_url": settings.MJML_URL}


def available_social_providers(request):
    """
    Checks which social authentication providers are available.
    Returns a list of provider names from either SOCIALACCOUNT_PROVIDERS settings
    or SocialApp database entries, as django-allauth supports both configuration methods.
    """
    available_providers = set()

    configured_providers = getattr(settings, "SOCIALACCOUNT_PROVIDERS", {})

    available_providers.update(configured_providers.keys())

    try:
        social_apps = SocialApp.objects.all()
        for social_app in social_apps:
            available_providers.add(social_app.provider)
    except Exception as e:
        logger.warning("Error retrieving SocialApp entries", error=str(e))

    available_providers_list = sorted(list(available_providers))

    return {
        "available_social_providers": available_providers_list,
        "has_social_providers": len(available_providers_list) > 0,
    }
