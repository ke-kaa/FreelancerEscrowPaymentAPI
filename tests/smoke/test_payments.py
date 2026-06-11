"""Smoke — payment endpoints wired; webhook ingress reachable.

Real signature verification + idempotency lands in Phase 6 (apps/webhooks/).
For now we only verify the URLs resolve and respond (not 404 / not 500).
"""

import pytest

pytestmark = [pytest.mark.smoke, pytest.mark.django_db]

PAYOUT_METHODS_URL = "/payments/payout-methods/"
STRIPE_WEBHOOK_URL = "/webhooks/stripe/"
CHAPA_WEBHOOK_URL = "/webhooks/chapa/"


def test_payout_methods_requires_auth(api_client):
    r = api_client.get(PAYOUT_METHODS_URL)
    assert r.status_code in (401, 403)


def test_stripe_webhook_endpoint_reachable(api_client):
    # No signature header — view should reject (400/403) but MUST resolve.
    r = api_client.post(STRIPE_WEBHOOK_URL, data={}, format="json")
    assert r.status_code != 404
    assert r.status_code < 500, r.content


def test_chapa_webhook_endpoint_reachable(api_client):
    r = api_client.post(CHAPA_WEBHOOK_URL, data={}, format="json")
    assert r.status_code != 404
    assert r.status_code < 500, r.content
