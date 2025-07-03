from django.db import models

from accounts.models import CustomUser

class UserProject(models.Model):
    STATUS_CHOICES = (
            ('pending', 'Pending'),
            ('active', 'Active'),       
            ('completed', 'Completed'),
            ('disputed', 'Disputed'),       
            ('cancelled', 'Cancelled'),
            )

    client = models.ForeignKey(CustomUser, related_name='client_projects', on_delete=models.PROTECT)
    freelancer = models.ForeignKey(CustomUser, related_name='freelancer_projects', on_delete=models.PROTECT)
    title = models.CharField(max_length=255)
    description = models.TextField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.10)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.client} -> {self.freelancer})"
