"""Celery task that processes a queued WebhookEvent."""

from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

from .handlers import handle_chapa_event, handle_stripe_event
from .models import WebhookEvent

logger = logging.getLogger(__name__)

_HANDLERS = {
    "stripe": handle_stripe_event,
    "chapa": handle_chapa_event,
}


@shared_task(bind=True, max_retries=5, default_retry_delay=30)
def process_webhook_event(self, event_id: int) -> dict:
    try:
        event = WebhookEvent.objects.get(id=event_id)
    except WebhookEvent.DoesNotExist:
        logger.error("process_webhook_event: id %s not found", event_id)
        return {"status": "error", "message": "event not found"}

    if event.status == "processed":
        return {"status": "processed", "idempotent": True}

    handler = _HANDLERS.get(event.provider)
    if not handler:
        event.status = "failed"
        event.last_error = f"no handler for provider {event.provider}"
        event.save(update_fields=["status", "last_error"])
        return {"status": "error", "message": event.last_error}

    event.status = "processing"
    event.attempts += 1
    event.save(update_fields=["status", "attempts"])

    try:
        result = handler(event.event_type, event.raw_payload)
        event.status = "processed"
        event.processed_at = timezone.now()
        event.last_error = ""
        event.save(update_fields=["status", "processed_at", "last_error"])
        return result
    except Exception as exc:
        logger.exception("process_webhook_event failed: %s", exc)
        event.status = "failed"
        event.last_error = str(exc)
        event.save(update_fields=["status", "last_error"])
        raise self.retry(exc=exc)
