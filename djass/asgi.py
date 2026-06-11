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


class McpRootPathAdapter:
    """Serve the mounted MCP app at both /mcp and /mcp/ without a redirect."""

    def __init__(self, app, root_path: str):
        self.app = app
        self.root_path = root_path

    async def __call__(self, scope, receive, send):
        adapted_scope = {
            **scope,
            "path": "/",
            "root_path": f"{scope.get('root_path', '')}{self.root_path}",
        }
        await self.app(adapted_scope, receive, send)


application = Starlette(
    routes=[
        Route(
            "/mcp",
            endpoint=McpRootPathAdapter(mcp_application, "/mcp"),
            methods=["GET", "POST", "DELETE", "OPTIONS"],
        ),
        Route(
            "/mcp/",
            endpoint=McpRootPathAdapter(mcp_application, "/mcp"),
            methods=["GET", "POST", "DELETE", "OPTIONS"],
        ),
        Mount("/", app=django_application),
    ],
    lifespan=mcp_application.router.lifespan_context,
)
