"""Dispute status state machine."""

from __future__ import annotations

from common.patterns.state_machine import StateMachine

DISPUTE_FSM = StateMachine(
    field="status",
    transitions={
        "open": {"resolved"},
        "resolved": {"closed"},
        # terminal: closed
    },
)
