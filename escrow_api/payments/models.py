from django.db import models
from django.contrib.auth import get_user_model
from escrow.models import EscrowTransaction
from django.core.exceptions import ValidationError
from user_projects.models import Milestone

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
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    milestone = models.ForeignKey(
        Milestone,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments'
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction_type} of {self.amount} for {self.escrow.project}"

class PaymentMethod(models.Model):
    """
    Stores a client's saved payment options (e.g., a card or mobile wallet).
    """
    PROVIDER_CHOICES = (
        ('chapa', 'Chapa'),
        ('stripe', 'Stripe')
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
    Base payout method descriptor. Provider-specific details live in child tables.
    """
    PROVIDER_CHOICES = (
        ('stripe', 'Stripe'),
        ('chapa', 'Chapa'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payout_methods')
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)

    is_default = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'provider', 'is_default']
        verbose_name = "Payout Method"
        verbose_name_plural = "Payout Methods"

    def __str__(self):
        return f"{self.user.email} - {self.provider}"


class ChapaPayoutMethod(models.Model):
    """
    Chapa-specific bank account details required for transfers API.
    """
    payout_method = models.OneToOneField(PayoutMethod, on_delete=models.CASCADE, related_name='chapa_details')
    account_name = models.CharField(max_length=255, help_text="Recipient's full name")
    account_number = models.CharField(max_length=50, help_text="Recipient's account number")
    bank_code = models.CharField(max_length=10, help_text="Bank code for the recipient's bank")
    bank_name = models.CharField(max_length=100, blank=True, help_text="Bank name (for display)")

    def __str__(self):
        return f"Chapa – {self.account_name} ({self.account_number})"


class StripePayoutMethod(models.Model):
    """
    Stripe Connect account reference for freelancer payouts.
    """
    payout_method = models.OneToOneField(PayoutMethod, on_delete=models.CASCADE, related_name='stripe_details')
    stripe_account_id = models.CharField(max_length=255, help_text="Stripe Connect account ID (acct_...)", unique=True)
    charges_enabled = models.BooleanField(default=False)
    payouts_enabled = models.BooleanField(default=False)

    def __str__(self):
        return f"Stripe – {self.stripe_account_id}"


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


class WebhookEvent(models.Model):
    """
    Stores processed webhook event IDs to ensure idempotency.
    """
    provider = models.CharField(max_length=50)
    event_id = models.CharField(max_length=255, unique=True)
    received_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.provider}:{self.event_id}"
