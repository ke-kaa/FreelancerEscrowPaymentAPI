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

