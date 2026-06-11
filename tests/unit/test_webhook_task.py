"""Unit — process_webhook_event task transitions WebhookEvent through states."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.webhooks.models import WebhookEvent
from apps.webhooks.tasks import process_webhook_event

pytestmark = pytest.mark.django_db


def _make_event(provider="stripe", status="pending", event_type="ping"):
    return WebhookEvent.objects.create(
        provider=provider,
        external_event_id=f"evt-{provider}-{status}-{event_type}",
        event_type=event_type,
        raw_payload={"id": "x"},
        status=status,
    )


def test_already_processed_short_circuits():
    evt = _make_event(status="processed")
    result = process_webhook_event.apply(args=[evt.id]).get()
    assert result == {"status": "processed", "idempotent": True}


def test_missing_event_returns_error():
    result = process_webhook_event.apply(args=[99999]).get()
    assert result["status"] == "error"


def test_unknown_provider_marks_failed():
    evt = _make_event(provider="paypal")
    result = process_webhook_event.apply(args=[evt.id]).get()
    assert result["status"] == "error"
    evt.refresh_from_db()
    assert evt.status == "failed"
    assert "no handler" in evt.last_error


def test_successful_routing_marks_processed():
    evt = _make_event(provider="stripe", event_type="ping")
    fake_handler = lambda event_type, data: {"status": "ok"}  # noqa: E731
    with patch.dict("apps.webhooks.tasks._HANDLERS", {"stripe": fake_handler}):
        result = process_webhook_event.apply(args=[evt.id]).get()
    assert result == {"status": "ok"}
    evt.refresh_from_db()
    assert evt.status == "processed"
    assert evt.processed_at is not None
    assert evt.attempts == 1
