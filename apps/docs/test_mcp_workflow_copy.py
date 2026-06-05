from pathlib import Path


def test_ai_agent_generation_workflow_has_starter_prompt():
    content = (
        Path(__file__).parent / "content/workflows/generate-project-with-ai-agent.md"
    ).read_text()

    assert "You have access to the Djass MCP server" in content
    assert "use get_generator_options for a local stdio Djass MCP server" in content
    assert "djass_generation_options for hosted Djass" in content
    assert "Use `get_generator_options` locally" in content
    assert "Do not treat `use_mcp`" in content
    assert "plugin becomes useful" in content
