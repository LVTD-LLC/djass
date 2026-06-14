from pathlib import Path


def test_premium_offer_workflow_copy_crosses_out_lifetime_price():
    content = Path("apps/docs/content/workflows/premium-offer-page-copy.md").read_text()

    assert "founders, solo builders, and product teams" in content
    assert "$10" in content
    assert "$100" in content
    assert "$200" in content
    assert "$999" in content
    assert "Launch pricing" in content
    assert "Review launch pricing" in content
    assert "limited number of spots" in content
    assert "Launch spot schedule" in content
    assert ("paid " + "seats") not in content.lower()
    assert ("scar" + "city") not in content.lower()
    assert "client SaaS" not in content
