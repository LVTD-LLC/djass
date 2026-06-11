from apps.core.agent_prompts import (
    DJASS_API_BASE_URL,
    build_djass_agent_prompt,
    build_djass_agent_skill_md,
)


def test_agent_skill_uses_canonical_api_base_url():
    skill_md = build_djass_agent_skill_md()

    assert f"`{DJASS_API_BASE_URL}`." in skill_md
    assert f'export DJASS_BASE_URL="{DJASS_API_BASE_URL}"' in skill_md
    assert "## Preferred MCP Workflow" in skill_md
    assert "## API Fallback Workflow" in skill_md
    assert "OpenAPI docs: https://djass.dev/api/docs" in skill_md
    assert "- `get_generator_options`" in skill_md
    assert "- `create_project`" in skill_md
    assert "- `get_project_download`" in skill_md
    assert "- `generate_project`" not in skill_md
    assert "which optional features and generator options they need" in skill_md
    assert "do not assume the server can write into the" in skill_md
    assert "Call `get_project_download`" in skill_md
    assert "djass_generation_options" not in skill_md
    assert "djass_create_project" not in skill_md
    assert "__DJASS_API_BASE_URL__" not in skill_md
    assert "__DJASS_OPENAPI_DOCS_URL__" not in skill_md
    assert "__DJASS_MCP_DOCS_URL__" not in skill_md


def test_agent_prompt_references_plain_skill_markdown_without_embedding_skill():
    prompt = build_djass_agent_prompt(
        "https://djass.dev/api/v1",
        "test-key",
        skill_url="http://testserver/skill.md",
    )

    assert 'export DJASS_BASE_URL="https://djass.dev/api/v1"' in prompt
    assert 'export DJASS_API_KEY="test-key"' in prompt
    assert "agent-skill" not in prompt
    assert "http://testserver/skill.md" in prompt
    assert "Read and follow the plain-text Djass skill instructions first" in prompt
    assert "Hosted Djass MCP URL: https://djass.dev/mcp" in prompt
    assert "https://djass.dev/mcp" in prompt
    assert "API key for hosted MCP bearer auth and HTTP fallback" in prompt
    assert "test-key" in prompt
    assert "This prompt includes a live `DJASS_API_KEY`" in prompt
    assert "djass_create_project" not in prompt
    assert "djass_get_project_download" not in prompt
    assert "Preferred path:" not in prompt
    assert "Use the skill workflow" not in prompt
    assert "`generate_project`" not in prompt
    assert "---BEGIN SKILL.md---" not in prompt
    assert "## API Fallback Workflow" not in prompt
    assert len(prompt.splitlines()) <= 20


def test_agent_prompt_derives_mcp_url_from_api_base_url():
    prompt = build_djass_agent_prompt(
        "https://staging.djass.example/api/v1",
        "test-key",
        skill_url="https://staging.djass.example/skill.md",
    )

    assert "Hosted Djass MCP URL: https://staging.djass.example/mcp" in prompt
    assert 'export DJASS_BASE_URL="https://staging.djass.example/api/v1"' in prompt
    assert "https://djass.dev/mcp" not in prompt
