"""
ASGI config for djass project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.0/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from starlette.applications import Starlette
from starlette.routing import Mount

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djass.settings")

django_application = get_asgi_application()

from apps.mcp.hosted import application as mcp_application  # noqa: E402

application = Starlette(
    routes=[
        Mount("/mcp", app=mcp_application),
        Mount("/", app=django_application),
    ]
)
