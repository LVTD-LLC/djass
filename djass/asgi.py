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


def _mcp_routes() -> list[Route]:
    routes = []
    for route in mcp_application.routes:
        if not isinstance(route, Route):
            continue
        routes.append(_mcp_route(route))
        if route.path == "/mcp":
            alias_name = f"{route.name}_slash" if route.name else "mcp_slash"
            routes.append(
                _mcp_route(
                    Route(
                        "/mcp/",
                        endpoint=route.endpoint,
                        methods=route.methods,
                        name=alias_name,
                        include_in_schema=route.include_in_schema,
                    )
                )
            )
    return routes


application = Starlette(
    routes=[
        *_mcp_routes(),
        Mount("/", app=django_application),
    ],
    lifespan=mcp_application.router.lifespan_context,
)
