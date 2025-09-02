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

    def refund(self, provider_transaction_id, amount, reason = "Project refund"):
        """
        Process a Stripe refund.
        
        Args:
            provider_transaction_id: Payment Intent ID
            amount: Amount to refund (if None, full refund)
            reason: Reason for refund
            
        Returns:
            Dict containing refund response
        """
        try:
            # Get the Payment Intent to find the charge
            intent = stripe.PaymentIntent.retrieve(provider_transaction_id)
            
            if intent.status != 'succeeded':
                return {
                    'status': 'error',
                    'message': 'Cannot refund unsuccessful payment',
                    'error': 'Payment was not successful'
                }
            
            # Get the charge ID
            charge_id = intent.latest_charge
            if not charge_id:
                return {
                    'status': 'error',
                    'message': 'No charge found for this payment intent'
                }
            
            # Prepare refund parameters
            refund_params = {
                'charge': charge_id,
                'metadata': {
                    'reason': reason,
                    'escrow_refund': 'true',
                    'original_intent': provider_transaction_id
                }
            }
            
            # Add amount if specified
            if amount:
                refund_params['amount'] = int(amount * 100)  # Convert to cents
            
            # Create refund
            refund = stripe.Refund.create(**refund_params)
            
            logger.info(f"Stripe refund created: {refund.id} for intent {provider_transaction_id}")
            
            return {
                'status': 'success',
                'refund_id': refund.id,
                'amount': str(amount) if amount else 'full',
                'original_intent': provider_transaction_id,
                'provider': 'stripe'
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe refund error: {str(e)}")
            return {
                'status': 'error',
                'message': 'Refund failed',
                'error': str(e)
            }
        except Exception as e:
            logger.error(f"Unexpected error in Stripe refund: {str(e)}")
            return {
                'status': 'error',
                'message': 'Refund processing failed',
                'error': str(e)
            }
