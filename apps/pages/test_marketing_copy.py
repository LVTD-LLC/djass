from pathlib import Path

LANDING_TEMPLATE = Path("frontend/templates/pages/landing-page.html")
PRICING_TEMPLATE = Path("frontend/templates/pages/pricing.html")


def test_landing_template_uses_product_led_copy():
    content = LANDING_TEMPLATE.read_text()

    assert "Agent-ready Django SaaS repo generator" in content
    assert "Generate agent-ready Django SaaS repos." in content
    assert "deployment defaults" in content
    assert "normal Django repo ZIP" in content
    assert "Generate your starter" in content
    assert "See pricing" in content
    assert "Generated with this cookiecutter" in content
    assert "FileBridge" in content
    assert "Tech Job Alerts" in content
    assert "Ask HN Digest" in content
    assert "https://osig.app/" in content
    assert "dj-logo-icon" in content
    assert "AI agent handoff" in content
    assert "/skill.md" in content
    assert "djass_openapi_docs_url" in content
    assert "premium" not in content.lower()
    assert "API-first delivery for modern Django agencies" not in content


def test_pricing_template_crosses_out_lifetime_price():
    content = PRICING_TEMPLATE.read_text()

    assert "Launch pricing" in content
    assert "$10" in content
    assert "$100" in content
    assert "$200" in content
    assert "$999" in content
    assert "Djass generator access" in content
    assert "10 launch spot" in content
    assert "Purchase once to unlock project generation" in content
    assert "Launch spot schedule" in content
    assert "Review the starter repository" in content
    assert ("scar" + "city") not in content.lower()
    assert ("paid " + "seats") not in content.lower()
    assert "agencies that ship client SaaS repeatedly" not in content
