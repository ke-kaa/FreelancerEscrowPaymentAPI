"""
Chapa webhook HMAC verification.

Chapa signs the raw body with HMAC-SHA256 using the secret in the
`Chapa-Signature` header. Constant-time comparison avoids timing leaks.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging

from django.conf import settings

from common.exception.domain import ProviderError
from common.patterns.ports import WebhookEvent

logger = logging.getLogger(__name__)


def verify_chapa_webhook(payload: bytes, signature: str) -> WebhookEvent:
    secret = getattr(settings, "CHAPA_WEBHOOK_SECRET", "")
    if not secret:
        # Fail closed: cannot trust any payload without a configured secret.
        logger.error("Chapa webhook: CHAPA_WEBHOOK_SECRET not configured")
        raise ProviderError("Chapa webhook secret not configured")

    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(expected, signature):
        logger.warning("Chapa webhook: signature mismatch")
        raise ProviderError("Invalid Chapa webhook signature")

    try:
        body = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.warning("Chapa webhook: malformed payload — %s", exc)
        raise ProviderError("Malformed Chapa webhook payload") from exc

    event_id = str(body.get("tx_ref") or body.get("reference") or body.get("id") or "")
    event_type = body.get("event") or body.get("status") or "unknown"
    return WebhookEvent(
        provider="chapa",
        event_id=event_id,
        event_type=event_type,
        data=body,
        raw=body,
    )
