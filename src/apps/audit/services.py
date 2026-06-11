"""Append a record to the hash-chained TransactionLog."""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from .models import TransactionLog


def record_event(
    *,
    actor_id: str | int | None,
    action: str,
    target_type: str,
    target_id: str | int,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> TransactionLog:
    """
    Append-only write — never updates an existing row. Uses
    `select_for_update()` on the tail row to serialize hash chaining
    across concurrent writers.
    """
    now = timezone.now()
    now_iso = now.isoformat()
    with transaction.atomic():
        tail = (
            TransactionLog.objects.select_for_update()
            .order_by("-id")
            .first()
        )
        prev_hash = tail.current_hash if tail else ""

        current_hash = TransactionLog.compute_hash(
            prev_hash=prev_hash,
            actor_id=str(actor_id or ""),
            action=action,
            target_type=target_type,
            target_id=str(target_id),
            before=before or {},
            after=after or {},
            timestamp_iso=now_iso,
        )

        return TransactionLog.objects.create(
            actor_id=str(actor_id or ""),
            action=action,
            target_type=target_type,
            target_id=str(target_id),
            before=before or {},
            after=after or {},
            prev_hash=prev_hash,
            current_hash=current_hash,
            timestamp=now,
        )


def verify_chain(start_id: int = 1) -> tuple[bool, int | None]:
    """
    Walk the ledger and re-derive each row's hash. Returns
    (ok, first_break_id_or_None).
    """
    prev_hash = ""
    for row in TransactionLog.objects.order_by("id").iterator():
        expected = TransactionLog.compute_hash(
            prev_hash=prev_hash,
            actor_id=row.actor_id,
            action=row.action,
            target_type=row.target_type,
            target_id=row.target_id,
            before=row.before,
            after=row.after,
            timestamp_iso=row.timestamp.isoformat(),
        )
        if expected != row.current_hash or row.prev_hash != prev_hash:
            return False, row.id
        prev_hash = row.current_hash
    return True, None
