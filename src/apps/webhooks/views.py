"""
Webhook ingress.

Pipeline per provider:
    1. Read raw request body (bytes).
    2. Verify signature via the integration adapter.
    3. Insert WebhookEvent atomically — uniqueness on (provider, external_event_id)
       absorbs replays.
    4. Enqueue process_webhook_event.delay(id).
    5. Return 200.

Routing + DB mutations live in the Celery task, NOT in the request path.
"""

from __future__ import annotations

import logging

from django.db import IntegrityError, transaction
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from common.exception.domain import ProviderError
from integrations.chapa.webhooks import verify_chapa_webhook
from integrations.stripe.webhooks import verify_stripe_webhook

from .models import WebhookEvent
from .tasks import process_webhook_event

logger = logging.getLogger(__name__)


def _ingest(provider: str, verifier, request) -> Response:
    payload = request.body
    signature = (
        request.headers.get("Stripe-Signature")
        or request.headers.get("Chapa-Signature")
        or request.headers.get("X-Chapa-Signature")
        or ""
    )
    try:
        event = verifier(payload, signature)
    except ProviderError as exc:
        logger.warning("%s webhook rejected: %s", provider, exc.message)
        return Response(exc.to_dict(), status=status.HTTP_400_BAD_REQUEST)

    try:
        # Savepoint so the unique-constraint violation doesn't poison any
        # outer transaction (e.g. a test wrapping the request in atomic()).
        with transaction.atomic():
            record = WebhookEvent.objects.create(
                provider=event.provider,
                external_event_id=event.event_id,
                event_type=event.event_type,
                raw_payload=event.data,
                signature=signature,
            )
    except IntegrityError:
        logger.info("%s webhook duplicate %s", provider, event.event_id)
        return Response({"status": "duplicate"}, status=status.HTTP_200_OK)

    process_webhook_event.delay(record.id)
    return Response({"status": "queued", "event_id": record.id}, status=status.HTTP_200_OK)


class StripeWebhookIngressView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []

    def post(self, request):
        return _ingest("stripe", verify_stripe_webhook, request)


class ChapaWebhookIngressView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []

    def post(self, request):
        return _ingest("chapa", verify_chapa_webhook, request)
