from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

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


def test_blog_posts_are_sorted_newest_first(client):
    old_post = BlogPost.objects.create(
        title="Old post",
        description="First post",
        slug="old-post",
        tags="release",
        content="Old",
        status=BlogPostStatus.PUBLISHED,
    )
    new_post = BlogPost.objects.create(
        title="New post",
        description="Latest post",
        slug="new-post",
        tags="release",
        content="New",
        status=BlogPostStatus.PUBLISHED,
    )

    now = timezone.now()
    BlogPost.objects.filter(pk=old_post.pk).update(created_at=now - timedelta(days=7))
    BlogPost.objects.filter(pk=new_post.pk).update(created_at=now)

    response = client.get(reverse("blog_posts"))

    assert response.status_code == 200
    ordered_slugs = [post.slug for post in response.context["blog_posts"]]
    assert ordered_slugs == ["new-post", "old-post"]


def test_blog_index_hides_draft_posts(client):
    BlogPost.objects.create(
        title="Draft",
        description="Hidden",
        slug="hidden-draft",
        tags="draft",
        content="Draft content",
        status=BlogPostStatus.DRAFT,
    )
    BlogPost.objects.create(
        title="Published",
        description="Visible",
        slug="visible-post",
        tags="release",
        content="Visible content",
        status=BlogPostStatus.PUBLISHED,
    )

    response = client.get(reverse("blog_posts"))

    assert response.status_code == 200
    slugs = [post.slug for post in response.context["blog_posts"]]
    assert "visible-post" in slugs
    assert "hidden-draft" not in slugs
