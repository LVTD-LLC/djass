import pytest
from django.urls import reverse

from apps.blog.choices import BlogPostStatus
from apps.blog.models import BlogPost

pytestmark = pytest.mark.django_db


def test_blog_index_uses_redesigned_header(client):
    BlogPost.objects.create(
        title="Shipping notes",
        description="What changed this week",
        slug="shipping-notes",
        tags="release",
        content="Hello world",
        status=BlogPostStatus.PUBLISHED,
    )

    response = client.get(reverse("blog_posts"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Djass Journal" in content
    assert "Build logs, product notes, and implementation details" in content


def test_blog_detail_uses_redesigned_shell(client):
    post = BlogPost.objects.create(
        title="API-first operations",
        description="Why this architecture matters",
        slug="api-first-operations",
        tags="architecture",
        content="# Intro\n\nThis is a test post.",
        status=BlogPostStatus.PUBLISHED,
    )

    response = client.get(reverse("blog_post", kwargs={"slug": post.slug}))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Back to blog" in content
    assert post.title in content
