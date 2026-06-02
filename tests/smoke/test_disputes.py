"""Smoke — disputes.

NOTE: apps.disputes.urls is NOT mounted in config/urls.py — this is the
Phase 7 fix called out in MIGRATION_TODO.md. Re-enable these tests once
disputes is included under /api/v1/.
"""

import pytest

pytestmark = [pytest.mark.smoke, pytest.mark.django_db]


@pytest.mark.skip(reason="apps.disputes.urls not mounted yet — Phase 7")
def test_list_disputes_requires_auth(api_client):
    r = api_client.get("/disputes/")
    assert r.status_code in (401, 403)
