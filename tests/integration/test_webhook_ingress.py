"""Integration — webhook ingress: signature gate + replay dedup."""

import hashlib
import hmac
import json
from unittest.mock import patch

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.webhooks.models import WebhookEvent
from common.exception.domain import ProviderError
from common.patterns.ports import WebhookEvent as DTOWebhookEvent

pytestmark = pytest.mark.django_db


@pytest.fixture
def api():
    return APIClient()


def test_forged_stripe_signature_returns_400(api):
    with patch("apps.webhooks.views.verify_stripe_webhook", side_effect=ProviderError("bad sig")):
        r = api.post("/webhooks/stripe/", data=b"{}", content_type="application/json", HTTP_STRIPE_SIGNATURE="bogus")
    assert r.status_code == 400
    assert r.json()["code"] == "provider_error"
    assert WebhookEvent.objects.count() == 0


def test_valid_stripe_event_persisted_and_queued(api):
    fake = DTOWebhookEvent(
        provider="stripe", event_id="evt_test_1", event_type="ping",
        data={"id": "evt_test_1"}, raw={"id": "evt_test_1"},
    )
    with patch("apps.webhooks.views.verify_stripe_webhook", return_value=fake), \
         patch("apps.webhooks.views.process_webhook_event.delay") as enqueue:
        r = api.post("/webhooks/stripe/", data=b'{"id":"evt_test_1"}', content_type="application/json")
    assert r.status_code == 200
    assert r.json()["status"] == "queued"
    assert WebhookEvent.objects.filter(provider="stripe", external_event_id="evt_test_1").exists()
    enqueue.assert_called_once()


def test_duplicate_event_returns_duplicate_no_reenqueue(api):
    fake = DTOWebhookEvent(
        provider="stripe", event_id="evt_test_dup", event_type="ping", data={}, raw={}
    )
    with patch("apps.webhooks.views.verify_stripe_webhook", return_value=fake), \
         patch("apps.webhooks.views.process_webhook_event.delay") as enqueue:
        r1 = api.post("/webhooks/stripe/", data=b"{}", content_type="application/json")
        r2 = api.post("/webhooks/stripe/", data=b"{}", content_type="application/json")
    assert r1.json()["status"] == "queued"
    assert r2.json()["status"] == "duplicate"
    assert WebhookEvent.objects.filter(external_event_id="evt_test_dup").count() == 1
    assert enqueue.call_count == 1


@override_settings(CHAPA_WEBHOOK_SECRET="testsecret")
def test_chapa_real_hmac_round_trip(api):
    body = json.dumps({"tx_ref": "chapa-tx-1", "status": "success"}).encode()
    sig = hmac.new(b"testsecret", body, hashlib.sha256).hexdigest()
    with patch("apps.webhooks.views.process_webhook_event.delay"):
        r = api.post("/webhooks/chapa/", data=body, content_type="application/json", HTTP_CHAPA_SIGNATURE=sig)
    assert r.status_code == 200, r.content
    assert WebhookEvent.objects.filter(provider="chapa", external_event_id="chapa-tx-1").exists()


@override_settings(CHAPA_WEBHOOK_SECRET="testsecret")
def test_chapa_bad_signature_rejected(api):
    body = b'{"tx_ref":"x","status":"success"}'
    r = api.post("/webhooks/chapa/", data=body, content_type="application/json", HTTP_CHAPA_SIGNATURE="wrong")
    assert r.status_code == 400
    assert WebhookEvent.objects.count() == 0
