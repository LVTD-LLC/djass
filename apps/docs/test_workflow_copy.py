from pathlib import Path


def test_premium_offer_workflow_copy_crosses_out_lifetime_price():
    content = Path("apps/docs/content/workflows/premium-offer-page-copy.md").read_text()

    assert "founders, solo builders, and product teams" in content
    assert "$999" in content
    assert "crossed out" in content
    assert "Free access" in content
    assert "Review free access" in content
    assert "feedback" in content.lower()
    assert "client SaaS" not in content
