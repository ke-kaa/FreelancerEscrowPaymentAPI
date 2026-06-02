"""
TimestampedModel — abstract base providing created_at / updated_at.

Refs: MIGRATION_PLAN.md Phase 3
"""

from __future__ import annotations

from django.db import models


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
