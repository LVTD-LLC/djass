from django.urls import path

from apps.mcp.views import mcp_project_download, mcp_prompt, mcp_protected_resource_metadata

urlpatterns = [
    path(
        ".well-known/oauth-protected-resource/mcp",
        mcp_protected_resource_metadata,
        name="mcp_oauth_protected_resource_metadata",
    ),
    path(
        ".well-known/oauth-protected-resource/mcp/",
        mcp_protected_resource_metadata,
        name="mcp_oauth_protected_resource_metadata_slash",
    ),
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
