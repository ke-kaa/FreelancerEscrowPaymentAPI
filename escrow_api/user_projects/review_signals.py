from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from .models import Review, UserProject

REVIEW_PERIOD_DAYS = 14

@receiver(post_save, sender=Review)
def auto_make_reviews_visible(sender, instance, created, **kwargs):
    if not created:
        return

    project_reviews = Review.objects.filter(project=instance.project)

    if project_reviews.count() == 2:
        project_reviews.update(is_visible=True)