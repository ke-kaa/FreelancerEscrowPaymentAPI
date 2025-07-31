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
    
