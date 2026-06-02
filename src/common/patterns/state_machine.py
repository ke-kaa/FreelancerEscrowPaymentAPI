"""
Generic state machine for model status transitions.

Each domain defines a transition table: `{from_state: {to_state, ...}}`.
Invalid moves raise `InvalidTransition` with structured details.

Phase 5 wires escrow / payments / disputes status changes through this.

Refs: MIGRATION_PLAN.md Phase 5; ARCHITECTURE_AUDIT.md §9
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from common.exception.domain import InvalidTransition

Transitions = Mapping[str, Iterable[str]]


class StateMachine:
    """
    Declarative transition table + transition() helper.

    Usage:
        ESCROW_FSM = StateMachine(
            field="status",
            transitions={
                "pending":  {"funded", "cancelled"},
                "funded":   {"released", "refunded", "disputed"},
                "disputed": {"released", "refunded"},
            },
        )
        ESCROW_FSM.transition(escrow, to="funded")
    """

    def __init__(self, *, field: str, transitions: Transitions) -> None:
        self.field = field
        self.transitions: dict[str, frozenset[str]] = {
            src: frozenset(dests) for src, dests in transitions.items()
        }

    def allowed_from(self, state: str) -> frozenset[str]:
        return self.transitions.get(state, frozenset())

    def can_transition(self, obj: Any, *, to: str) -> bool:
        return to in self.allowed_from(getattr(obj, self.field))

    def transition(self, obj: Any, *, to: str, save: bool = True) -> None:
        current = getattr(obj, self.field)
        if to not in self.allowed_from(current):
            raise InvalidTransition(
                f"Cannot transition {type(obj).__name__}.{self.field} from {current!r} to {to!r}",
                details={
                    "model": type(obj).__name__,
                    "field": self.field,
                    "from": current,
                    "to": to,
                    "allowed": sorted(self.allowed_from(current)),
                },
            )
        setattr(obj, self.field, to)
        if save:
            fields = [self.field]
            if hasattr(obj, "updated_at"):
                fields.append("updated_at")
            obj.save(update_fields=fields)
