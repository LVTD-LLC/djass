import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


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
