from pathlib import Path


def test_free_access_workflow_copy_is_feedback_led():
    content = Path("apps/docs/content/workflows/free-access-page-copy.md").read_text()

    assert "founders, solo builders, and product teams" in content
    assert "Create your free account" in content
    assert "feedback" in content.lower()
    assert "paid" not in content.lower()
    assert "payment" not in content.lower()
    assert "premium" not in content.lower()
    assert "client SaaS" not in content
