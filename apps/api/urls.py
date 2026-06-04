from django.urls import path

from apps.api.mcp import mcp_endpoint, mcp_prompt
from apps.api.views import api

urlpatterns = [
    path("mcp", mcp_endpoint, name="mcp_endpoint"),
    path("mcp/", mcp_endpoint, name="mcp_endpoint_slash"),
    path("mcp/prompt", mcp_prompt, name="mcp_prompt"),
    path("mcp/prompt/", mcp_prompt, name="mcp_prompt_slash"),
    path("", api.urls),
]
