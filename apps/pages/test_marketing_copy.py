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
    assert "See the premium agency plan" not in content
    assert "API-first delivery for modern Django agencies" not in content


def test_pricing_template_uses_product_led_copy():
    content = PRICING_TEMPLATE.read_text()

    assert "One plan for serious Django SaaS work" in content
    assert "$999 one-time for founders and teams shipping Django SaaS repeatedly" in content
    assert "Unlimited starter generations for new SaaS products, experiments, and internal tools" in content
    assert "Djass Premium Plan" in content
    assert "Review the open-source baseline" in content
    assert "Need full control?" not in content
    assert "self-host for free" not in content
    assert "Premium Agency Plan" not in content
    assert "agencies that ship client SaaS repeatedly" not in content
