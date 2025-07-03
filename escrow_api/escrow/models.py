from django.db import models


from user_projects.models import UserProject

# Create your models here.
class EscrowTransaction(models.Model):
    STATUS_CHOICES = (
        ('funded', 'Funded'),
        ('released', 'Released'),
        ('refunded', 'Refunded'),
        ('disputed', 'Disputed'),
    )

    project = models.OneToOneField(UserProject, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_locked = models.BooleanField(default=False)  # Lock during disputes
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2)
    # stripe_payment_intent_id = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Escrow for {self.project.title} ({self.amount})"