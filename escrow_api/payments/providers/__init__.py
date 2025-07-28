from .base import BasePaymentProvider
from .chapa import ChapaProvider

def get_payment_provider(provider_name: str, **kwargs) -> BasePaymentProvider:
    """
    Factory function to get payment provider instances.
    
    Args:
        provider_name: Name of the payment provider
        **kwargs: Additional configuration
        
    Returns:
        BasePaymentProvider: Payment provider instance
    """
    providers = {
        'chapa': ChapaProvider,
        # other providers ...
    }
    
    if provider_name not in providers:
        raise ValueError(f"Unknown payment provider: {provider_name}")
    
    return providers[provider_name](**kwargs)