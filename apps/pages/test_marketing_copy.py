from pathlib import Path


LANDING_TEMPLATE = Path("frontend/templates/pages/landing-page.html")
FREE_ACCESS_TEMPLATE = Path("frontend/templates/pages/free-access.html")


def test_landing_template_uses_product_led_copy():
    content = LANDING_TEMPLATE.read_text()

    assert "Django SaaS starter, without setup drag" in content
    assert "production-ready" in content
    assert "Founders, product teams, and solo builders" in content
    assert "Create your Djass account" in content
    assert "Sign in to your dashboard" in content
    assert "Create your free account" in content
    assert "premium" not in content.lower()
    assert "API-first delivery for modern Django agencies" not in content


def test_free_access_template_uses_feedback_led_copy():
    content = FREE_ACCESS_TEMPLATE.read_text()

    assert "Free access while Djass improves" in content
    assert "Generate Django SaaS starters for free." in content
    assert "Djass Free Access" in content
    assert "feedback" in content.lower()
    assert "Review the open-source baseline" in content
    assert "Need full control?" not in content
    assert "$999" not in content
    assert "payment" not in content.lower()
    assert "premium" not in content.lower()
    assert "agencies that ship client SaaS repeatedly" not in content
