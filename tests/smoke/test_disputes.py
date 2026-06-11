"""Smoke — disputes endpoints reachable."""

import pytest

pytestmark = [pytest.mark.smoke, pytest.mark.django_db]


def test_list_disputes_requires_auth(api_client):
    r = api_client.get("/api/v1/disputes/disputes/")
    assert r.status_code in (401, 403)


def test_authenticated_disputes_list(auth_client_api):
    r = auth_client_api.get("/api/v1/disputes/disputes/")
    assert r.status_code == 200, r.content
