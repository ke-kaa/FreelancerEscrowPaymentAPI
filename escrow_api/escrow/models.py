from django.db import models


from user_projects.models import UserProject


class EscrowTransaction(models.Model):
    STATUS_CHOICES = (
        ('pending_funding', 'Pending Funding'),
        ('funded', 'Funded'),
        ('release_pending', 'Release Pending'),
        ('released', 'Released'),
        ('partially_released', 'Partially Released'),
        ('refunded', 'Refunded'),
        ('disputed', 'Disputed'),
    )

    project = models.OneToOneField(UserProject, on_delete=models.CASCADE)
    funded_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    current_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_locked = models.BooleanField(default=False)  # Lock during disputes
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_funding')

    def __str__(self):
        return f"Escrow for {self.project.title} ({self.funded_amount})"

