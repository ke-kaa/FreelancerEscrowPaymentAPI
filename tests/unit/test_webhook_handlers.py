"""Unit — provider webhook handlers route events to escrow service correctly."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.webhooks.handlers.chapa import handle_chapa_event
from apps.webhooks.handlers.stripe import handle_stripe_event

pytestmark = pytest.mark.django_db


class TestStripeHandler:
    def test_payment_intent_succeeded_routes_to_verify_funding(self):
        with patch("apps.webhooks.handlers.stripe.EscrowService") as svc:
            svc.return_value.verify_funding.return_value = {"status": "success"}
            result = handle_stripe_event("payment_intent.succeeded", {"id": "pi_1"})
        svc.return_value.verify_funding.assert_called_once_with(tx_ref="pi_1")
        assert result["status"] == "success"

    def test_payment_intent_failed_marks_payment_failed(self):
        with patch("apps.webhooks.handlers.stripe.Payment") as PaymentMock:
            payment = PaymentMock.objects.filter.return_value.first.return_value
            payment.status = "pending"
            payment.id = 7
            result = handle_stripe_event("payment_intent.payment_failed", {"id": "pi_2"})
        assert result["status"] == "failed"
        assert payment.status == "failed"

    def test_transfer_paid_routes_success(self):
        with patch("apps.webhooks.handlers.stripe.EscrowService") as svc:
            svc.return_value.verify_transfer_to_freelancer.return_value = {"status": "success"}
            handle_stripe_event("transfer.paid", {"id": "tr_1"})
        kwargs = svc.return_value.verify_transfer_to_freelancer.call_args.kwargs
        assert kwargs["provider_name"] == "stripe"
        assert kwargs["transfer_reference"] == "tr_1"
        assert kwargs["success"] is True

    def test_transfer_failed_routes_failure(self):
        with patch("apps.webhooks.handlers.stripe.EscrowService") as svc:
            svc.return_value.verify_transfer_to_freelancer.return_value = {"status": "error"}
            handle_stripe_event("transfer.failed", {"id": "tr_2"})
        assert svc.return_value.verify_transfer_to_freelancer.call_args.kwargs["success"] is False

    def test_payout_paid_also_routes_to_transfer_verify(self):
        with patch("apps.webhooks.handlers.stripe.EscrowService") as svc:
            handle_stripe_event("payout.paid", {"id": "po_1"})
        assert svc.return_value.verify_transfer_to_freelancer.call_args.kwargs["success"] is True

    def test_unknown_event_ignored(self):
        result = handle_stripe_event("customer.created", {"id": "cus_1"})
        assert result["status"] == "ignored"


class TestChapaHandler:
    def test_transfer_success_status_routes_to_verify(self):
        with patch("apps.webhooks.handlers.chapa.EscrowService") as svc:
            handle_chapa_event("transfer", {"transfer_reference": "ref-1", "status": "success"})
        kwargs = svc.return_value.verify_transfer_to_freelancer.call_args.kwargs
        assert kwargs["provider_name"] == "chapa"
        assert kwargs["transfer_reference"] == "ref-1"
        assert kwargs["success"] is True

    def test_transfer_failed_status_routes_to_verify_failure(self):
        with patch("apps.webhooks.handlers.chapa.EscrowService") as svc:
            handle_chapa_event("transfer", {"transfer_reference": "ref-2", "status": "failed"})
        assert svc.return_value.verify_transfer_to_freelancer.call_args.kwargs["success"] is False

    def test_transfer_indeterminate_status_ignored(self):
        result = handle_chapa_event("transfer", {"transfer_reference": "r", "status": "weird"})
        assert result["status"] == "ignored"

    def test_funding_success_status_routes_to_verify_funding(self):
        with patch("apps.webhooks.handlers.chapa.EscrowService") as svc:
            svc.return_value.verify_funding.return_value = {"status": "success"}
            handle_chapa_event("charge.completed", {"tx_ref": "tx-1", "status": "success"})
        svc.return_value.verify_funding.assert_called_once_with(tx_ref="tx-1")

    def test_funding_failure_status_marks_payment_failed(self):
        with patch("apps.webhooks.handlers.chapa.Payment") as PaymentMock:
            payment = PaymentMock.objects.filter.return_value.first.return_value
            payment.status = "pending"
            payment.id = 9
            handle_chapa_event("charge.failed", {"tx_ref": "tx-2", "status": "failed"})
        assert payment.status == "failed"

    def test_unhandled_event_ignored(self):
        result = handle_chapa_event("", {})
        assert result["status"] == "ignored"
