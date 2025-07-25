from django.db import models
from django.contrib.auth import get_user_model
from escrow.models import EscrowTransaction

User = get_user_model()

class Payment(models.Model):
    TYPE_CHOICES = (
        ('funding', 'Funding'),
        ('release', 'Release'),
        ('refund', 'Refund'),
        ('commission', 'Commission'),
    )

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('disputed', 'Disputed'),
        ('cancelled', 'Cancelled'),
    )

    escrow = models.ForeignKey(EscrowTransaction, on_delete=models.CASCADE, related_name='payments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payment_records')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    provider_transactionn_id = models.CharField(max_length=255)
    transaction_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    provider = models.CharField(max_length=50, blank=True) # e.g., 'stripe', 'chapa'
    status = models.CharField(choices=STATUS_CHOICES, default="pending")
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction_type} of {self.amount} for {self.escrow.project}"

class PaymentMethod(models.Model):
    """
    Stores a client's saved payment options (e.g., a card or mobile wallet).
    """
    PROVIDER_CHOICES = (
        ('telebirr', 'Telebirr'),
        ('mpesa', 'M-Pesa'),
        ('chapa', 'Chapa'),
        ('webirr', 'WeBirr'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payment_methods')
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    provider_token = models.CharField(max_length=255) # Secure token from the provider
    display_info = models.CharField(max_length=100) # e.g., "Visa ending in 4242"
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user}'s {self.provider} - {self.display_info}"


class PayoutMethod(models.Model):
    """
    Stores a freelancer's information for receiving money.
    """
    PROVIDER_CHOICES = (
        ('telebirr', 'Telebirr'),
        ('mpesa', 'M-Pesa'),
        ('chapa', 'Chapa'),
        ('webirr', 'WeBirr'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payout_methods')
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    provider_account_id = models.CharField(max_length=255) # Account ID, phone number, etc.
    display_info = models.CharField(max_length=100) # e.g., "Stripe Account" or "0912345678"
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user}'s {self.provider} Payout"

