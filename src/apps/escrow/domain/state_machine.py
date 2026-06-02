"""
EscrowTransaction status state machine.

Every status mutation in EscrowService MUST go through ESCROW_FSM.transition().
Direct `escrow.status = '...'` assignments are a regression.
"""

from __future__ import annotations

from common.patterns.state_machine import StateMachine

ESCROW_FSM = StateMachine(
    field="status",
    transitions={
        "pending_funding": {"funded", "refunded"},  # refunded = cancel-before-fund
        "funded": {"release_pending", "refunded", "disputed"},
        "release_pending": {
            "released",
            "partially_released",
            "funded",  # transfer failed, balance restored
            "disputed",
        },
        "partially_released": {"release_pending", "refunded", "disputed"},
        "disputed": {"funded", "released", "refunded"},
        # terminal: released, refunded
    },
)
