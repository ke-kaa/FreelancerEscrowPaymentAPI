from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from .providers import get_payment_provider
from .models import Payment, PayoutMethod
from escrow.models import EscrowTransaction
from user_projects.models import UserProject
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class PaymentService:
    """
    Orchestrates payment business logic while delegating provider API calls
    to the selected provider. Provider is chosen per call or injected at init.
    """
    def __init__(self, provider_name = None):
        self.provider = get_payment_provider(provider_name=None)
        self.default_provider_name = provider_name

    def _get_provider(self, provider_name):
        name = provider_name or self.default_provider_name
        if not name:
            raise ValueError("provider_name is required (no default configured).")
        return get_payment_provider(name), name
    
    @transaction.atomic
    def initiate_escrow_payment(self, user, project, amount, provider_name = None, **kwargs):
        """
        - Creates the escrow transaction row (virtual escrow)
        - Initiates payment with provider (no provider hardcoding)
        - Creates a pending Payment record tied to escrow
        """
        try:
            provider, resolved_name = self._get_provider(provider_name)

            commission_amount = amount * settings.PLATFORM_COMMISSION_RATE
            
            # Escrow transaction record
            escrow = EscrowTransaction.objects.create(
                project=project,
                funded_amount=amount,
                current_balance=amount,
                commission_amount=commission_amount,
            )
            
            # Initiate payment with provider
            init = provider.charge(
                user=user,
                amount=amount,
                **kwargs
            )
            if init.get("status") != "success":
                # rollback escrow if init failed
                raise ValueError(init.get("message") or "Payment initialization failed")
                
            if init.get('status') == 'success':
                # payment record
                Payment.objects.create(
                    escrow=escrow,
                    user=user,
                    amount=amount,
                    provider_transactionn_id=init['tx_ref'],
                    transaction_type='funding',
                    provider=resolved_name,
                    status='pending'
                )
                
                return {
                    'status': 'success',
                    'payment_url': init['data']['checkout_url'],
                    'tx_ref': init['tx_ref'],
                    'escrow_id': escrow.id,
                    'provider': resolved_name,
                    'total_amount': str(amount),
                    'commission_rate': str(settings.PLATFORM_COMMISSION_RATE),
                    'commission_amount': str(commission_amount)
                }
            else:
                # Payment failed, rollback
                escrow.delete()
                return init
                        
        except Exception as e:
            logger.error(f"Payment initiation failed: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def verify_and_fund_escrow(self, tx_ref):
        """
        - Verifies payment with the same provider used to fund
        - Updates escrow and payment records
        """
        try:
            with transaction.atomic():
                payment = Payment.objects.select_related("escrow", "escrow__project").get(provider_transactionn_id=tx_ref, transaction_type="funding")
                # Verify payment with provider
                is_verified = self.provider.verify(tx_ref)
                
                if is_verified:
                    # Get payment record
                    payment = Payment.objects.get(provider_transactionn_id=tx_ref)
                    escrow = payment.escrow
                    
                    # Update escrow with funded amount
                    escrow.funded_amount = payment.amount
                    escrow.current_balance = payment.amount
                    escrow.status = 'funded'
                    escrow.save()
                    
                    # Update payment status
                    payment.status = 'completed'
                    payment.save()
                    
                    return {
                        'status': 'success',
                        'message': 'Escrow funded successfully',
                        'escrow_id': escrow.id,
                        'funded_amount': escrow.funded_amount,
                        "available_balance": str(escrow.current_balance),
                        "commission_amount": str(escrow.commission_amount)
                    }
                else:
                    return {'status': 'error', 'message': 'Payment verification failed'}
        except ObjectDoesNotExist:
            return {"status": "error", "message": "Funding payment not found."}
        except Exception as e:
            logger.error(f"Escrow funding failed: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def refund_to_client(self, escrow, amount = None, reason = "Project refund", provider_name = None):
        """
        - Refunds via the original funding provider by default
        - If provider_name is passed, use that; else derive from funding payment
        """
        # Find the original funding payment
        funding_payment = (
            Payment.objects.filter(
                escrow=escrow, transaction_type="funding", status="completed"
            )
            .order_by("-timestamp")
            .first()
        )
        if not funding_payment:
            return {"status": "error", "message": "No completed funding to refund from"}

        provider, resolved_name = self._get_provider(provider_name or funding_payment.provider)
        provider_tx_id = funding_payment.provider_transaction_id

        # Default to current_balance if amount not provided
        refund_amount = amount or escrow.current_balance
        if refund_amount <= 0:
            return {"status": "error", "message": "No available balance to refund"}

        # Call provider refund (to original payment method)
        result = provider.refund(provider_tx_id, refund_amount, reason=reason)

        if result.get("status") != "success":
            return {"status": "error", "message": result.get("message", "Refund failed")}

        # Record refund
        Payment.objects.create(
            escrow=escrow,
            user=escrow.project.client,
            amount=refund_amount,
            provider_transactionn_id=result.get("refund_id") or f"refund-{provider_tx_id}",
            transaction_type="refund",
            provider=resolved_name,
            status="completed",
        )

        # Update escrow balance
        escrow.current_balance -= refund_amount
        escrow.save()

        return {
            "status": "success",
            "message": "Refund processed",
            "refund_amount": str(refund_amount),
            "escrow_balance": str(escrow.current_balance),
        }
    
    def transfer_to_freelancer(self, freelancer, amount, provider_name = None, **kwargs):
        """
        Transfer funds to freelancer's account using the specified provider.
        """
        provider, resolved_name = self._get_provider(provider_name)
        
        try:
            payout_method = self._get_freelancer_payout_method(freelancer, resolved_name)

            if not payout_method:
                return {
                    'status': 'error', 
                    'message': f'No {resolved_name} payment method found for freelancer'
                }
            
            # Call provider's transfer method 
            transfer_result = provider.transfer_to_account(
                recipient=payout_method,
                amount=amount,
                **kwargs
            )
            
            return transfer_result
                
        except Exception as e:
            logger.error(f"Transfer to freelancer failed: {str(e)}")
            return {
                'status': 'error',
                'message': f'Transfer failed: {str(e)}'
            }

    def _get_freelancer_payout_method(self, freelancer, provider_name: str):
        """
        Get freelancer's preferred payment method for the given provider.
        """
        try:
            # Look for freelancer's saved payment method for this provider
            payout_method = PayoutMethod.objects.filter(
                user=freelancer,
                provider=provider_name,
                is_default=True
            ).first()

            if not payout_method:
                return None
            
            # Return formatted data for the provider
            if provider_name == 'chapa':
                return {
                    'account_name': payout_method.account_name,
                    'account_number': payout_method.account_number,
                    'bank_code': payout_method.bank_code,
                    'bank_name': payout_method.bank_name
                }
            # Shorty, we will add formatted data response for other provider methods shortly.
            else:
                return None
            
        except Exception as e:
            logger.error(f"Error getting freelancer payment method: {str(e)}")
            return None
