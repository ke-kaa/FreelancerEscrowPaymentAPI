"""
Payment gateway port + shared DTOs.

Apps (services, views, tasks) depend on the `PaymentGateway` Protocol —
NOT on concrete adapters. Concrete adapters live in `integrations/<provider>/adapter.py`.

On failure, adapters raise `common.exception.domain.ProviderError`. They
do not return error dicts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class ChargeRequest:
    user_id: str
    user_email: str
    amount: Decimal
    currency: str = "USD"
    description: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ChargeResult:
    provider: str
    tx_ref: str
    client_secret: str | None = None
    checkout_url: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class VerifyResult:
    provider: str
    provider_transaction_id: str
    succeeded: bool
    status: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RefundRequest:
    provider_transaction_id: str
    amount: Decimal | None = None
    reason: str = "Project refund"
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RefundResult:
    provider: str
    refund_id: str
    amount: Decimal | None
    original_tx_ref: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TransferRequest:
    recipient: dict[str, Any]
    amount: Decimal
    currency: str = "USD"
    description: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TransferResult:
    provider: str
    transfer_id: str
    reference: str
    amount: Decimal
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class WebhookEvent:
    """
    Result of `verify_webhook()`. Handlers in `apps/webhooks/` (Phase 6)
    route on `event_type` and own any DB mutations.
    """
    provider: str
    event_id: str
    event_type: str
    data: dict[str, Any]
    raw: dict[str, Any] = field(default_factory=dict)


class PaymentGateway(Protocol):
    """
    Provider-agnostic contract. Every adapter implements this.

    Failure semantics: raise `ProviderError` on upstream failures.
    Do not return error dicts.
    """
    provider_name: str

    def charge(self, request: ChargeRequest) -> ChargeResult: ...
    def verify(self, provider_transaction_id: str) -> VerifyResult: ...
    def refund(self, request: RefundRequest) -> RefundResult: ...
    def transfer(self, request: TransferRequest) -> TransferResult: ...
    def verify_webhook(self, payload: bytes, signature: str) -> WebhookEvent: ...
