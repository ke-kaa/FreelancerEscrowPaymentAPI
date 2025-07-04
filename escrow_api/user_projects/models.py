from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class UserProject(models.Model):
    STATUS_CHOICES = (
            ('pending', 'Pending'),
            ('active', 'Active'),       
            ('completed', 'Completed'),
            ('disputed', 'Disputed'),       
            ('cancelled', 'Cancelled'),
        )

    client = models.ForeignKey(User, related_name='client_projects', on_delete=models.PROTECT)
    freelancer = models.ForeignKey(User, related_name='freelancer_projects', on_delete=models.PROTECT, null=True, blank=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.10)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_public = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.title} ({self.client} -> {self.freelancer})"


class Proposal(models.Model):
    project = models.ForeignKey(UserProject, on_delete=models.PROTECT, related_name="proposals")
    freelancer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="proposals")
    cover_letter = models.TextField()
    bid_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=[("pending", "Pending"), ("accepted", "Accepted"), ("rejected", "Rejected")], default="pending")
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    client_note = models.TextField(blank=True, null=True)
    estimated_delivery_days = models.PositiveIntegerField()
    is_seen_by_client = models.BooleanField(default=False)
    is_widthdrawn = models.BooleanField(default=False)


class Milestone(models.Model):
    project = models.ForeignKey(UserProject, on_delete=models.PROTECT, related_name="milestones")
    title = models.CharField(max_length=255)
    description = models.TextField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=[("pending", "Pending"), ("submitted", "Submitted"), ("approved", "Approved"), ("rejected", "Rejected")], default="pending")
    due_date = models.DateField(null=True, blank=True)


class Review(models.Model):
    project = models.ForeignKey(UserProject, on_delete=models.CASCADE, related_name="reviews")
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="given_reviews")
    reviewee = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_reviews")
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
