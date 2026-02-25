import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_pricing_page_shows_one_time_copy(client):
    response = client.get(reverse("pricing"))
    assert response.status_code == 200

    content = response.content.decode()
    assert "$999" in content
    assert "Unlimited project generations" in content
    assert "Forever updates" in content
