import requests
import json
import environ
import os
import logging
from .base import BasePaymentProvider
from django.conf import settings
import uuid
import http.client

logger = logging.getLogger(__name__)

env = environ.Env()
BASE_DIR = settings.BASE_DIR
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

class ChapaProvider(BasePaymentProvider):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.secret_key = env('CHAPA_SECRET_KEY')
        self.base_url = "https://api.chapa.co/v1"
        self.callback_url = env('CHAPA_CALLBACK_URL')
        self.return_url = env('CHAPA_RETURN_URL', default='http://localhost:3000/payment/success')

    def charge(self, user, amount, **kwargs):
        """
        Initiate a Chapa payment.
        
        Args:
            user: User object
            amount: Amount to charge (Decimal)
            **kwargs: Additional parameters
            
        Returns:
            Dict containing payment initiation response
        """
        try:
            url = f"{self.base_url}/transaction/initialize"
            tx_ref = f'escrow-fund-{uuid.uuid4().hex[:10]}'
            
            payload = {
                "amount": str(amount),
                "currency": "ETB",
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone_number": user.phone_number or "",
                "tx_ref": tx_ref,
                "callback_url": self.callback_url,
                "return_url": self.return_url,
                "customization": {
                    "title": "Escrow Fund",
                    "description": f"Funding escrow for project - {kwargs.get('project_title', 'Unknown Project')}"
                }
            }
            
            headers = {
                'Authorization': f'Bearer {self.secret_key}',
                'Content-Type': 'application/json'
            }
            
            logger.info(f"Initiating Chapa payment for user {user.email}, amount: {amount}")
            
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            data['tx_ref'] = tx_ref
            data['provider'] = 'chapa'
            
            logger.info(f"Chapa payment initiated successfully. TX Ref: {tx_ref}")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Chapa API request failed: {str(e)}")
            return {
                'status': 'error',
                'message': 'Payment initiation failed',
                'error': str(e)
            }
        except Exception as e:
            logger.error(f"Unexpected error in Chapa charge: {str(e)}")
            return {
                'status': 'error',
                'message': 'Payment initiation failed',
                'error': str(e)
            }
    
    def verify(self, provider_transaction_id):
        """
        Verify a Chapa payment using transaction reference.
        
        Args:
            provider_transaction_id: Transaction reference (tx_ref)
            
        Returns:
            bool: True if payment is successful
        """
        try:
            url = f"{self.base_url}/transaction/verify/{provider_transaction_id}"
            payload = ''
            headers = {
                'Authorization': f'Bearer {self.secret_key}'
            }

            logger.info(f"Verifying Chapa Payment: {provider_transaction_id}")

            response = requests.get(url, headers=headers, data=payload)
            data = response.json()
            is_successful = data.get('status') == 'success'

            logger.info(f"Chapa payment verification result: {is_successful}")
            return is_successful
        except requests.exceptions.RequestException as e:
            logger.error(f"Chapa verfication request failed: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error in Chapa verify: {str(e)}")
            return False
    
    def refund(self, provider_transaction_id, amount=None, reason="Project refund"):
        """
        Process a refund.

        Args:
            provider_transaction_id: Transaction reference
            amount: Amount to refund (not morethan funded amount.)
        
        Returns:
            Dict containing refund initiation response
        """
        # Refund may not be instant. Chapa may return status: "pending". You should:
        # Mark refund Payment as "pending" in DB.
        # Update to "completed" when webhook confirms.
        try:
            # verify original transaction - extra api call can be avoided.
            verification_url = f"{self.base_url}/transaction/verify/{provider_transaction_id}"
            headers = {
                'Authorization': f'Bearer {self.secret_key}'
            }

            # OG transaction detail
            verify_response = requests.get(verification_url, headers=headers)
            verify_response.raise_for_status()
            original_transaction = verify_response.json()
            
            if original_transaction.get('status') != 'success':
                return {
                    'status': 'error',
                    'message': 'Cannot refund unsuccessful transaction',
                    'error': 'Transaction was not successful'
                }
            
            refund_url = f"{self.base_url}/refund/{provider_transaction_id}"
            
            if amount is None:
                amount = original_transaction.get('data', {}).get('amount', 0)
            
            payload = {
                'reason': reason,
                'amount': str(amount) if amount else None,
                'meta': {
                    'customer_id': original_transaction.get('data', {}).get('customer', {}).get('email', ''),
                    'reference': f'REF-{provider_transaction_id}',
                }
            }
            
            # Convert payload to form data as required by Chapa API
            form_data = f"reason={reason}&amount={amount}&meta[customer_id]={payload['meta']['customer_id']}&meta[reference]={payload['meta']['reference']}&meta[escrow_refund]=true"
            
            refund_headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Authorization': f'Bearer {self.secret_key}'
            }
            
            logger.info(f"Initiating Chapa refund for tx_ref: {provider_transaction_id}, amount: {amount}")
            
            # Make refund request
            refund_response = requests.post(refund_url, data=form_data, headers=refund_headers)
            refund_response.raise_for_status()
            
            refund_data = refund_response.json()
            
            logger.info(f"Chapa refund initiated successfully. Refund ID: {refund_data.get('data', {}).get('refund_id', 'N/A')}")
            
            return {
                'status': 'success',
                'message': 'Refund initiated successfully',
                'refund_id': refund_data.get('data', {}).get('refund_id'),
                'amount': amount,
                'original_tx_ref': provider_transaction_id,
                'provider': 'chapa'
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Chapa refund API request failed: {str(e)}")
            return {
                'status': 'error',
                'message': 'Refund request failed',
                'error': str(e)
            }
        except KeyError as e:
            logger.error(f"Missing required data in transaction verification: {str(e)}")
            return {
                'status': 'error',
                'message': 'Invalid transaction data',
                'error': f'Missing field: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Unexpected error in Chapa refund: {str(e)}")
            return {
                'status': 'error',
                'message': 'Refund processing failed',
                'error': str(e)
            }

    def get_payment_status(self, provider_transaction_id):
        """
        Get payment status from Chapa.
        
        Args:
            provider_transaction_id: Transaction reference
            
        Returns:
            str: Payment status
        """
        try:
            url = f"{self.base_url}/transaction/verify/{provider_transaction_id}"
            headers = {
                'Authorization': f'Bearer {self.secret_key}'
            }
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            return data.get('status', 'unknown')
            
        except Exception as e:
            logger.error(f"Error getting payment status: {str(e)}")
            return 'error'

    def transfer_to_account(self, recipient, amount, **kwargs):
        """
        Transfer funds to freelancer's account via Chapa.
        
        Args:
            recipient: Dict containing recipient payment method info
            amount: Amount to transfer
            **kwargs: Additional parameters
            
        Returns:
            Dict containing transfer response
        """
        try:
            url = f"{self.base_url}/transfers"
            transfer_ref = f"freelancer-payment-{uuid.uuid4().hex[:10]}"
            
            payload = {
                "account_name": recipient['account_name'],
                "account_number": recipient['account_number'],
                "amount": str(amount),
                "currency": "ETB",
                "reference": transfer_ref,
                "bank_code": int(recipient['bank_code'])
            }
            
            headers = {
                'Authorization': f'Bearer {self.secret_key}',
                'Content-Type': 'application/json'
            }
            
            logger.info(f"Initiating Chapa transfer: {amount} to {recipient.get('email', 'saved_method')}")
            
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            
            logger.info(f"Initiating Chapa transfer: {amount} ETB to {recipient['account_name']} ({recipient['account_number']})")

            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            
            logger.info(f"Chapa transfer initiated successfully. Reference: {transfer_ref}")

            return {
                'status': 'success',
                'transfer_id': data.get('data', {}).get('transfer_id'),
                'reference': transfer_ref,
                'amount': str(amount),
                'recipient': recipient['account_name'],
                'message': 'Transfer initiated successfully'
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Chapa transfer API request failed: {str(e)}")
            return {
                'status': 'error',
                'message': 'Transfer request failed',
                'error': str(e)
            }
        except Exception as e:
            logger.error(f"Unexpected error in Chapa transfer: {str(e)}")
            return {
                'status': 'error',
                'message': 'Transfer processing failed',
                'error': str(e)
            }
        
    def get_transfer_status(self, transfer_reference: str) -> dict:
        """
        Get the status of a transfer using the reference.
        
        Args:
            transfer_reference: The reference used when initiating the transfer
            
        Returns:
            Dict containing transfer status
        """
        try:
            url = f"{self.base_url}/transfers/{transfer_reference}"
            headers = {
                'Authorization': f'Bearer {self.secret_key}'
            }
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            
            return {
                'status': 'success',
                'transfer_data': data.get('data', {}),
                'status': data.get('data', {}).get('status', 'unknown')
            }
            
        except Exception as e:
            logger.error(f"Error getting transfer status: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }

    def get_banks(self) -> dict:
        """
        Get list of available banks from Chapa.
        
        Returns:
            Dict containing banks list
        """
        try:
            url = f"{self.base_url}/banks"
            headers = {
                'Authorization': f'Bearer {self.secret_key}'
            }
            
            response = requests.get(url, headers=headers, data='')
            response.raise_for_status()
            
            data = response.json()
            
            return {
                'status': 'success',
                'banks': data.get('data', [])
            }
            
        except Exception as e:
            logger.error(f"Error getting banks: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def verify_transfer(self, transfer_reference):
        """
        Verify transfers after you initiated a transfer.

        Args:
            transfer_reference: The reference used when initiating the transfer

        Returns:
            Dict containing transfer status
        """
        try:
            url = f'{self.base_url}/transfers/verify/{transfer_reference}'
            headers = {
                'Authorization': f'Bearer {self.secret_key}'
            }

            response = requests.get(url, headers=headers)
            response.raise_for_status()

            data = response.json()

            return {
                'status': 'success',
                'data': data
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }