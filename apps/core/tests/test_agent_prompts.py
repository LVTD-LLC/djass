from apps.core.agent_prompts import (
    DJASS_API_BASE_URL,
    build_djass_agent_prompt,
    build_djass_agent_skill_md,
)


def test_agent_skill_uses_canonical_api_base_url():
    skill_md = build_djass_agent_skill_md()

    assert f"`{DJASS_API_BASE_URL}`." in skill_md
    assert f'export DJASS_BASE_URL="{DJASS_API_BASE_URL}"' in skill_md
    assert "__DJASS_API_BASE_URL__" not in skill_md


def test_agent_prompt_includes_runtime_without_embedding_skill():
    prompt = build_djass_agent_prompt(
        "https://djass.dev/api/v1",
        "test-key",
    )

    assert "export DJASS_BASE_URL=\"https://djass.dev/api/v1\"" in prompt
    assert "export DJASS_API_KEY=\"test-key\"" in prompt
    assert "agent-skill" not in prompt
    assert "---BEGIN SKILL.md---" not in prompt
    assert "## API Workflow" not in prompt
