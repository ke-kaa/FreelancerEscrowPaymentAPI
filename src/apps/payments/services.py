"""
PaymentService — translates app-layer calls into PaymentGateway calls.

This service does NOT mutate Escrow / Payment rows. It only orchestrates
provider invocations. State changes live in EscrowService (Phase 5).

Gateways are injected via constructor; defaults resolve through the
registry. On gateway failure, `ProviderError` propagates — callers handle
or convert as needed.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from common.exception.domain import ProviderError
from common.patterns.ports import (
    ChargeRequest,
    ChargeResult,
    PaymentGateway,
    RefundRequest,
    RefundResult,
    TransferRequest,
    TransferResult,
    VerifyResult,
)
from integrations import get_gateway

from .models import PayoutMethod

logger = logging.getLogger(__name__)


class PaymentService:
    """Provider-agnostic facade over `PaymentGateway`."""

    def __init__(
        self,
        *,
        default_provider: str | None = None,
        gateway: PaymentGateway | None = None,
    ) -> None:
        """
        Args:
            default_provider: Provider name to use when callers omit one.
            gateway:          Pre-built gateway (DI for tests). When set,
                              `default_provider` is derived from it.
        """
        if gateway is not None:
            self._injected_gateway = gateway
            self.default_provider = gateway.provider_name
        else:
            self._injected_gateway = None
            self.default_provider = default_provider

    def _resolve(self, provider_name: str | None) -> tuple[PaymentGateway, str]:
        if self._injected_gateway is not None and (
            provider_name is None or provider_name == self._injected_gateway.provider_name
        ):
            return self._injected_gateway, self._injected_gateway.provider_name
        name = provider_name or self.default_provider
        if not name:
            raise ValueError("provider_name is required (no default configured).")
        return get_gateway(name), name

    # ─── public API ──────────────────────────────────────────────────────────

    def init_charge(
        self,
        *,
        user,
        amount: Decimal,
        provider_name: str | None = None,
        description: str = "",
        metadata: dict[str, str] | None = None,
        currency: str | None = None,
    ) -> ChargeResult:
        gateway, _ = self._resolve(provider_name)
        meta = dict(metadata or {})
        # Carry user names through metadata so Chapa adapter can use them.
        if hasattr(user, "first_name"):
            meta.setdefault("first_name", user.first_name or "")
            meta.setdefault("last_name", user.last_name or "")
        if hasattr(user, "phone_number"):
            meta.setdefault("phone_number", user.phone_number or "")

        request = ChargeRequest(
            user_id=str(user.id),
            user_email=user.email,
            amount=amount,
            currency=currency or _default_currency(gateway.provider_name),
            description=description,
            metadata=meta,
        )
        return gateway.charge(request)

    def verify_payment(
        self, *, provider_name: str, provider_transaction_id: str
    ) -> VerifyResult:
        gateway, _ = self._resolve(provider_name)
        return gateway.verify(provider_transaction_id)

    def refund(
        self,
        *,
        provider_name: str,
        provider_transaction_id: str,
        amount: Decimal | None = None,
        reason: str = "Project refund",
    ) -> RefundResult:
        gateway, _ = self._resolve(provider_name)
        return gateway.refund(
            RefundRequest(
                provider_transaction_id=provider_transaction_id,
                amount=amount,
                reason=reason,
            )
        )

    def transfer_to_freelancer(
        self,
        *,
        freelancer,
        amount: Decimal,
        provider_name: str | None = None,
        currency: str | None = None,
        description: str = "",
        metadata: dict[str, str] | None = None,
    ) -> TransferResult:
        gateway, name = self._resolve(provider_name)
        recipient = self._get_freelancer_payout_method(freelancer, name)
        if recipient is None:
            raise ProviderError(
                f"No active {name} payout method for freelancer",
                details={"freelancer_id": str(freelancer.id), "provider": name},
            )

        request = TransferRequest(
            recipient=recipient,
            amount=amount,
            currency=currency or _default_currency(name),
            description=description,
            metadata=dict(metadata or {}),
        )
        return gateway.transfer(request)

    # ─── private ─────────────────────────────────────────────────────────────

    def _get_freelancer_payout_method(self, freelancer, provider_name: str) -> dict[str, Any] | None:
        payout_method = (
            PayoutMethod.objects.filter(
                user=freelancer, provider=provider_name, is_active=True
            )
            .order_by("-is_default", "-created_at")
            .first()
        )
        if not payout_method:
            return None

        if provider_name == "chapa":
            details = getattr(payout_method, "chapa_details", None)
            if not details:
                return None
            return {
                "account_name": details.account_name,
                "account_number": details.account_number,
                "bank_code": details.bank_code,
                "bank_name": details.bank_name,
            }
        if provider_name == "stripe":
            details = getattr(payout_method, "stripe_details", None)
            if not details or not details.payouts_enabled:
                return None
            return {
                "stripe_account_id": details.stripe_account_id,
                "user_id": str(freelancer.id),
            }
        return None


def _default_currency(provider_name: str) -> str:
    return {"chapa": "ETB", "stripe": "USD"}.get(provider_name, "USD")
