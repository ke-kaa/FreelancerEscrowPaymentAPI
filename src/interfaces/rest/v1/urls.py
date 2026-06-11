"""
API v1 surface.

Single source of truth for the public REST surface. Each app's existing
url module is mounted under a namespace here. Adding a new app endpoint
goes through this file, not through editing config/urls.py.

Decision: views/serializers stay at apps/<x>/views.py / serializers.py;
this module references the per-app urlconfs. See docs/adr/0001-api-versioning.md.
"""

from __future__ import annotations

from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    # App routers.
    path("", include("apps.accounts.urls")),
    path("escrow/", include("apps.escrow.urls")),
    path("projects/", include("apps.projects.urls")),
    path("payments/", include("apps.payments.urls")),
    path("disputes/", include("apps.disputes.urls")),

    # OpenAPI schema + UIs.
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
