"""
WebhookEvent — durable record of every incoming provider webhook.

Inserted by the ingress view AFTER signature verification, BEFORE the
business handler runs. Uniqueness on (provider, external_event_id)
provides replay protection at the DB layer — duplicate deliveries fail
the insert and short-circuit the ingress with a 200.
"""

from __future__ import annotations

from django.db import models


class WebhookEvent(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("processed", "Processed"),
        ("failed", "Failed"),
    )

    provider = models.CharField(max_length=50)
    external_event_id = models.CharField(max_length=255)
    event_type = models.CharField(max_length=100, blank=True)
    raw_payload = models.JSONField(default=dict)
    signature = models.CharField(max_length=512, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    last_error = models.TextField(blank=True)
    attempts = models.PositiveIntegerField(default=0)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "external_event_id"],
                name="uniq_provider_event",
            )
        ]
        indexes = [
            models.Index(fields=["status", "received_at"]),
        ]
        ordering = ["-received_at"]

    def __str__(self) -> str:
        return f"{self.provider}:{self.external_event_id} ({self.status})"
