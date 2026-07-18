from pathlib import Path


def test_cli_docs_cover_agent_safe_generation_and_api_parity():
    content = Path("apps/docs/content/api/cli.md").read_text()

    assert "djass generate" in content
    assert "djass options" in content
    assert "djass projects create" in content
    assert "djass projects list" in content
    assert "djass projects get" in content
    assert "djass projects status" in content
    assert "djass projects download" in content
    assert "must be new or empty" in content
    assert "never prints the key" in content
