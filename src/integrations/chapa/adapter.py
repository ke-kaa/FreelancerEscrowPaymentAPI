"""
ChapaGateway — adapter implementing PaymentGateway over ChapaClient.

Maps `requests.RequestException` to `ProviderError`. No DB access, no
business logic. Removes the duplicate POST bug from the legacy provider.
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import Any

import requests

from common.exception.domain import ProviderError
from common.patterns.ports import (
    ChargeRequest,
    ChargeResult,
    RefundRequest,
    RefundResult,
    TransferRequest,
    TransferResult,
    VerifyResult,
)

from .client import ChapaClient
from .webhooks import verify_chapa_webhook

logger = logging.getLogger(__name__)


class ChapaGateway:
    provider_name = "chapa"

    def __init__(self, client: ChapaClient | None = None) -> None:
        self._client = client or ChapaClient()

    def charge(self, request: ChargeRequest) -> ChargeResult:
        tx_ref = f"escrow-fund-{uuid.uuid4().hex[:10]}"
        payload = {
            "amount": str(request.amount),
            "currency": request.currency or "ETB",
            "email": request.user_email,
            "first_name": request.metadata.get("first_name", "Customer"),
            "last_name": request.metadata.get("last_name", "User"),
            "phone_number": request.metadata.get("phone_number", ""),
            "tx_ref": tx_ref,
            "callback_url": self._client.callback_url,
            "return_url": self._client.return_url,
            "customization": {
                "title": "Escrow Fund",
                "description": request.description or "Funding escrow for project",
            },
        }
        try:
            data = self._client.initialize_transaction(payload)
        except requests.RequestException as exc:
            raise self._wrap("charge", exc) from exc

        checkout_url = data.get("data", {}).get("checkout_url")
        return ChargeResult(
            provider=self.provider_name,
            tx_ref=tx_ref,
            client_secret=None,
            checkout_url=checkout_url,
            raw=data,
        )

    def verify(self, provider_transaction_id: str) -> VerifyResult:
        try:
            data = self._client.verify_transaction(provider_transaction_id)
        except requests.RequestException as exc:
            raise self._wrap("verify", exc) from exc

        status = data.get("status", "unknown")
        return VerifyResult(
            provider=self.provider_name,
            provider_transaction_id=provider_transaction_id,
            succeeded=status == "success",
            status=status,
            raw=data,
        )

    def refund(self, request: RefundRequest) -> RefundResult:
        try:
            original = self._client.verify_transaction(request.provider_transaction_id)
        except requests.RequestException as exc:
            raise self._wrap("refund", exc) from exc

        if original.get("status") != "success":
            raise ProviderError(
                "Cannot refund unsuccessful transaction",
                details={"chapa_status": original.get("status")},
            )

        amount = request.amount
        if amount is None:
            amount = original.get("data", {}).get("amount", 0)

        customer_email = original.get("data", {}).get("customer", {}).get("email", "")
        form_data = (
            f"reason={request.reason}"
            f"&amount={amount}"
            f"&meta[customer_id]={customer_email}"
            f"&meta[reference]=REF-{request.provider_transaction_id}"
            f"&meta[escrow_refund]=true"
        )
        try:
            data = self._client.refund(request.provider_transaction_id, form_data)
        except requests.RequestException as exc:
            raise self._wrap("refund", exc) from exc

        refund_id = data.get("data", {}).get("refund_id", "")
        return RefundResult(
            provider=self.provider_name,
            refund_id=refund_id,
            amount=Decimal(str(amount)) if amount else None,
            original_tx_ref=request.provider_transaction_id,
            raw=data,
        )

    def transfer(self, request: TransferRequest) -> TransferResult:
        recipient = request.recipient
        required = ("account_name", "account_number", "bank_code")
        missing = [k for k in required if not recipient.get(k)]
        if missing:
            raise ProviderError(
                "Missing Chapa recipient fields",
                details={"missing": missing},
            )

        reference = f"freelancer-payment-{uuid.uuid4().hex[:10]}"
        payload = {
            "account_name": recipient["account_name"],
            "account_number": recipient["account_number"],
            "amount": str(request.amount),
            "currency": request.currency or "ETB",
            "reference": reference,
            "bank_code": int(recipient["bank_code"]),
        }
        try:
            data = self._client.transfer(payload)
        except requests.RequestException as exc:
            raise self._wrap("transfer", exc) from exc

        transfer_id = data.get("data", {}).get("transfer_id", "")
        return TransferResult(
            provider=self.provider_name,
            transfer_id=transfer_id,
            reference=reference,
            amount=request.amount,
            raw=data,
        )

    def verify_webhook(self, payload: bytes, signature: str):
        return verify_chapa_webhook(payload, signature)

    # ─── Chapa-specific extensions ──────────────────────────────────────────

    def list_banks(self) -> list[dict[str, Any]]:
        try:
            data = self._client.list_banks()
        except requests.RequestException as exc:
            raise self._wrap("list_banks", exc) from exc
        return data.get("data", [])

    def verify_transfer(self, reference: str) -> dict[str, Any]:
        try:
            return self._client.verify_transfer(reference)
        except requests.RequestException as exc:
            raise self._wrap("verify_transfer", exc) from exc

    def _wrap(self, op: str, exc: requests.RequestException) -> ProviderError:
        logger.error("Chapa %s failed: %s", op, exc)
        return ProviderError(
            f"Chapa {op} failed: {exc}",
            details={"op": op, "request_error": type(exc).__name__},
        )
