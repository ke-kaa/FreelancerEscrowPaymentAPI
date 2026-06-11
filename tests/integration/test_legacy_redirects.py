"""Integration — legacy flat URLs 301-redirect to /api/v1/."""

import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def api():
    return APIClient()


@pytest.mark.parametrize("legacy,target", [
    ("/api/account/register/", "/api/v1/account/register/"),
    ("/api/account/", "/api/v1/account/"),
    ("/escrow/", "/api/v1/escrow/"),
    ("/projects/client/list/", "/api/v1/projects/client/list/"),
    ("/payments/payout-methods/", "/api/v1/payments/payout-methods/"),
])
def test_legacy_path_redirects_to_v1(api, legacy, target):
    r = api.get(legacy)
    assert r.status_code == 301, r.content
    assert r["Location"] == target


def test_webhook_path_not_redirected(api):
    # Webhooks intentionally stay un-versioned.
    r = api.post("/webhooks/stripe/", data=b"{}", content_type="application/json")
    assert r.status_code != 301
