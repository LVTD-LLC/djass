from pathlib import Path

LANDING_TEMPLATE = Path("frontend/templates/pages/landing-page.html")
PRICING_TEMPLATE = Path("frontend/templates/pages/pricing.html")


def test_landing_template_uses_product_led_copy():
    content = LANDING_TEMPLATE.read_text()

    assert "Django SaaS starter, without setup drag" in content
    assert "production-ready" in content
    assert "Founders, product teams, and solo builders" in content
    assert "Create your Djass account" in content
    assert "Sign in to your dashboard" in content
    assert "See pricing and what's included" in content
    assert "Agent flow" in content
    assert "/skill.md" in content
    assert "premium" not in content.lower()
    assert "API-first delivery for modern Django agencies" not in content


def test_pricing_template_crosses_out_lifetime_price():
    content = PRICING_TEMPLATE.read_text()

    assert "One plan for serious Django SaaS work" in content
    assert "$999" in content
    assert "line-through" in content
    assert "Free for now while Djass improves" in content
    assert "Djass Premium Plan" in content
    assert "No payment required during the current feedback window" in content
    assert "feedback" in content.lower()
    assert "Review the open-source baseline" in content
    assert "agencies that ship client SaaS repeatedly" not in content
