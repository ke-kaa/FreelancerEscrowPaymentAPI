"""
Project URL configuration.

All API endpoints are namespaced under /api/v1/. Webhook ingress lives at
/webhooks/<provider>/ (not versioned — third-party providers configure
those URLs directly and we don't want to break them on version bumps).

Legacy flat paths (/api/, /escrow/, /projects/, /payments/) 301-redirect
to /api/v1/* for one release window, then are removed.
"""

from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("interfaces.rest.v1.urls")),
    path("webhooks/", include("apps.webhooks.urls")),

    # ── 301 redirects from old flat paths ───────────────────────────────────
    # `<path:rest>` requires at least one trailing char, so explicit empty
    # patterns cover the bare prefix.
    #
    # Only the LEGACY paths that existed before /api/v1/ get redirected.
    # `/api/v1/*` itself is the new surface — never catch-all `/api/` or it
    # rewrites /api/v1/docs -> /api/v1/v1/docs in an infinite loop.
    path("escrow/", RedirectView.as_view(url="/api/v1/escrow/", permanent=True, query_string=True)),
    path("projects/", RedirectView.as_view(url="/api/v1/projects/", permanent=True, query_string=True)),
    path("payments/", RedirectView.as_view(url="/api/v1/payments/", permanent=True, query_string=True)),
    path("api/account/", RedirectView.as_view(url="/api/v1/account/", permanent=True, query_string=True)),
    path("api/account/<path:rest>", RedirectView.as_view(url="/api/v1/account/%(rest)s", permanent=True, query_string=True)),
    path("escrow/<path:rest>", RedirectView.as_view(url="/api/v1/escrow/%(rest)s", permanent=True, query_string=True)),
    path("projects/<path:rest>", RedirectView.as_view(url="/api/v1/projects/%(rest)s", permanent=True, query_string=True)),
    path("payments/<path:rest>", RedirectView.as_view(url="/api/v1/payments/%(rest)s", permanent=True, query_string=True)),
]
