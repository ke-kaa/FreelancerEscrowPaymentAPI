"""
E2E — full escrow lifecycle from funded to released, with payment provider
mocked at the PaymentGateway boundary.

Skips client/freelancer/project setup ceremony (factories handle that) and
exercises only the escrow state machine + lock discipline end-to-end.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.escrow.models import EscrowTransaction
from apps.escrow.services import EscrowService
from apps.payments.models import Payment
from common.patterns.ports import (
    RefundResult,
    TransferResult,
    VerifyResult,
)
from tests.factories import (
    EscrowTransactionFactory,
    PaymentFactory,
    StripePayoutMethodFactory,
)

pytestmark = pytest.mark.django_db


def _seeded_escrow():
    """Funded escrow + completed funding Payment + freelancer payout method."""
    escrow = EscrowTransactionFactory(
        funded_amount=Decimal("1000.00"),
        current_balance=Decimal("1000.00"),
        commission_amount=Decimal("100.00"),
        status="funded",
    )
    PaymentFactory(
        escrow=escrow,
        amount=Decimal("1000.00"),
        provider_transaction_id="seed-funding-tx",
        transaction_type="funding",
        provider="stripe",
        status="completed",
    )
    StripePayoutMethodFactory(payout_method__user=escrow.project.freelancer)
    return escrow


class TestFullReleaseFlow:
    def test_release_then_confirm_via_webhook(self):
        escrow = _seeded_escrow()
        fake_transfer = TransferResult(
            provider="stripe",
            transfer_id="tr_test_1",
            reference="ref-test-1",
            amount=Decimal("450.00"),
        )

        with patch(
            "apps.payments.services.PaymentService.transfer_to_freelancer",
            return_value=fake_transfer,
        ):
            release = EscrowService().release_funds(
                escrow_id=escrow.id, amount=Decimal("500.00")
            )

        assert release["status"] == "pending"
        assert release["freelancer_amount"] == "450.00"
        assert release["commission_deducted"] == "50.00"
        assert release["escrow_balance"] == "500.00"

        escrow.refresh_from_db()
        assert escrow.status == "release_pending"
        assert escrow.current_balance == Decimal("500.00")

        # Webhook confirms the transfer.
        verify = EscrowService().verify_transfer_to_freelancer(
            provider_name="stripe",
            transfer_reference=fake_transfer.reference,
            success=True,
            details={"raw": "stripe payload"},
        )
        assert verify["status"] == "success"

        escrow.refresh_from_db()
        # Still positive balance → partial release.
        assert escrow.status == "partially_released"
        assert escrow.current_balance == Decimal("500.00")

        # Final release zeroes the balance.
        with patch(
            "apps.payments.services.PaymentService.transfer_to_freelancer",
            return_value=TransferResult(
                provider="stripe",
                transfer_id="tr_test_2",
                reference="ref-test-2",
                amount=Decimal("450.00"),
            ),
        ):
            EscrowService().release_funds(escrow_id=escrow.id)

        EscrowService().verify_transfer_to_freelancer(
            provider_name="stripe",
            transfer_reference="ref-test-2",
            success=True,
            details={},
        )

        escrow.refresh_from_db()
        assert escrow.status == "released"
        assert escrow.current_balance == Decimal("0.00")

    def test_provider_failure_restores_balance(self):
        escrow = _seeded_escrow()

        from common.exception.domain import ProviderError

        with patch(
            "apps.payments.services.PaymentService.transfer_to_freelancer",
            side_effect=ProviderError("Stripe transfer rejected"),
        ):
            result = EscrowService().release_funds(
                escrow_id=escrow.id, amount=Decimal("500.00")
            )

        assert result["status"] == "error"
        escrow.refresh_from_db()
        # Balance restored, status walked back from release_pending → funded.
        assert escrow.status == "funded"
        assert escrow.current_balance == Decimal("1000.00")
        # Release payment marked failed.
        release_payment = Payment.objects.filter(
            escrow=escrow, transaction_type="release"
        ).first()
        assert release_payment.status == "failed"


class TestRefundFlow:
    def test_full_refund_settles_balance(self):
        escrow = _seeded_escrow()
        fake_refund = RefundResult(
            provider="stripe",
            refund_id="re_test_1",
            amount=Decimal("1000.00"),
            original_tx_ref="seed-funding-tx",
        )
        with patch(
            "apps.payments.services.PaymentService.refund",
            return_value=fake_refund,
        ):
            result = EscrowService().refund(
                user=escrow.project.client,
                escrow_id=escrow.id,
                reason="Project cancelled",
            )

        assert result["status"] == "success"
        assert result["refund_amount"] == "1000.00"
        escrow.refresh_from_db()
        assert escrow.status == "refunded"
        assert escrow.current_balance == Decimal("0.00")


class TestVerifyFundingIdempotency:
    def test_double_call_returns_idempotent(self):
        escrow = EscrowTransactionFactory(
            funded_amount=Decimal("500.00"),
            current_balance=Decimal("0.00"),
            status="pending_funding",
        )
        PaymentFactory(
            escrow=escrow,
            amount=Decimal("500.00"),
            provider_transaction_id="idem-tx-1",
            transaction_type="funding",
            provider="stripe",
            status="pending",
        )

        fake_verify = VerifyResult(
            provider="stripe",
            provider_transaction_id="idem-tx-1",
            succeeded=True,
            status="success",
        )
        with patch(
            "apps.payments.services.PaymentService.verify_payment",
            return_value=fake_verify,
        ):
            first = EscrowService().verify_funding(tx_ref="idem-tx-1")
            second = EscrowService().verify_funding(tx_ref="idem-tx-1")

        assert first["status"] == "success"
        assert second.get("idempotent") is True
        # Only one funded transition happened.
        assert EscrowTransaction.objects.get(id=escrow.id).funded_amount == Decimal("500.00")
