from django.db import transaction
from decimal import Decimal
from .models import EscrowTransaction
from payments.models import Payment
from payments.services import PaymentService
from disputes.models import Dispute
import logging
from django.conf import settings
import uuid

logger = logging.getLogger(__name__)

class EscrowService:
    def __init__(self):
        self.payment_service = PaymentService()
    
    def initiate_funding(self, *, user, project, amount, provider_name=None, **kwargs):
        """
        Orchestrate escrow funding initiation.
        - Validates requester (must be project.client)
        - Delegates payment init to PaymentService
        NOTE: PaymentService currently creates the escrow; we keep that for now.
        """
        if user.id != project.client_id:
            return {"status": "error", "message": "Only the project client can fund the escrow"}

        try:
            with transaction.atomic():
                commission_amount = amount * settings.PLATFORM_COMMISSION_RATE

                escrow = EscrowTransaction.objects.create(
                    project=project,
                    funded_amount=amount,
                    current_balance=amount,
                    commission_amount=commission_amount,
                    is_locked=False,
                )

                init = self.payment_service.init_charge(
                    user=user,
                    amount=amount,
                    provider_name=provider_name,
                    project_title=getattr(project, 'title', ''),
                    **kwargs,
                )

                if init.get('status') != 'success':
                    raise ValueError(init.get('message') or 'Payment initialization failed')

                # Resolve provider transaction id across providers
                tx_ref = init.get('tx_ref') or init.get('payment_intent_id') or init.get('id')
                if not tx_ref:
                    raise ValueError('Missing provider transaction reference')

                Payment.objects.create(
                    escrow=escrow,
                    user=user,
                    amount=amount,
                    provider_transactionn_id=tx_ref,
                    transaction_type='funding',
                    provider=provider_name or init.get('provider') or '',
                    status='pending',
                )

                return {
                    'status': 'success',
                    'payment_url': (init.get('data') or {}).get('checkout_url'),
                    'client_secret': (init.get('data') or {}).get('client_secret'),
                    'tx_ref': tx_ref,
                    'escrow_id': escrow.id,
                    'provider': provider_name or init.get('provider'),
                    'total_amount': str(amount),
                    'commission_rate': str(settings.PLATFORM_COMMISSION_RATE),
                    'commission_amount': str(commission_amount),
                }
        except Exception as e:
            logger.error(f"Escrow funding initiation failed: {str(e)}")
            return {"status": "error", "message": str(e)}

    def verify_funding(self, *, tx_ref: str):
        """Verify provider-side payment and mark escrow as funded."""
        try:
            with transaction.atomic():
                payment = Payment.objects.select_related('escrow', 'escrow__project').get(
                    provider_transactionn_id=tx_ref,
                    transaction_type='funding',
                )
                provider_name = payment.provider
                verified = self.payment_service.verify_payment(
                    provider_name=provider_name,
                    provider_transaction_id=tx_ref,
                )
                if not verified:
                    return {"status": "error", "message": "Payment verification failed"}

                escrow = payment.escrow
                escrow.funded_amount = payment.amount
                escrow.current_balance = payment.amount
                escrow.status = 'funded'
                escrow.save()

                payment.status = 'completed'
                payment.save()

                return {
                    'status': 'success',
                    'message': 'Escrow funded successfully',
                    'escrow_id': escrow.id,
                    'funded_amount': str(escrow.funded_amount),
                    'available_balance': str(escrow.current_balance),
                    'commission_amount': str(escrow.commission_amount),
                }
        except Payment.DoesNotExist:
            return {"status": "error", "message": "Funding payment not found"}
        except Exception as e:
            logger.error(f"Escrow verify funding failed: {str(e)}")
            return {"status": "error", "message": str(e)}

    def release_funds(self, escrow, amount=None, provider=None, milestone=None):
        """
        Release funds from escrow to freelancer
        Commission is deducted at the time of release.
        """
        try:
            if escrow.is_locked:
                return {'status': 'error', 'message': 'Escrow is locked due to dispute'}
            
            milestone_instance = milestone
            if milestone_instance:
                if milestone_instance.project_id != escrow.project_id:
                    return {'status': 'error', 'message': 'Milestone does not belong to this escrow project'}
                if milestone_instance.is_paid:
                    return {'status': 'error', 'message': 'Milestone has already been paid'}
                if milestone_instance.status not in {'approved', 'submitted'}:
                    return {'status': 'error', 'message': 'Milestone must be approved before releasing funds'}

                pending_for_milestone = Payment.objects.filter(
                    escrow=escrow,
                    transaction_type='release',
                    status__in=['pending', 'active'],
                    milestone=milestone_instance,
                ).exists()
                if pending_for_milestone:
                    return {'status': 'error', 'message': 'A payout for this milestone is already pending confirmation'}
            else:
                # Prevent duplicate releases while one is pending (global)
                pending_release_exists = Payment.objects.filter(
                    escrow=escrow,
                    transaction_type='release',
                    status__in=['pending', 'active']
                ).exists()
                if pending_release_exists:
                    return {'status': 'error', 'message': 'A payout is already pending confirmation'}

            if milestone_instance and amount is None:
                release_amount = Decimal(str(milestone_instance.amount)).quantize(Decimal('0.01'))
            elif amount is None or amount == '':
                release_amount = escrow.current_balance
            else:
                release_amount = Decimal(str(amount)).quantize(Decimal('0.01'))

            if release_amount <= 0:
                return {"status": "error", "message": "No available balance to release"}
            if release_amount > escrow.current_balance:
                return {'status': 'error', 'message': 'Insufficient escrow balance'}
            
            commission_rate = Decimal(str(settings.PLATFORM_COMMISSION_RATE))
            commission_on_release = (release_amount * commission_rate).quantize(Decimal('0.01'))
            freelancer_amount = (release_amount - commission_on_release).quantize(Decimal('0.01'))
            
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

            transfer_result = self.payment_service.transfer_to_freelancer(
                freelancer=escrow.project.freelancer,
                amount=freelancer_amount,
                provider_name=resolved_provider,
                project_title=getattr(escrow.project, 'title', ''),
            )

            if transfer_result.get("status") != "success":
                return {
                    "status": transfer_result.get("status", "error"),
                    "message": transfer_result.get("message", "Transfer initiation failed"),
                    "provider": resolved_provider,
                    "transfer_result": transfer_result,
                }

            transfer_reference = (
                transfer_result.get('reference')
                or transfer_result.get('transfer_id')
                or transfer_result.get('tx_ref')
                or f'escrow-release-{uuid.uuid4().hex[:10]}'
            )

            with transaction.atomic():
                payout_payment = Payment.objects.create(
                    escrow=escrow,
                    user=escrow.project.freelancer,
                    amount=freelancer_amount,
                    provider_transactionn_id=transfer_reference,
                    transaction_type='release',
                    provider=resolved_provider,
                    status='pending',
                    milestone=milestone_instance,
                )

                commission_payment = Payment.objects.create(
                    escrow=escrow,
                    user=escrow.project.client,
                    amount=commission_on_release,
                    provider_transactionn_id=f'commission-{payout_payment.id}',
                    transaction_type='commission',
                    provider=resolved_provider,
                    status='pending',
                    milestone=milestone_instance,
                )

                escrow.status = 'release_pending'
                escrow.save(update_fields=['status'])

            return {
                "status": "pending",
                "message": "Transfer initiated, awaiting provider confirmation",
                "total_released": str(release_amount),
                "freelancer_amount": str(freelancer_amount),
                "commission_deducted": str(commission_on_release),
                "escrow_balance": str(escrow.current_balance),
                "provider": resolved_provider,
                "transfer_reference": transfer_reference,
                "release_payment_id": payout_payment.id,
                "commission_payment_id": commission_payment.id,
                "milestone_id": milestone_instance.id if milestone_instance else None,
                "transfer_result": transfer_result,
            }
                
        except Exception as e:
            logger.error(f"Escrow release failed: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def verify_transfer_to_freelancer(self, *, provider_name: str, transfer_reference: str, success: bool, details: dict | None = None):
        """
        Finalize freelancer payout after provider confirmation (webhook).
        """
        try:
            logger.info(
                "Verifying freelancer transfer",
                extra={
                    'provider': provider_name,
                    'transfer_reference': transfer_reference,
                    'success': success,
                }
            )
            with transaction.atomic():
                payment = Payment.objects.select_related('escrow', 'escrow__project').get(
                    provider_transactionn_id=transfer_reference,
                    transaction_type='release',
                    provider=provider_name,
                )

                escrow = payment.escrow
                commission_payment = Payment.objects.filter(
                    escrow=escrow,
                    transaction_type='commission',
                    provider=provider_name,
                    provider_transactionn_id=f'commission-{payment.id}'
                ).first()

                if success:
                    if payment.status == 'completed':
                        return {
                            'status': 'success',
                            'message': 'Payout already processed',
                            'escrow_id': escrow.id,
                        }

                    total_release = payment.amount
                    if commission_payment:
                        total_release += commission_payment.amount

                    escrow.current_balance = max(Decimal('0'), escrow.current_balance - total_release)
                    escrow.status = 'released' if escrow.current_balance == 0 else 'partially_released'
                    escrow.save(update_fields=['current_balance', 'status'])

                    payment.status = 'completed'
                    payment.save(update_fields=['status'])

                    if commission_payment:
                        commission_payment.status = 'completed'
                        commission_payment.save(update_fields=['status'])

                    milestone_instance = payment.milestone
                    if milestone_instance and not milestone_instance.is_paid:
                        milestone_instance.is_paid = True
                        milestone_instance.save(update_fields=['is_paid'])

                    return {
                        'status': 'success',
                        'message': 'Freelancer payout confirmed',
                        'escrow_id': escrow.id,
                        'remaining_balance': str(escrow.current_balance),
                        'milestone_id': milestone_instance.id if milestone_instance else None,
                    }

                # Handle failure scenario
                if payment.status != 'failed':
                    payment.status = 'failed'
                    payment.save(update_fields=['status'])

                if commission_payment and commission_payment.status != 'cancelled':
                    commission_payment.status = 'cancelled'
                    commission_payment.save(update_fields=['status'])

                milestone_instance = payment.milestone
                if milestone_instance and milestone_instance.is_paid:
                    milestone_instance.is_paid = False
                    milestone_instance.save(update_fields=['is_paid'])

                if escrow.status == 'release_pending':
                    escrow.status = 'funded'
                    escrow.save(update_fields=['status'])

                return {
                    'status': 'error',
                    'message': 'Freelancer payout failed',
                    'escrow_id': escrow.id,
                    'milestone_id': milestone_instance.id if milestone_instance else None,
                }

        except Payment.DoesNotExist:
            return {'status': 'error', 'message': 'Release payment not found'}
        except Exception as e:
            logger.error(f"Verify transfer failed: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def refund(self, *, user, escrow: EscrowTransaction, amount=None, reason="Project refund", provider_name=None):
        """
        Orchestrate refunds to client.
        - Only project client (owner) can request refund; admins/moderators could be added here.
        - Disallows refund if escrow is locked/disputed unless resolved by moderator.
        Delegates provider refund to PaymentService.
        """
        if escrow.is_locked:
            return {"status": "error", "message": "Escrow is locked due to dispute"}
        if user.id != escrow.project.client_id:
            return {"status": "error", "message": "Only the project client can request a refund"}

        try:
            with transaction.atomic():
                # Find original funding payment
                funding_payment = (
                    Payment.objects.filter(
                        escrow=escrow, transaction_type='funding', status='completed'
                    ).order_by('-timestamp').first()
                )
                if not funding_payment:
                    return {"status": "error", "message": "No completed funding to refund from"}

                provider = provider_name or funding_payment.provider
                provider_tx_id = funding_payment.provider_transactionn_id

                refund_amount = amount or escrow.current_balance
                if refund_amount <= 0:
                    return {"status": "error", "message": "No available balance to refund"}

                result = self.payment_service.refund(
                    provider_name=provider,
                    provider_transaction_id=provider_tx_id,
                    amount=refund_amount,
                    reason=reason,
                )
                if result.get('status') != 'success':
                    return {"status": "error", "message": result.get('message', 'Refund failed')}

                Payment.objects.create(
                    escrow=escrow,
                    user=escrow.project.client,
                    amount=refund_amount,
                    provider_transactionn_id=result.get('refund_id') or f'refund-{provider_tx_id}',
                    transaction_type='refund',
                    provider=provider,
                    status='completed',
                )

                escrow.current_balance -= refund_amount
                if escrow.current_balance == 0:
                    escrow.status = 'refunded'
                escrow.save()

                return {
                    'status': 'success',
                    'message': 'Refund processed',
                    'refund_amount': str(refund_amount),
                    'escrow_balance': str(escrow.current_balance),
                }
        except Exception as e:
            logger.error(f"Refund orchestration failed: {str(e)}")
            return {"status": "error", "message": str(e)}
