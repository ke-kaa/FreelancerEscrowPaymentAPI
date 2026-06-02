"""
Stripe webhook signature verification.

`verify_stripe_webhook(raw_body, signature) -> WebhookEvent` is the ONLY
function the webhook ingress (apps/webhooks/ in Phase 6) calls. NO DB
writes here.
"""

from __future__ import annotations

import logging

import stripe

from common.exception.domain import ProviderError
from common.patterns.ports import WebhookEvent

logger = logging.getLogger(__name__)


def verify_stripe_webhook(payload: bytes, signature: str, *, client=None) -> WebhookEvent:
    """
    Args:
        payload:   Raw request body (bytes). Must be the exact bytes Stripe signed.
        signature: Value of the `Stripe-Signature` header.
        client:    Optional StripeClient (DI for tests).
    """
    if client is None:
        from .client import StripeClient
        client = StripeClient()

    try:
        event = client.construct_webhook_event(payload, signature)
    except ValueError as exc:
        logger.warning("Stripe webhook: invalid payload — %s", exc)
        raise ProviderError("Invalid Stripe webhook payload") from exc
    except stripe.error.SignatureVerificationError as exc:
        logger.warning("Stripe webhook: bad signature — %s", exc)
        raise ProviderError("Invalid Stripe webhook signature") from exc

    return WebhookEvent(
        provider="stripe",
        event_id=event["id"],
        event_type=event["type"],
        data=event.get("data", {}).get("object", {}),
        raw=dict(event),
    )
