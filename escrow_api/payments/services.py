from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from .providers import get_payment_provider
from .models import Payment, PayoutMethod, StripePayoutMethod, ChapaPayoutMethod
from escrow.models import EscrowTransaction
from user_projects.models import UserProject
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class PaymentService:
    """
    Provider adapter. This class should NOT create or update Escrow/Payment records.
    It only calls the configured payment provider(s).
    """
    def __init__(self, provider_name = None):
        self.default_provider_name = provider_name

    def _get_provider(self, provider_name):
        name = provider_name or self.default_provider_name
        if not name:
            raise ValueError("provider_name is required (no default configured).")
        return get_payment_provider(name), name

    def init_charge(self, *, user, amount, provider_name=None, **kwargs):
        provider, resolved_name = self._get_provider(provider_name)
        return provider.charge(user=user, amount=amount, **kwargs)

    def verify_payment(self, *, provider_name, provider_transaction_id):
        provider, _ = self._get_provider(provider_name)
        return provider.verify(provider_transaction_id)

    def refund(self, *, provider_name, provider_transaction_id, amount=None, reason="Project refund"):
        provider, _ = self._get_provider(provider_name)
        return provider.refund(provider_transaction_id, amount, reason)
    
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
            # Locate base payout method for provider
            payout_method = PayoutMethod.objects.filter(
                user=freelancer,
                provider=provider_name,
                is_active=True,
            ).order_by('-is_default', '-created_at').first()

            if not payout_method:
                return None

            # Map provider-specific details
            if provider_name == 'chapa':
                details = getattr(payout_method, 'chapa_details', None)
                if not details:
                    return None
                return {
                    'account_name': details.account_name,
                    'account_number': details.account_number,
                    'bank_code': details.bank_code,
                    'bank_name': details.bank_name,
                }
            elif provider_name == 'stripe':
                details = getattr(payout_method, 'stripe_details', None)
                if not details or not details.payouts_enabled:
                    return None
                return {
                    'stripe_account_id': details.stripe_account_id,
                    'user_id': str(freelancer.id),
                }
            else:
                return None
            
        except Exception as e:
            logger.error(f"Error getting freelancer payment method: {str(e)}")
            return None
