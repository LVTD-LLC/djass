from django.urls import path
from django.views.generic import RedirectView

from apps.docs.views import docs_markdown_view, docs_page_view

urlpatterns = [
    path(
        "",
        RedirectView.as_view(
            url="/docs/getting-started/introduction/",
            permanent=False,
        ),
        name="docs_home",
    ),
    path("<str:category>/<str:page>.md", docs_markdown_view, name="docs_page_markdown"),
    path("<str:category>/<str:page>/.md", docs_markdown_view, name="docs_page_markdown_slash"),
    path("<str:category>/<str:page>/", docs_page_view, name="docs_page"),
]
