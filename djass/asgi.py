"""
ASGI config for djass project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.0/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from starlette.applications import Starlette
from starlette.routing import Mount, Route

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djass.settings")

django_application = get_asgi_application()

from apps.mcp.hosted import application as mcp_application  # noqa: E402


def _mcp_route(route: Route) -> Route:
    return Route(
        route.path,
        endpoint=route.endpoint,
        methods=route.methods,
        name=route.name,
        include_in_schema=route.include_in_schema,
        middleware=mcp_application.user_middleware,
    )


application = Starlette(
    routes=[
        *[_mcp_route(route) for route in mcp_application.routes if isinstance(route, Route)],
        Mount("/", app=django_application),
    ],
    lifespan=mcp_application.router.lifespan_context,
)
