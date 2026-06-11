"""Stripe webhook event router — translates events to escrow service calls."""

from __future__ import annotations

import logging
from typing import Any

from apps.escrow.services import EscrowService
from apps.payments.models import Payment

logger = logging.getLogger(__name__)

_SUCCESS_TRANSFER = {"transfer.paid", "transfer.succeeded", "transfer.completed"}
_FAILURE_TRANSFER = {"transfer.failed", "transfer.canceled", "transfer.reversed"}
_SUCCESS_PAYOUT = {"payout.paid", "payout.succeeded"}
_FAILURE_PAYOUT = {"payout.failed", "payout.canceled"}


def handle_stripe_event(event_type: str, data: dict[str, Any]) -> dict[str, Any]:
    if event_type == "payment_intent.succeeded":
        intent_id = data.get("id")
        if not intent_id:
            return {"status": "ignored", "reason": "missing intent id"}
        return EscrowService().verify_funding(tx_ref=intent_id)

    if event_type == "payment_intent.payment_failed":
        intent_id = data.get("id")
        payment = Payment.objects.filter(
            provider_transactionn_id=intent_id, provider="stripe"
        ).first()
        if payment and payment.status != "failed":
            payment.status = "failed"
            payment.save(update_fields=["status"])
        return {"status": "failed", "payment_id": getattr(payment, "id", None)}

    if event_type in _SUCCESS_TRANSFER | _FAILURE_TRANSFER:
        transfer_id = data.get("id")
        success = event_type in _SUCCESS_TRANSFER
        return EscrowService().verify_transfer_to_freelancer(
            provider_name="stripe",
            transfer_reference=transfer_id,
            success=success,
            details=data,
        )

    if event_type in _SUCCESS_PAYOUT | _FAILURE_PAYOUT:
        transfer_id = data.get("id")
        success = event_type in _SUCCESS_PAYOUT
        return EscrowService().verify_transfer_to_freelancer(
            provider_name="stripe",
            transfer_reference=transfer_id,
            success=success,
            details=data,
        )

    logger.info("Stripe webhook: unhandled event %s", event_type)
    return {"status": "ignored", "reason": f"unhandled event {event_type}"}
