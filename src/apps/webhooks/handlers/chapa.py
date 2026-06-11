"""Chapa webhook event router."""

from __future__ import annotations

import logging
from typing import Any

from apps.escrow.services import EscrowService
from apps.payments.models import Payment

logger = logging.getLogger(__name__)

_SUCCESS_STATUSES = {"success", "completed", "paid"}
_FAILURE_STATUSES = {"failed", "declined", "expired", "cancelled"}
_SUCCESS_TRANSFER_EVENTS = {"transfer.success", "transfer.completed", "transfer.paid"}
_FAILURE_TRANSFER_EVENTS = {"transfer.failed", "transfer.cancelled", "transfer.reversed"}


def handle_chapa_event(event_type: str, data: dict[str, Any]) -> dict[str, Any]:
    """
    Chapa payloads vary by event. We branch on shape:
      - presence of `transfer_reference` → payout webhook
      - presence of `tx_ref` → funding webhook
    """
    status_value = (data.get("status") or "").lower()
    transfer_reference = data.get("transfer_reference") or data.get("reference")
    tx_ref = data.get("tx_ref")

    if transfer_reference:
        if status_value in _SUCCESS_STATUSES or event_type in _SUCCESS_TRANSFER_EVENTS:
            success = True
        elif status_value in _FAILURE_STATUSES or event_type in _FAILURE_TRANSFER_EVENTS:
            success = False
        else:
            return {"status": "ignored", "reason": "indeterminate transfer outcome"}

        return EscrowService().verify_transfer_to_freelancer(
            provider_name="chapa",
            transfer_reference=transfer_reference,
            success=success,
            details=data,
        )

    if tx_ref:
        if status_value in _SUCCESS_STATUSES:
            return EscrowService().verify_funding(tx_ref=tx_ref)
        if status_value in _FAILURE_STATUSES:
            payment = Payment.objects.filter(
                provider_transactionn_id=tx_ref, provider="chapa"
            ).first()
            if payment and payment.status != "failed":
                payment.status = "failed"
                payment.save(update_fields=["status"])
            return {"status": "failed", "payment_id": getattr(payment, "id", None)}

    logger.info("Chapa webhook: unhandled event %s / status %s", event_type, status_value)
    return {"status": "ignored", "reason": "unhandled chapa event"}
