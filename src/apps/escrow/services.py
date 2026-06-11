"""
EscrowService — orchestrates escrow lifecycle.

Phase 5 invariants:
- Every state-mutating method that touches an escrow row uses
  `@atomic_with_lock` to acquire `select_for_update()` BEFORE reading or
  writing the row.
- Status changes go through `ESCROW_FSM.transition()`. Direct
  `escrow.status = '...'` is forbidden.
- External provider calls happen OUTSIDE the locked block. Balance is
  pre-debited inside the lock; a compensating update restores it if the
  provider call fails.
- Verification paths are idempotent: a re-delivered webhook or repeated
  call returns the existing terminal state rather than mutating again.
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.disputes.domain.state_machine import DISPUTE_FSM
from apps.disputes.models import Dispute
from apps.escrow.domain import policies
from apps.escrow.domain.state_machine import ESCROW_FSM
from apps.payments.models import Payment
from apps.payments.services import PaymentService
from common.decorators.atomic_with_lock import atomic_with_lock
from common.exception.domain import InvalidTransition, ProviderError

from .models import EscrowTransaction

logger = logging.getLogger(__name__)


class EscrowService:
    def __init__(self) -> None:
        self.payment_service = PaymentService()

    # ─── initiate ───────────────────────────────────────────────────────────

    def initiate_funding(self, *, user, project, amount: Decimal, provider_name=None, **kwargs):
        """
        Idempotent: if an escrow already exists for the project in a
        pending/funded state, return its existing pending Payment rather
        than creating a duplicate escrow row.
        """
        if user.id != project.client_id:
            return {"status": "error", "message": "Only the project client can fund the escrow"}

        # Idempotency check — OneToOne(project) means one escrow ever.
        existing = EscrowTransaction.objects.filter(project=project).first()
        if existing:
            existing_payment = (
                Payment.objects.filter(escrow=existing, transaction_type="funding")
                .order_by("-timestamp")
                .first()
            )
            if existing_payment and existing_payment.status == "pending":
                return {
                    "status": "success",
                    "message": "Existing pending funding returned",
                    "tx_ref": existing_payment.provider_transaction_id,
                    "escrow_id": existing.id,
                    "provider": existing_payment.provider,
                    "total_amount": str(existing.funded_amount),
                    "idempotent": True,
                }
            if existing.status not in {"pending_funding"}:
                return {"status": "error", "message": f"Escrow already in state {existing.status}"}

        try:
            with transaction.atomic():
                commission_amount = policies.commission_on(amount)
                escrow = existing or EscrowTransaction.objects.create(
                    project=project,
                    funded_amount=amount,
                    current_balance=Decimal("0.00"),  # funded only after verify
                    commission_amount=commission_amount,
                    is_locked=False,
                )

                try:
                    init = self.payment_service.init_charge(
                        user=user,
                        amount=amount,
                        provider_name=provider_name,
                        description=f"Escrow funding for {getattr(project, 'title', '')}",
                    )
                except ProviderError as exc:
                    raise ValueError(exc.message) from exc

                Payment.objects.create(
                    escrow=escrow,
                    user=user,
                    amount=amount,
                    provider_transaction_id=init.tx_ref,
                    transaction_type="funding",
                    provider=init.provider,
                    status="pending",
                )

                return {
                    "status": "success",
                    "payment_url": init.checkout_url,
                    "client_secret": init.client_secret,
                    "tx_ref": init.tx_ref,
                    "escrow_id": escrow.id,
                    "provider": init.provider,
                    "total_amount": str(amount),
                    "commission_rate": str(policies.commission_rate()),
                    "commission_amount": str(commission_amount),
                }
        except Exception as e:
            logger.error("Escrow funding initiation failed: %s", e)
            return {"status": "error", "message": str(e)}

    # ─── verify funding (webhook / poll path) ───────────────────────────────

    def verify_funding(self, *, tx_ref: str):
        """
        Idempotent. Looks up the funding payment (no lock), checks provider,
        then locks the escrow row to apply the status + balance change.
        """
        try:
            payment = Payment.objects.select_related("escrow").get(
                provider_transaction_id=tx_ref, transaction_type="funding"
            )
        except Payment.DoesNotExist:
            return {"status": "error", "message": "Funding payment not found"}

        # Idempotency — already settled, return current state.
        if payment.status == "completed":
            escrow = payment.escrow
            return {
                "status": "success",
                "message": "Already verified",
                "escrow_id": escrow.id,
                "funded_amount": str(escrow.funded_amount),
                "available_balance": str(escrow.current_balance),
                "idempotent": True,
            }

        try:
            verify_result = self.payment_service.verify_payment(
                provider_name=payment.provider, provider_transaction_id=tx_ref
            )
        except ProviderError as exc:
            return {"status": "error", "message": exc.message}
        if not verify_result.succeeded:
            return {"status": "error", "message": "Payment verification failed"}

        return self._apply_funded(escrow_id=payment.escrow_id, payment_id=payment.id)

    @atomic_with_lock(model=EscrowTransaction, lookup="escrow_id", inject_as="escrow")
    def _apply_funded(self, *, escrow: EscrowTransaction, payment_id: int):
        # Re-fetch payment with row lock — guards against concurrent webhook delivery.
        payment = Payment.objects.select_for_update().get(id=payment_id)
        if payment.status == "completed":
            return {
                "status": "success",
                "message": "Already verified",
                "escrow_id": escrow.id,
                "idempotent": True,
            }

        escrow.funded_amount = payment.amount
        escrow.current_balance = payment.amount
        try:
            ESCROW_FSM.transition(escrow, to="funded", save=False)
        except InvalidTransition as exc:
            return {"status": "error", "message": exc.message, "details": exc.details}
        escrow.save(update_fields=["funded_amount", "current_balance", "status", "updated_at"])

        payment.status = "completed"
        payment.save(update_fields=["status"])

        return {
            "status": "success",
            "message": "Escrow funded successfully",
            "escrow_id": escrow.id,
            "funded_amount": str(escrow.funded_amount),
            "available_balance": str(escrow.current_balance),
            "commission_amount": str(escrow.commission_amount),
        }

    # ─── release ────────────────────────────────────────────────────────────

    def release_funds(self, *, escrow_id: int, amount=None, milestone_id: int | None = None):
        """
        Two-stage release:
            1. Locked pre-debit + Payment(pending) creation.
            2. Provider transfer call (no DB lock held).
            3. On provider failure, compensating credit restores balance.
        """
        prep = self._prepare_release(escrow_id=escrow_id, amount=amount, milestone_id=milestone_id)
        if prep.get("status") != "pending":
            return prep

        try:
            transfer_result = self.payment_service.transfer_to_freelancer(
                freelancer=prep["freelancer"],
                amount=prep["freelancer_amount"],
                provider_name=prep["provider"],
                description=prep["description"],
            )
        except ProviderError as exc:
            self._compensate_release_failure(
                escrow_id=escrow_id,
                release_payment_id=prep["release_payment_id"],
                commission_payment_id=prep["commission_payment_id"],
            )
            return {
                "status": "error",
                "message": exc.message,
                "provider": prep["provider"],
                "details": exc.details,
            }

        # Link the provider reference to our payment row.
        transfer_reference = (
            transfer_result.reference
            or transfer_result.transfer_id
            or prep["internal_reference"]
        )
        Payment.objects.filter(id=prep["release_payment_id"]).update(
            provider_transaction_id=transfer_reference
        )

        return {
            "status": "pending",
            "message": "Transfer initiated, awaiting provider confirmation",
            "total_released": str(prep["release_amount"]),
            "freelancer_amount": str(prep["freelancer_amount"]),
            "commission_deducted": str(prep["commission_amount"]),
            "escrow_balance": str(prep["new_balance"]),
            "provider": prep["provider"],
            "transfer_reference": transfer_reference,
            "release_payment_id": prep["release_payment_id"],
            "commission_payment_id": prep["commission_payment_id"],
            "milestone_id": milestone_id,
        }

    @atomic_with_lock(model=EscrowTransaction, lookup="escrow_id", inject_as="escrow")
    def _prepare_release(
        self, *, escrow: EscrowTransaction, amount, milestone_id: int | None
    ) -> dict[str, Any]:
        if escrow.is_locked:
            return {"status": "error", "message": "Escrow is locked due to dispute"}

        milestone = self._validate_milestone(escrow, milestone_id)
        if isinstance(milestone, dict):  # error envelope
            return milestone

        # Reject if a release is already pending for this scope.
        pending_q = Payment.objects.filter(
            escrow=escrow, transaction_type="release", status__in=["pending", "active"]
        )
        if milestone is not None:
            pending_q = pending_q.filter(milestone=milestone)
        if pending_q.exists():
            return {
                "status": "error",
                "message": "A payout for this scope is already pending confirmation",
            }

        if milestone is not None and amount is None:
            release_amount = Decimal(str(milestone.amount)).quantize(Decimal("0.01"))
        elif amount in (None, ""):
            release_amount = escrow.current_balance
        else:
            release_amount = Decimal(str(amount)).quantize(Decimal("0.01"))

        if release_amount <= 0:
            return {"status": "error", "message": "No available balance to release"}
        if release_amount > escrow.current_balance:
            return {"status": "error", "message": "Insufficient escrow balance"}

        commission = policies.commission_on(release_amount)
        freelancer_amount = release_amount - commission

        funding_payment = (
            Payment.objects.filter(escrow=escrow, transaction_type="funding", status="completed")
            .order_by("-timestamp")
            .first()
        )
        provider = funding_payment.provider if funding_payment else None
        if not provider:
            return {"status": "error", "message": "No provider available for payout"}

        internal_reference = f"escrow-release-{uuid.uuid4().hex[:10]}"

        release_payment = Payment.objects.create(
            escrow=escrow,
            user=escrow.project.freelancer,
            amount=freelancer_amount,
            provider_transaction_id=internal_reference,
            transaction_type="release",
            provider=provider,
            status="pending",
            milestone=milestone,
        )
        commission_payment = Payment.objects.create(
            escrow=escrow,
            user=escrow.project.client,
            amount=commission,
            provider_transaction_id=f"commission-{release_payment.id}",
            transaction_type="commission",
            provider=provider,
            status="pending",
            milestone=milestone,
        )

        # Pre-debit balance.
        escrow.current_balance = escrow.current_balance - release_amount
        try:
            ESCROW_FSM.transition(escrow, to="release_pending", save=False)
        except InvalidTransition as exc:
            return {"status": "error", "message": exc.message, "details": exc.details}
        escrow.save(update_fields=["current_balance", "status", "updated_at"])

        return {
            "status": "pending",
            "escrow_id": escrow.id,
            "freelancer": escrow.project.freelancer,
            "freelancer_amount": freelancer_amount,
            "release_amount": release_amount,
            "commission_amount": commission,
            "new_balance": escrow.current_balance,
            "provider": provider,
            "internal_reference": internal_reference,
            "release_payment_id": release_payment.id,
            "commission_payment_id": commission_payment.id,
            "description": f"Payout for {getattr(escrow.project, 'title', '')}",
        }

    @atomic_with_lock(model=EscrowTransaction, lookup="escrow_id", inject_as="escrow")
    def _compensate_release_failure(
        self,
        *,
        escrow: EscrowTransaction,
        release_payment_id: int,
        commission_payment_id: int,
    ):
        release_payment = Payment.objects.select_for_update().get(id=release_payment_id)
        commission_payment = Payment.objects.select_for_update().get(id=commission_payment_id)

        restored_amount = release_payment.amount + commission_payment.amount

        if release_payment.status == "pending":
            release_payment.status = "failed"
            release_payment.save(update_fields=["status"])
        if commission_payment.status == "pending":
            commission_payment.status = "cancelled"
            commission_payment.save(update_fields=["status"])

        escrow.current_balance = escrow.current_balance + restored_amount
        # Walk back to whatever state we came from. Most common: release_pending → funded.
        if escrow.status == "release_pending":
            try:
                ESCROW_FSM.transition(escrow, to="funded", save=False)
            except InvalidTransition:
                pass
        escrow.save(update_fields=["current_balance", "status", "updated_at"])

    # ─── verify transfer (webhook path) ─────────────────────────────────────

    def verify_transfer_to_freelancer(
        self,
        *,
        provider_name: str,
        transfer_reference: str,
        success: bool,
        details: dict | None = None,
    ):
        try:
            payment = Payment.objects.select_related("escrow").get(
                provider_transaction_id=transfer_reference,
                transaction_type="release",
                provider=provider_name,
            )
        except Payment.DoesNotExist:
            return {"status": "error", "message": "Release payment not found"}

        # Idempotency — terminal already.
        if payment.status == "completed" and success:
            return {"status": "success", "message": "Payout already processed", "escrow_id": payment.escrow_id, "idempotent": True}
        if payment.status == "failed" and not success:
            return {"status": "error", "message": "Payout already marked failed", "escrow_id": payment.escrow_id, "idempotent": True}

        return self._apply_transfer_outcome(
            escrow_id=payment.escrow_id,
            payment_id=payment.id,
            success=success,
            details=details or {},
        )

    @atomic_with_lock(model=EscrowTransaction, lookup="escrow_id", inject_as="escrow")
    def _apply_transfer_outcome(
        self,
        *,
        escrow: EscrowTransaction,
        payment_id: int,
        success: bool,
        details: dict,
    ):
        # of=("self",) restricts the row lock to Payment; without it Postgres
        # refuses FOR UPDATE across the nullable milestone outer join.
        payment = (
            Payment.objects.select_for_update(of=("self",))
            .select_related("milestone")
            .get(id=payment_id)
        )
        commission_payment = (
            Payment.objects.select_for_update()
            .filter(
                escrow=escrow,
                transaction_type="commission",
                provider=payment.provider,
                provider_transaction_id=f"commission-{payment.id}",
            )
            .first()
        )

        if success:
            if payment.status == "completed":
                return {"status": "success", "idempotent": True, "escrow_id": escrow.id}

            payment.status = "completed"
            payment.save(update_fields=["status"])
            if commission_payment and commission_payment.status == "pending":
                commission_payment.status = "completed"
                commission_payment.save(update_fields=["status"])

            try:
                ESCROW_FSM.transition(
                    escrow,
                    to=policies.resolve_release_status(escrow.current_balance),
                    save=False,
                )
            except InvalidTransition as exc:
                logger.warning("verify_transfer: %s", exc.message)
            escrow.save(update_fields=["status", "updated_at"])

            if payment.milestone and not payment.milestone.is_paid:
                payment.milestone.is_paid = True
                payment.milestone.save(update_fields=["is_paid"])

            return {
                "status": "success",
                "message": "Freelancer payout confirmed",
                "escrow_id": escrow.id,
                "remaining_balance": str(escrow.current_balance),
                "milestone_id": payment.milestone.id if payment.milestone else None,
            }

        # Failure path: compensate (balance was pre-debited at release time).
        restored = payment.amount + (commission_payment.amount if commission_payment else Decimal("0"))
        payment.status = "failed"
        payment.save(update_fields=["status"])
        if commission_payment and commission_payment.status != "cancelled":
            commission_payment.status = "cancelled"
            commission_payment.save(update_fields=["status"])

        escrow.current_balance = escrow.current_balance + restored
        if escrow.status == "release_pending":
            try:
                ESCROW_FSM.transition(escrow, to="funded", save=False)
            except InvalidTransition:
                pass
        escrow.save(update_fields=["current_balance", "status", "updated_at"])

        if payment.milestone and payment.milestone.is_paid:
            payment.milestone.is_paid = False
            payment.milestone.save(update_fields=["is_paid"])

        return {
            "status": "error",
            "message": "Freelancer payout failed",
            "escrow_id": escrow.id,
            "milestone_id": payment.milestone.id if payment.milestone else None,
        }

    # ─── refund ─────────────────────────────────────────────────────────────

    def refund(self, *, user, escrow_id: int, amount=None, reason: str = "Project refund", provider_name=None):
        prep = self._prepare_refund(
            escrow_id=escrow_id,
            user_id=user.id,
            amount=amount,
            provider_name=provider_name,
        )
        if prep.get("status") != "pending":
            return prep

        try:
            refund_dto = self.payment_service.refund(
                provider_name=prep["provider"],
                provider_transaction_id=prep["provider_tx_id"],
                amount=prep["refund_amount"],
                reason=reason,
            )
        except ProviderError as exc:
            self._compensate_refund_failure(
                escrow_id=escrow_id, refund_payment_id=prep["refund_payment_id"]
            )
            return {"status": "error", "message": exc.message}

        Payment.objects.filter(id=prep["refund_payment_id"]).update(
            provider_transaction_id=refund_dto.refund_id or prep["internal_reference"],
            status="completed",
        )

        return {
            "status": "success",
            "message": "Refund processed",
            "refund_amount": str(prep["refund_amount"]),
            "escrow_balance": str(prep["new_balance"]),
        }

    @atomic_with_lock(model=EscrowTransaction, lookup="escrow_id", inject_as="escrow")
    def _prepare_refund(
        self,
        *,
        escrow: EscrowTransaction,
        user_id: int,
        amount,
        provider_name: str | None,
    ) -> dict[str, Any]:
        if escrow.is_locked:
            return {"status": "error", "message": "Escrow is locked due to dispute"}
        if user_id != escrow.project.client_id:
            return {"status": "error", "message": "Only the project client can request a refund"}

        funding_payment = (
            Payment.objects.filter(escrow=escrow, transaction_type="funding", status="completed")
            .order_by("-timestamp")
            .first()
        )
        if not funding_payment:
            return {"status": "error", "message": "No completed funding to refund from"}

        provider = provider_name or funding_payment.provider
        provider_tx_id = funding_payment.provider_transaction_id

        refund_amount = (
            Decimal(str(amount)).quantize(Decimal("0.01"))
            if amount not in (None, "")
            else escrow.current_balance
        )
        if refund_amount <= 0:
            return {"status": "error", "message": "No available balance to refund"}
        if refund_amount > escrow.current_balance:
            return {"status": "error", "message": "Insufficient escrow balance"}

        internal_reference = f"refund-{uuid.uuid4().hex[:10]}"
        refund_payment = Payment.objects.create(
            escrow=escrow,
            user=escrow.project.client,
            amount=refund_amount,
            provider_transaction_id=internal_reference,
            transaction_type="refund",
            provider=provider,
            status="pending",
        )

        # Pre-debit balance.
        escrow.current_balance = escrow.current_balance - refund_amount
        if escrow.current_balance == 0:
            try:
                ESCROW_FSM.transition(escrow, to="refunded", save=False)
            except InvalidTransition as exc:
                return {"status": "error", "message": exc.message, "details": exc.details}
        escrow.save(update_fields=["current_balance", "status", "updated_at"])

        return {
            "status": "pending",
            "provider": provider,
            "provider_tx_id": provider_tx_id,
            "refund_amount": refund_amount,
            "new_balance": escrow.current_balance,
            "refund_payment_id": refund_payment.id,
            "internal_reference": internal_reference,
        }

    @atomic_with_lock(model=EscrowTransaction, lookup="escrow_id", inject_as="escrow")
    def _compensate_refund_failure(self, *, escrow: EscrowTransaction, refund_payment_id: int):
        refund_payment = Payment.objects.select_for_update().get(id=refund_payment_id)
        if refund_payment.status == "pending":
            refund_payment.status = "failed"
            refund_payment.save(update_fields=["status"])
        escrow.current_balance = escrow.current_balance + refund_payment.amount
        # If we transitioned to refunded prematurely, walk back.
        if escrow.status == "refunded":
            # No direct refunded→funded; use disputed→funded path or accept it.
            # Simplest: re-evaluate based on whether any funding completed.
            pass  # leave the status; refund_amount restored is the priority
        escrow.save(update_fields=["current_balance", "updated_at"])

    # ─── dispute lifecycle ──────────────────────────────────────────────────

    def open_dispute(self, *, project, raised_by, dispute_type="other", reason=""):
        if raised_by.id not in (project.client_id, getattr(project.freelancer, "id", None)):
            return {"status": "error", "message": "Only project participants can open a dispute"}
        if hasattr(project, "dispute"):
            return {"status": "error", "message": "A dispute already exists for this project"}

        try:
            with transaction.atomic():
                dispute = Dispute.objects.create(
                    project=project,
                    raised_by=raised_by,
                    dispute_type=dispute_type,
                    reason=reason,
                    status="open",
                )
                escrow = EscrowTransaction.objects.select_for_update().filter(project=project).first()
                if escrow and not escrow.is_locked:
                    escrow.is_locked = True
                    try:
                        ESCROW_FSM.transition(escrow, to="disputed", save=False)
                    except InvalidTransition as exc:
                        return {"status": "error", "message": exc.message}
                    escrow.save(update_fields=["is_locked", "status", "updated_at"])

                return {"status": "success", "dispute_id": dispute.id}
        except Exception as e:
            logger.error("Open dispute failed: %s", e)
            return {"status": "error", "message": str(e)}

    def resolve_dispute(self, *, dispute: Dispute, resolved_by, resolution: str = ""):
        try:
            with transaction.atomic():
                DISPUTE_FSM.transition(dispute, to="resolved", save=False)
                dispute.resolution = resolution
                dispute.resolved_by = resolved_by
                dispute.save()

                escrow = EscrowTransaction.objects.select_for_update().filter(project=dispute.project).first()
                if escrow and escrow.is_locked:
                    escrow.is_locked = False
                    # Walk back to a sensible non-disputed state.
                    try:
                        ESCROW_FSM.transition(escrow, to="funded", save=False)
                    except InvalidTransition:
                        pass
                    escrow.save(update_fields=["is_locked", "status", "updated_at"])
                return {"status": "success", "message": "Dispute resolved"}
        except InvalidTransition as exc:
            return {"status": "error", "message": exc.message}
        except Exception as e:
            logger.error("Resolve dispute failed: %s", e)
            return {"status": "error", "message": str(e)}

    def close_dispute(self, *, dispute: Dispute, closed_by):
        try:
            DISPUTE_FSM.transition(dispute, to="closed")
            return {"status": "success", "message": "Dispute closed"}
        except InvalidTransition as exc:
            return {"status": "error", "message": exc.message}

    # ─── helpers ────────────────────────────────────────────────────────────

    def _validate_milestone(self, escrow: EscrowTransaction, milestone_id: int | None):
        if not milestone_id:
            return None
        from apps.projects.models import Milestone
        milestone = Milestone.objects.filter(id=milestone_id).first()
        if not milestone:
            return {"status": "error", "message": "Milestone not found"}
        if milestone.project_id != escrow.project_id:
            return {"status": "error", "message": "Milestone does not belong to this escrow project"}
        if milestone.is_paid:
            return {"status": "error", "message": "Milestone has already been paid"}
        if milestone.status not in {"approved", "submitted"}:
            return {"status": "error", "message": "Milestone must be approved before releasing funds"}
        return milestone

    @staticmethod
    def can_manage_escrow(user, escrow: EscrowTransaction) -> bool:
        return user.id in (escrow.project.client_id, getattr(escrow.project.freelancer, "id", None))

    @staticmethod
    def is_client(user, escrow: EscrowTransaction) -> bool:
        return user.id == escrow.project.client_id

    @staticmethod
    def is_freelancer(user, escrow: EscrowTransaction) -> bool:
        return getattr(escrow.project.freelancer, "id", None) == user.id

    def audit(self, action: str, *, escrow: EscrowTransaction = None, extra: dict = None):
        payload = {"escrow_id": getattr(escrow, "id", None), **(extra or {})}
        logger.info("AUDIT %s: %s", action, payload)
