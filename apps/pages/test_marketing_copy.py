from pathlib import Path

LANDING_TEMPLATE = Path("frontend/templates/pages/landing-page.html")
PRICING_TEMPLATE = Path("frontend/templates/pages/pricing.html")


def test_landing_template_uses_product_led_copy():
    content = LANDING_TEMPLATE.read_text()

    assert "Project generator for Django SaaS" in content
    assert "Generate the codebase. Ship the product." in content
    assert "production-ready" in content
    assert "hosted project generator" in content
    assert "Create a free account" in content
    assert (
        """<a href="{% url 'account_login' %}" class="dj-button dj-button-secondary sm:min-w-44">Sign in</a>"""
        in content
    )
    assert "Review free access" in content
    assert "AI agent handoff" in content
    assert "/skill.md" in content
    assert "djass_openapi_docs_url" in content
    assert "premium" not in content.lower()
    assert "API-first delivery for modern Django agencies" not in content


def test_pricing_template_crosses_out_lifetime_price():
    content = PRICING_TEMPLATE.read_text()

    assert "Free access while the generator improves" in content
    assert "$999" in content
    assert "line-through" in content
    assert "Free access while Djass improves" in content
    assert "Djass generator access" in content
    assert "No payment required during the current feedback window" in content
    assert "feedback" in content.lower()
    assert "Review the starter repository" in content
    assert "agencies that ship client SaaS repeatedly" not in content
