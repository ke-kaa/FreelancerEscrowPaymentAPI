"""
StripeGateway — adapter implementing PaymentGateway over StripeClient.

Translates DTOs to/from Stripe SDK objects. Maps Stripe errors to
`ProviderError`. No DB access; no business logic.
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import Any

import stripe
from django.conf import settings

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

from .client import StripeClient
from .webhooks import verify_stripe_webhook

logger = logging.getLogger(__name__)


class StripeGateway:
    provider_name = "stripe"

    def __init__(self, client: StripeClient | None = None) -> None:
        self._client = client or StripeClient()

    # ─── PaymentGateway methods ─────────────────────────────────────────────

    def charge(self, request: ChargeRequest) -> ChargeResult:
        try:
            tx_ref = f"escrow-fund-{uuid.uuid4().hex[:10]}"
            intent = self._client.create_payment_intent(
                amount_cents=int(request.amount * 100),
                currency=(request.currency or "usd").lower(),
                receipt_email=request.user_email,
                description=request.description or "Escrow funding",
                metadata={
                    "user_id": request.user_id,
                    "user_email": request.user_email,
                    "tx_ref": tx_ref,
                    "escrow_funding": "true",
                    **request.metadata,
                },
            )
        except stripe.error.StripeError as exc:
            raise self._wrap("charge", exc) from exc

        return ChargeResult(
            provider=self.provider_name,
            tx_ref=intent.id,
            client_secret=intent.client_secret,
            checkout_url=f"/payment/stripe/{intent.id}",
            raw=_to_dict(intent),
        )

    def verify(self, provider_transaction_id: str) -> VerifyResult:
        try:
            intent = self._client.retrieve_payment_intent(provider_transaction_id)
        except stripe.error.StripeError as exc:
            raise self._wrap("verify", exc) from exc

        return VerifyResult(
            provider=self.provider_name,
            provider_transaction_id=provider_transaction_id,
            succeeded=intent.status == "succeeded",
            status=intent.status,
            raw=_to_dict(intent),
        )

    def refund(self, request: RefundRequest) -> RefundResult:
        try:
            intent = self._client.retrieve_payment_intent(request.provider_transaction_id)
            if intent.status != "succeeded":
                raise ProviderError(
                    "Cannot refund unsuccessful payment",
                    details={"intent_status": intent.status},
                )
            charge_id = intent.latest_charge
            if not charge_id:
                raise ProviderError("No charge found for payment intent")

            params: dict[str, Any] = {
                "charge": charge_id,
                "metadata": {
                    "reason": request.reason,
                    "escrow_refund": "true",
                    "original_intent": request.provider_transaction_id,
                    **request.metadata,
                },
            }
            if request.amount is not None:
                params["amount"] = int(request.amount * 100)

            refund = self._client.create_refund(**params)
        except stripe.error.StripeError as exc:
            raise self._wrap("refund", exc) from exc

        return RefundResult(
            provider=self.provider_name,
            refund_id=refund.id,
            amount=request.amount,
            original_tx_ref=request.provider_transaction_id,
            raw=_to_dict(refund),
        )

    def transfer(self, request: TransferRequest) -> TransferResult:
        try:
            transfer_ref = f"freelancer-payment-{uuid.uuid4().hex[:10]}"
            destination = request.recipient.get("stripe_account_id")
            if not destination:
                raise ProviderError("Missing stripe_account_id in recipient")

            transfer = self._client.create_transfer(
                amount=int(request.amount * 100),
                currency=(request.currency or "usd").lower(),
                destination=destination,
                description=request.description or "Escrow payout",
                metadata={
                    "freelancer_id": str(request.recipient.get("user_id", "")),
                    "transfer_reference": transfer_ref,
                    "escrow_payout": "true",
                    **request.metadata,
                },
            )
        except stripe.error.StripeError as exc:
            raise self._wrap("transfer", exc) from exc

        return TransferResult(
            provider=self.provider_name,
            transfer_id=transfer.id,
            reference=transfer_ref,
            amount=request.amount,
            raw=_to_dict(transfer),
        )

    def verify_webhook(self, payload: bytes, signature: str):
        return verify_stripe_webhook(payload, signature, client=self._client)

    # ─── Stripe-specific extensions (not on Protocol) ────────────────────────

    def create_account_link(self, account_id: str) -> dict[str, Any]:
        """Stripe Connect onboarding link. Called by StripeOnboardingLinkView."""
        try:
            link = self._client.create_account_link(
                account_id=account_id,
                refresh_url=f"{settings.FRONTEND_DOMAIN}/onboarding/refresh",
                return_url=f"{settings.FRONTEND_DOMAIN}/onboarding/return",
            )
        except stripe.error.StripeError as exc:
            raise self._wrap("create_account_link", exc) from exc
        return {"url": link.url, "expires_at": link.expires_at}

    # ─── helpers ─────────────────────────────────────────────────────────────

    def _wrap(self, op: str, exc: stripe.error.StripeError) -> ProviderError:
        logger.error("Stripe %s failed: %s", op, exc)
        return ProviderError(
            f"Stripe {op} failed: {exc}",
            details={"op": op, "stripe_error": type(exc).__name__},
        )


def _to_dict(obj: Any) -> dict[str, Any]:
    """Coerce a Stripe SDK object into a JSON-serializable dict."""
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "__dict__"):
        return dict(obj.__dict__)
    return {"repr": repr(obj)}


# Avoid lint warning on unused import in some configurations
_ = Decimal
