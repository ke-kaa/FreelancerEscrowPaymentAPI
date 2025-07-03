from django.db import models


from accounts.models import CustomUser
from escrow.models import EscrowTransaction


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
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='payment_records')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    stripe_transaction_id = models.CharField(max_length=100)  # From Stripe/PayPal
    transaction_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    status = models.CharField(choices=STATUS_CHOICES, default="pending")
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction_type} of {self.amount} for {self.escrow.project}"

