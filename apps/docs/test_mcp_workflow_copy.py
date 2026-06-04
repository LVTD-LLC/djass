from pathlib import Path


def test_ai_agent_generation_workflow_has_starter_prompt():
    content = Path(
        "apps/docs/content/workflows/generate-project-with-ai-agent.md"
    ).read_text()

    assert "You have access to the Djass MCP server" in content
    assert "First call get_generator_options" in content
    assert "Do not treat `use_mcp`" in content
    assert "plugin becomes useful" in content
