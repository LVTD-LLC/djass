import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def use_plain_staticfiles_storage(settings):
    settings.STORAGES["staticfiles"]["BACKEND"] = (
        "django.contrib.staticfiles.storage.StaticFilesStorage"
    )


def test_docs_introduction_mentions_api_first_agent_ready(client):
    response = client.get(
        reverse(
            "docs_page",
            kwargs={"category": "getting-started", "page": "introduction"},
        )
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert "API-first, agent-ready" in content
    assert "human + agent execution" in content


def test_docs_page_has_markdown_variant(client):
    response = client.get(
        reverse(
            "docs_page_markdown",
            kwargs={"category": "getting-started", "page": "introduction"},
        )
    )

    assert response.status_code == 200
    assert response["Content-Type"] == "text/markdown; charset=utf-8"
    content = response.content.decode()
    assert content.startswith("# Introduction\n\n")
    assert "**API-first, agent-ready**" in content
    assert "<strong>API-first, agent-ready</strong>" not in content
    assert "---\ntitle:" not in content


def test_docs_page_supports_markdown_variant_after_trailing_slash(client):
    response = client.get("/docs/getting-started/introduction/.md")

    assert response.status_code == 200
    assert response["Content-Type"] == "text/markdown; charset=utf-8"
    assert response.content.decode().startswith("# Introduction\n\n")


def test_docs_markdown_variant_returns_404_for_missing_page(client):
    response = client.get("/docs/getting-started/missing-page.md")

    assert response.status_code == 404
