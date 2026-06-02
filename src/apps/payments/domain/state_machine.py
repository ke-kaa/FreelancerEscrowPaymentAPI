"""Payment status state machine."""

from __future__ import annotations

from common.patterns.state_machine import StateMachine

PAYMENT_FSM = StateMachine(
    field="status",
    transitions={
        "pending": {"active", "completed", "failed", "cancelled"},
        "active": {"completed", "failed", "cancelled"},
        # terminal: completed, failed, cancelled, disputed
        "disputed": {"completed", "cancelled"},
    },
)
