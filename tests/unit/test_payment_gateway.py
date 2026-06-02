"""
Unit — PaymentGateway Protocol is satisfied by a fake without touching
real SDKs. Proves services can be tested via DI.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

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
    WebhookEvent,
)


class FakeGateway:
    """Implements PaymentGateway purely in-memory."""

    provider_name = "fake"

    def __init__(self) -> None:
        self.charges: list[ChargeRequest] = []
        self.refunds: list[RefundRequest] = []
        self.transfers: list[TransferRequest] = []
        self.fail_next = False

    def charge(self, request: ChargeRequest) -> ChargeResult:
        if self.fail_next:
            raise ProviderError("simulated charge failure")
        self.charges.append(request)
        return ChargeResult(
            provider=self.provider_name,
            tx_ref=f"fake-{len(self.charges)}",
            client_secret="cs_fake",
            checkout_url="https://example.test/checkout",
        )

    def verify(self, provider_transaction_id: str) -> VerifyResult:
        return VerifyResult(
            provider=self.provider_name,
            provider_transaction_id=provider_transaction_id,
            succeeded=True,
            status="success",
        )

    def refund(self, request: RefundRequest) -> RefundResult:
        self.refunds.append(request)
        return RefundResult(
            provider=self.provider_name,
            refund_id=f"refund-{len(self.refunds)}",
            amount=request.amount,
            original_tx_ref=request.provider_transaction_id,
        )

    def transfer(self, request: TransferRequest) -> TransferResult:
        self.transfers.append(request)
        return TransferResult(
            provider=self.provider_name,
            transfer_id=f"tr-{len(self.transfers)}",
            reference=f"ref-{len(self.transfers)}",
            amount=request.amount,
        )

    def verify_webhook(self, payload: bytes, signature: str) -> WebhookEvent:
        return WebhookEvent(provider=self.provider_name, event_id="evt-1", event_type="test", data={})


def test_fake_satisfies_protocol():
    gw: PaymentGateway = FakeGateway()
    assert gw.provider_name == "fake"


def test_fake_charge_round_trip():
    gw = FakeGateway()
    result = gw.charge(
        ChargeRequest(user_id="1", user_email="u@e.com", amount=Decimal("10.00"))
    )
    assert result.tx_ref == "fake-1"
    assert gw.charges[0].amount == Decimal("10.00")


def test_fake_can_simulate_failure():
    gw = FakeGateway()
    gw.fail_next = True
    with pytest.raises(ProviderError):
        gw.charge(ChargeRequest(user_id="1", user_email="u@e.com", amount=Decimal("1.00")))
