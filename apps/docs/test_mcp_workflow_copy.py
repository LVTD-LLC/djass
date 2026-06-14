from pathlib import Path


def test_ai_agent_generation_workflow_has_starter_prompt():
    content = (
        Path(__file__).parent / "content/workflows/generate-project-with-ai-agent.md"
    ).read_text()

    assert "You have access to the Djass MCP server" in content
    assert "This is the production path for AI" in content
    assert "First call get_generator_options on the hosted Djass MCP server" in content
    assert "call get_project_download" in content
    assert "PGSandbox MCP testing workflow" in content
    assert ".agents/skills/pgsandbox-testing" in content
    assert "make test-local-postgres" in content
    assert "djass_generation_options" not in content
    assert "Do not treat `use_mcp`" in content
    assert "plugin becomes useful" in content
