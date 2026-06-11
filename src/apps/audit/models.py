"""
TransactionLog — append-only, hash-chained audit ledger.

Every financial state transition appends one row. `prev_hash` links to the
prior row's `current_hash`; `current_hash` covers (prev_hash, actor_id,
action, target_type, target_id, before, after, timestamp). Tampering
breaks the chain at the modified row.

This complements django-auditlog (which records ORM row diffs) by
capturing INTENT — what the service believed it was doing.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from django.db import models


def _hash(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


class TransactionLog(models.Model):
    actor_id = models.CharField(max_length=64, blank=True)
    action = models.CharField(max_length=100)
    target_type = models.CharField(max_length=100)
    target_id = models.CharField(max_length=64)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    prev_hash = models.CharField(max_length=64, blank=True)
    current_hash = models.CharField(max_length=64, db_index=True)
    # Set explicitly by record_event() so the hash and stored value
    # always derive from the same datetime instance. auto_now_add can
    # drift by microseconds and break verify_chain().
    timestamp = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["target_type", "target_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.action} {self.target_type}:{self.target_id} @ {self.timestamp.isoformat()}"

    @staticmethod
    def compute_hash(
        *,
        prev_hash: str,
        actor_id: str,
        action: str,
        target_type: str,
        target_id: str,
        before: dict[str, Any],
        after: dict[str, Any],
        timestamp_iso: str,
    ) -> str:
        return _hash(
            prev_hash,
            actor_id,
            action,
            target_type,
            target_id,
            json.dumps(before, sort_keys=True, default=str),
            json.dumps(after, sort_keys=True, default=str),
            timestamp_iso,
        )
