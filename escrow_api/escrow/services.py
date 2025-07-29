from django.db import transaction
from .models import EscrowTransaction
from payments.models import Payment
from payments.services import PaymentService
import logging
from django.conf import settings
import uuid

logger = logging.getLogger(__name__)

class EscrowService:
    def __init__(self):
        self.payment_service = PaymentService()
    
    def release_funds(self, escrow, amount = None, provider = None):
        """
        Release funds from escrow to freelancer
        Commission is deducted at the time of release.
        """
        try:
            if escrow.is_locked:
                return {'status': 'error', 'message': 'Escrow is locked due to dispute'}
            
            release_amount = amount or escrow.current_balance

            if release_amount <= 0:
                return {"status": "error", "message": "No available balance to release"}
            if release_amount > escrow.current_balance:
                return {'status': 'error', 'message': 'Insufficient escrow balance'}
            
            commission_on_release = release_amount * settings.PLATFORM_COMMISSION_RATE
            freelancer_amount = release_amount - commission_on_release 
            
            # Determine provider
            funding_payment = (
                Payment.objects.filter(
                    escrow=escrow, transaction_type="funding", status="completed"
                )
                .order_by("-timestamp")
                .first()
            )

            resolved_provider = (funding_payment.provider if funding_payment else None)
            if not resolved_provider:
                return {"status": "error", "message": "No provider available for payout"}

            with transaction.atomic():
                # payout payment record for freelancer
                payout_payment = Payment.objects.create(
                    escrow=escrow,
                    user=escrow.project.freelancer,
                    amount=freelancer_amount,
                    provider_transactionn_id=f'escrow-release-{uuid.uuid4().hex[:10]}',
                    transaction_type='release',
                    provider=resolved_provider,
                    status='pending'
                )

                # commission payment for platform
                commission_payment = Payment.objects.create(
                    escrow=escrow, 
                    user=escrow.project.client,
                    amount=commission_on_release,
                    provider_transaction_id=f"commission-{escrow.id}",
                    transaction_type="commission",
                    provider=resolved_provider,
                    status="completed"
                )
                
                # Update escrow balance
                escrow.current_balance -= release_amount
                if escrow.current_balance == 0:
                    escrow.status = 'released'
                else:
                    escrow.status = 'partially_released'
                escrow.save()
                
                # Process actual fund transfer
                transfer_result = self.payment_service.transfer_to_freelancer(
                    freelancer=escrow.project.freelancer,
                    amount=freelancer_amount,
                    provider_name=resolved_provider,
                )

                # Update payment status based on transfer result
                # migrate to webhook later to mark completed payments and use async for transfering funds
                if transfer_result.get("status") == "success":
                    payout_payment.status = "completed"
                    payout_payment.provider_transactionn_id = transfer_result.get('reference', payout_payment.provider_transactionn_id)
                    payout_payment.save()
                else:
                    payout_payment.status = "failed"
                    payout_payment.save()
                    # Rollback escrow balance if transfer failed
                    escrow.current_balance += release_amount
                    escrow.save()
                    commission_payment.delete()
                
                return {
                    "status": transfer_result.get("status", "error"),
                    "message": transfer_result.get("message", "Transfer failed"),
                    "total_released": str(release_amount),
                    "freelancer_amount": str(freelancer_amount),
                    "commission_deducted": str(commission_on_release),
                    "escrow_balance": str(escrow.current_balance),
                    "provider": resolved_provider,
                    "transfer_result": transfer_result
                }
                
        except Exception as e:
            logger.error(f"Escrow release failed: {str(e)}")
            return {'status': 'error', 'message': str(e)}