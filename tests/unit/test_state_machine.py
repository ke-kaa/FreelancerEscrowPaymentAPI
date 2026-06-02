"""Unit — generic StateMachine + InvalidTransition."""

from dataclasses import dataclass

import pytest

from common.exception.domain import InvalidTransition
from common.patterns.state_machine import StateMachine

ESCROW_FSM = StateMachine(
    field="status",
    transitions={
        "pending": {"funded", "cancelled"},
        "funded": {"released", "refunded", "disputed"},
        "disputed": {"released", "refunded"},
    },
)


@dataclass
class FakeEscrow:
    status: str
    saved: bool = False
    save_fields: list[str] | None = None

    def save(self, update_fields=None):
        self.saved = True
        self.save_fields = list(update_fields) if update_fields else None


class TestStateMachine:
    def test_allowed_transition(self):
        esc = FakeEscrow(status="pending")
        ESCROW_FSM.transition(esc, to="funded", save=False)
        assert esc.status == "funded"

    def test_can_transition(self):
        esc = FakeEscrow(status="pending")
        assert ESCROW_FSM.can_transition(esc, to="funded")
        assert not ESCROW_FSM.can_transition(esc, to="released")

    def test_disallowed_raises_invalid_transition(self):
        esc = FakeEscrow(status="pending")
        with pytest.raises(InvalidTransition) as exc:
            ESCROW_FSM.transition(esc, to="released", save=False)
        details = exc.value.details
        assert details["from"] == "pending"
        assert details["to"] == "released"
        assert "funded" in details["allowed"]

    def test_transition_with_save(self):
        esc = FakeEscrow(status="pending")
        ESCROW_FSM.transition(esc, to="funded")
        assert esc.saved is True
        assert esc.save_fields == ["status"]

    def test_unknown_source_state_blocks_all(self):
        esc = FakeEscrow(status="archived")
        with pytest.raises(InvalidTransition):
            ESCROW_FSM.transition(esc, to="funded", save=False)
