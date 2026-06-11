"""Unit — TransactionLog hash chain integrity."""

import pytest

from apps.audit.models import TransactionLog
from apps.audit.services import record_event, verify_chain

pytestmark = pytest.mark.django_db


def test_first_entry_has_empty_prev_hash():
    row = record_event(actor_id=1, action="escrow.update", target_type="EscrowTransaction", target_id=42, after={"status": "funded"})
    assert row.prev_hash == ""
    assert row.current_hash != ""


def test_chain_links_sequential_entries():
    a = record_event(actor_id=1, action="x", target_type="T", target_id=1)
    b = record_event(actor_id=1, action="y", target_type="T", target_id=1)
    assert b.prev_hash == a.current_hash
    ok, broken_id = verify_chain()
    assert ok is True
    assert broken_id is None


def test_tampering_breaks_chain():
    a = record_event(actor_id=1, action="x", target_type="T", target_id=1)
    record_event(actor_id=1, action="y", target_type="T", target_id=1)
    # Mutate a stored row in place — simulates tampering.
    a.after = {"injected": True}
    a.save(update_fields=["after"])
    ok, broken_id = verify_chain()
    assert ok is False
    assert broken_id == a.id


def test_hash_deterministic_for_same_inputs():
    h1 = TransactionLog.compute_hash(
        prev_hash="", actor_id="1", action="x", target_type="T",
        target_id="1", before={}, after={"k": "v"}, timestamp_iso="2026-01-01T00:00:00",
    )
    h2 = TransactionLog.compute_hash(
        prev_hash="", actor_id="1", action="x", target_type="T",
        target_id="1", before={}, after={"k": "v"}, timestamp_iso="2026-01-01T00:00:00",
    )
    assert h1 == h2
