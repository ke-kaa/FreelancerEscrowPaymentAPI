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
    completed_at = models.DateTimeField(null=True, blank=True)

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
    is_withdrawn = models.BooleanField(default=False)
    accepted_at = models.DateTimeField(null=True, blank=True)


class Milestone(models.Model):
    project = models.ForeignKey(UserProject, on_delete=models.PROTECT, related_name="milestones")
    title = models.CharField(max_length=255)
    description = models.TextField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=[
        ("pending", "Pending"),
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        ("rejected", "Rejected")
    ], default="pending")

    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_reason = models.TextField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    is_paid = models.BooleanField(default=False)


class Review(models.Model):
    REVIEW_TYPE_CHOICES = [
        ("client", "Client Review"),  # from client to freelancer
        ("freelancer", "Freelancer Review"),  # from freelancer to client
    ]

    project = models.ForeignKey(UserProject, on_delete=models.CASCADE, related_name="reviews")
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="given_reviews")
    reviewee = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_reviews")
    
    review_type = models.CharField(max_length=20, choices=REVIEW_TYPE_CHOICES)
    
    rating = models.PositiveSmallIntegerField()
    communication = models.PositiveSmallIntegerField(null=True, blank=True)
    quality = models.PositiveSmallIntegerField(null=True, blank=True)
    professionalism = models.PositiveSmallIntegerField(null=True, blank=True)

    comment = models.TextField()
    private_comment = models.TextField(blank=True, null=True)
    
    is_visible = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['project', 'reviewer', 'review_type']

