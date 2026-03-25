from pathlib import Path


def test_premium_offer_workflow_copy_is_product_led():
    content = Path("apps/docs/content/workflows/premium-offer-page-copy.md").read_text()

    assert "founders, solo builders, and product teams" in content
    assert "See pricing" in content
    assert "Need full control?" not in content
    assert "premium agency plan" not in content.lower()
    assert "client SaaS" not in content
