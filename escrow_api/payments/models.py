from django.db import models
from django.contrib.auth import get_user_model
from escrow.models import EscrowTransaction
from django.core.exceptions import ValidationError

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
    Stores freelancer's payout account details for transfers.
    """
    PROVIDER_CHOICES = (
        ('telebirr', 'Telebirr'),
        ('mpesa', 'M-Pesa'),
        ('chapa', 'Chapa'),
        ('webirr', 'WeBirr'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payout_methods')
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)

    account_name = models.CharField(max_length=255, help_text="Recipient's full name")
    account_number = models.CharField(max_length=50, help_text="Recipient's account number")
    bank_code = models.CharField(max_length=10, help_text="Bank code for the recipient's bank")
    bank_name = models.CharField(max_length=100, blank=True, help_text="Bank name (for display)")

    is_default = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'provider', 'account_number']
        verbose_name = "Payout Method"
        verbose_name_plural = "Payout Methods"

    def __str__(self):
        return f"{ self.user.email } - { self.provider } - { self.account_number }"
    
    def clean(self):
        """Validate payout method based on provider requirements"""
        if self.provider == 'chapa':
            if not all([self.account_name, self.account_number, self.bank_code]):
                raise ValidationError("Chapa requires account_name, account_number, and bank_code")
        elif self.provider in ['mpesa', 'telebirr', 'webirr']:
            if not self.phone_number:
                raise ValidationError(f"{self.provider} requires phone_number")
        # other are coming soon ..............
            
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class Bank(models.Model):
    """
    Stores bank information for Chapa transfers.
    This can be populated from Chapa's get banks endpoint.
    """
    code = models.CharField(max_length=10, unique=True, help_text="Bank code from Chapa API")
    name = models.CharField(max_length=100, help_text="Bank name")
    country = models.CharField(max_length=10, default='ET', help_text="Country code")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Bank"
        verbose_name_plural = "Banks"
    
    def __str__(self):
        return f"{self.name} ({self.code})"