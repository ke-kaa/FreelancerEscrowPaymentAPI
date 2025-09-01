import stripe
import requests
import json
import environ
import os
import logging
from .base import BasePaymentProvider
from django.conf import settings
import uuid
import http.client
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class StripeProvider(BasePaymentProvider):
    """
    Stripe payment provider implementation for escrow system.
    Handles payments, refunds, and transfers to freelancers.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        stripe.api_key = settings.STRIPE_SECRET_KEY
        self.publishable_key = settings.STRIPE_PUBLISHABLE_KEY
        self.currency = getattr(settings, 'STRIPE_CURRENCY', 'usd')
        self.country = getattr(settings, 'STRIPE_COUNTRY', 'US')
        self.webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')

    def charge(self, user, amount, **kwargs):
        """
        Create a Stripe Payment Intent for escrow funding.
        
        Args:
            user: User object making the payment
            amount: Amount to charge (Decimal)
            **kwargs: Additional parameters
            
        Returns:
            Dict containing payment initiation response
        """
        try:
            # Convert amount to cents (Stripe uses smallest currency unit)
            amount_cents = int(amount * 100)
            
            # Create Payment Intent
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=self.currency,
                customer_email=user.email,
                metadata={
                    'user_id': str(user.id),
                    'user_email': user.email,
                    'project_title': kwargs.get('project_title', 'Unknown Project'),
                    'escrow_funding': 'true',
                    'tx_ref': f'escrow-fund-{uuid.uuid4().hex[:10]}'
                },
                description=f"Escrow funding for {kwargs.get('project_title', 'project')}",
                automatic_payment_methods={
                    'enabled': True,
                },
            )
            
            logger.info(f"Stripe Payment Intent created: {intent.id} for user {user.email}, amount: {amount}")
            
            return {
                'status': 'success',
                'payment_intent_id': intent.id,
                'client_secret': intent.client_secret,
                'tx_ref': intent.metadata.get('tx_ref'),
                'provider': 'stripe',
                'data': {
                    'checkout_url': f"/payment/stripe/{intent.id}",  # Frontend URL
                    'client_secret': intent.client_secret
                }
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe API error in charge: {str(e)}")
            return {
                'status': 'error',
                'message': 'Payment initiation failed',
                'error': str(e)
            }
        except Exception as e:
            logger.error(f"Unexpected error in Stripe charge: {str(e)}")
            return {
                'status': 'error',
                'message': 'Payment initiation failed',
                'error': str(e)
            }
    
    
        """Handle transfer created webhook"""
        # return {
        #     'status': 'success',
        #     'message': 'Transfer created',
        #     'transfer_id': event_data.get('id'),
        #     'amount': event_data.get('amount')
        # }

    def verify(self, provider_transaction_id):
        """
        Verify a Stripe Payment Intent.
        
        Args:
            provider_transaction_id: Payment Intent ID
            
        Returns:
            bool: True if payment is successful
        """
        try:
            intent = stripe.PaymentIntent.retrieve(provider_transaction_id)
            
            is_successful = intent.status == 'succeeded'
            
            logger.info(f"Stripe payment verification result: {is_successful} for intent {provider_transaction_id}")
            return is_successful
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe verification error: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error in Stripe verify: {str(e)}")
            return False
  