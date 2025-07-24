from django.db import models


from user_projects.models import UserProject
from accounts.models import CustomUser

class Dispute(models.Model):
    STATUS_CHOICES = (
        ('open', 'Open'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    )
    
    DISPUTE_TYPE_CHOICES = (
        ('payment', 'Payment Issue'),
        ('quality', 'Work Quality'),
        ('delay', 'Project Delay'),
        ('other', 'Other'),
    )

    project = models.OneToOneField(UserProject, on_delete=models.CASCADE, related_name='dispute')
    raised_by = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name='disputes')
    
    dispute_type = models.CharField(max_length=20, choices=DISPUTE_TYPE_CHOICES, default='other')
    reason = models.TextField()
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    resolution = models.TextField(blank=True)
    resolved_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_disputes')
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    
    moderator_note = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Dispute for {self.project.title} by {self.raised_by}"

class DisputeMessage(models.Model):
    dispute = models.ForeignKey('Dispute', on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)