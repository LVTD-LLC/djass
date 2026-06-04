from django.urls import path

from apps.mcp.views import mcp_endpoint, mcp_project_download, mcp_prompt

urlpatterns = [
    path("mcp", mcp_endpoint, name="mcp_endpoint"),
    path("mcp/", mcp_endpoint, name="mcp_endpoint_slash"),
    path("mcp/prompt", mcp_prompt, name="mcp_prompt"),
    path("mcp/prompt/", mcp_prompt, name="mcp_prompt_slash"),
    path(
        "mcp/projects/<int:project_id>/download",
        mcp_project_download,
        name="mcp_project_download",
    ),
    path(
        "mcp/projects/<int:project_id>/download/",
        mcp_project_download,
        name="mcp_project_download_slash",
    ),
]
