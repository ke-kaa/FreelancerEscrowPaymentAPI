from django.db import models


from UserProjects.models import UserProject
from accounts.models import CustomUser

class Dispute(models.Model):
            STATUS_CHOICES = (
                ('open', 'Open'),
                ('resolved', 'Resolved'),
                ('closed', 'Closed'),
            )
            project = models.OneToOneField(UserProject, on_delete=models.CASCADE, related_name='dispute')
            raised_by = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name='disputes')
            reason = models.TextField()
            resolved = models.BooleanField(default=False)
            status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
            resolution = models.TextField(blank=True)
            resolved_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_disputes')
            created_at = models.DateTimeField(auto_now_add=True)
            updated_at = models.DateTimeField(auto_now=True)

            def __str__(self):
                return f"Dispute for {self.project.title} by {self.raised_by}"
