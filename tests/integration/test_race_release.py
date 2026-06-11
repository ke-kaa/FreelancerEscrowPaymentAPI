"""
Integration — concurrent release_funds on the same escrow.

Two threads call release_funds simultaneously. `@atomic_with_lock` +
`select_for_update()` must serialize them so balance never goes negative
and only one release_payment row in `pending` state survives.

Runs against the test Postgres DB; SQLite has no-op `select_for_update`
so this test only proves what it claims under the configured backend.
"""

from __future__ import annotations

import threading
from decimal import Decimal

import pytest
from django.db import connections
from django.test import TransactionTestCase

from apps.accounts.models import CustomUser
from apps.escrow.models import EscrowTransaction
from apps.escrow.services import EscrowService
from apps.payments.models import Payment
from apps.projects.models import UserProject


@pytest.mark.django_db(transaction=True)
class ConcurrentReleaseTests(TransactionTestCase):
    def _setup_funded_escrow(self) -> EscrowTransaction:
        client = CustomUser.objects.create_user(
            email="race-client@example.com",
            password="pw",
            first_name="C",
            last_name="L",
            user_type="client",
            country="US",
        )
        freelancer = CustomUser.objects.create_user(
            email="race-freelancer@example.com",
            password="pw",
            first_name="F",
            last_name="L",
            user_type="freelancer",
            country="US",
        )
        project = UserProject.objects.create(
            client=client,
            freelancer=freelancer,
            title="Race test",
            description="...",
            amount=Decimal("100.00"),
            status="approved",
        )
        escrow = EscrowTransaction.objects.create(
            project=project,
            funded_amount=Decimal("100.00"),
            current_balance=Decimal("100.00"),
            commission_amount=Decimal("10.00"),
            status="funded",
        )
        Payment.objects.create(
            escrow=escrow,
            user=client,
            amount=Decimal("100.00"),
            provider_transaction_id="seed-funding-tx",
            transaction_type="funding",
            provider="stripe",
            status="completed",
        )
        return escrow

    def test_concurrent_full_releases_serialize(self):
        escrow = self._setup_funded_escrow()

        # Patch out the provider call: instead of hitting Stripe, return a
        # synthetic TransferResult so we exercise only the locking path.
        from apps.escrow import services as svc_mod
        from common.patterns.ports import TransferResult

        def fake_transfer(self, **kwargs):
            return TransferResult(
                provider="stripe",
                transfer_id="tx-fake",
                reference="tx-fake-ref",
                amount=kwargs["amount"],
            )

        original = svc_mod.PaymentService.transfer_to_freelancer
        svc_mod.PaymentService.transfer_to_freelancer = fake_transfer
        try:
            results: list[dict] = []
            barrier = threading.Barrier(2)

            def run():
                barrier.wait()
                svc = EscrowService()
                results.append(svc.release_funds(escrow_id=escrow.id))
                connections.close_all()

            t1 = threading.Thread(target=run)
            t2 = threading.Thread(target=run)
            t1.start(); t2.start()
            t1.join(); t2.join()
        finally:
            svc_mod.PaymentService.transfer_to_freelancer = original

        # Exactly one should have moved escrow into release_pending; the
        # other must have been rejected for already-pending release.
        statuses = [r.get("status") for r in results]
        assert statuses.count("pending") == 1, results
        assert statuses.count("error") == 1, results

        escrow.refresh_from_db()
        # Balance debited at most once (90.00 = 100 - 100 net? No — release pays
        # freelancer_amount=90, commission=10, total debit=100). Balance == 0.
        assert escrow.current_balance == Decimal("0.00")
        assert escrow.status == "release_pending"

        assert Payment.objects.filter(escrow=escrow, transaction_type="release").count() == 1
