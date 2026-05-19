from apps.core.agent_prompts import build_djass_agent_prompt


def test_agent_prompt_embeds_skill_without_outer_markdown_fence():
    prompt = build_djass_agent_prompt(
        "http://testserver/api/v1",
        "test-key",
        skill_md="# Skill\n\n```bash\necho ok\n```",
    )

    assert "export DJASS_BASE_URL=\"http://testserver/api/v1\"" in prompt
    assert "export DJASS_API_KEY=\"test-key\"" in prompt
    assert "---BEGIN SKILL.md---" in prompt
    assert "---END SKILL.md---" in prompt
    assert "```markdown" not in prompt
    assert "```bash\necho ok\n```" in prompt
