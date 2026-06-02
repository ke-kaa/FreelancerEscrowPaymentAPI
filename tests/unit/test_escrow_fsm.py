"""Unit — escrow state machine guards."""

from dataclasses import dataclass

import pytest

from apps.escrow.domain.state_machine import ESCROW_FSM
from common.exception.domain import InvalidTransition


@dataclass
class FakeEscrow:
    status: str
    saved: bool = False

    def save(self, update_fields=None):
        self.saved = True


class TestEscrowFSM:
    def test_pending_to_funded(self):
        e = FakeEscrow(status="pending_funding")
        ESCROW_FSM.transition(e, to="funded", save=False)
        assert e.status == "funded"

    def test_funded_to_release_pending(self):
        e = FakeEscrow(status="funded")
        ESCROW_FSM.transition(e, to="release_pending", save=False)
        assert e.status == "release_pending"

    def test_release_pending_back_to_funded_on_failure(self):
        e = FakeEscrow(status="release_pending")
        ESCROW_FSM.transition(e, to="funded", save=False)
        assert e.status == "funded"

    def test_released_is_terminal(self):
        e = FakeEscrow(status="released")
        with pytest.raises(InvalidTransition):
            ESCROW_FSM.transition(e, to="funded", save=False)

    def test_pending_cannot_skip_to_released(self):
        e = FakeEscrow(status="pending_funding")
        with pytest.raises(InvalidTransition):
            ESCROW_FSM.transition(e, to="released", save=False)

    def test_funded_to_disputed_and_back(self):
        e = FakeEscrow(status="funded")
        ESCROW_FSM.transition(e, to="disputed", save=False)
        assert e.status == "disputed"
        ESCROW_FSM.transition(e, to="funded", save=False)
        assert e.status == "funded"
