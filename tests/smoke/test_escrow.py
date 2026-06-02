"""Smoke — escrow list endpoint reachable; auth required.

Full initiate→verify funding flow requires PaymentProvider mocking — added
in Phase 5 once `common/resilience/` and the integration adapters are in place.
"""

import pytest

pytestmark = [pytest.mark.smoke, pytest.mark.django_db]

ESCROW_LIST_URL = "/escrow/"


def test_escrow_list_requires_auth(api_client):
    r = api_client.get(ESCROW_LIST_URL)
    assert r.status_code in (401, 403)


def test_authenticated_escrow_list_returns_200(auth_client_api):
    r = auth_client_api.get(ESCROW_LIST_URL)
    assert r.status_code == 200, r.content
