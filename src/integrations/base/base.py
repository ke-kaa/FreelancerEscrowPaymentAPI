import uuid
from abc import ABC, abstractmethod

class BasePaymentProvider(ABC):
    """
    Abstract base class for all payment providers.
    Defines the common interface that all payment providers must implement.
    """

    def __init__(self, **kwargs):
        """Initialize the payment provider with configuration."""
        self.config = kwargs

    @abstractmethod
    def charge(self, user, amount, **kwargs):
        """
        Initiate a payment charge.
        
        Args:
            user: User object making the payment
            amount: Amount to charge (as Decimal)
            **kwargs: Additional parameters specific to the provider
            
        Returns:
            Dict containing payment initiation response
        """
        pass
    
    @abstractmethod
    def verify(self, provider_transaction_id: str) -> bool:
        """
        Verify a payment transaction.
        
        Args:
            provider_transaction_id: Transaction ID from the provider
            
        Returns:
            bool: True if payment is successful, False otherwise
        """
        pass
    
    @abstractmethod
    def refund(self, provider_transaction_id, amount):
        """
        Process a refund.
        
        Args:
            provider_transaction_id: Original transaction ID
            amount: Amount to refund (if None, full refund)
            
        Returns:
            Dict containing refund response
        """
        pass
    
    @abstractmethod
    def get_payment_status(self, provider_transaction_id):
        """
        Get the current status of a payment.
        
        Args:
            provider_transaction_id: Transaction ID from the provider
            
        Returns:
            str: Payment status (pending, completed, failed, etc.)
        """
        pass
    
    def validate_webhook(self, payload, signature):
        """
        Validate webhook signature (optional implementation).
        
        Args:
            payload: Raw webhook payload
            signature: Webhook signature header
            
        Returns:
            bool: True if webhook is valid
        """
        return True  # Override in specific providers if needed
    
    def process_webhook(self, payload):
        """
        Process webhook payload (optional implementation).
        
        Args:
            payload: Parsed webhook payload
            
        Returns:
            Dict containing processing result
        """
        return {"status": "processed"}