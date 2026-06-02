"""Unit — domain exceptions surface a stable envelope."""

from common.exception.domain import (
    DomainError,
    InsufficientFunds,
    InvalidTransition,
)


def test_domain_error_to_dict_minimal():
    err = DomainError("boom")
    assert err.to_dict() == {"code": "domain_error", "message": "boom", "details": {}}


def test_insufficient_funds_has_code_and_status():
    err = InsufficientFunds("balance 0")
    assert err.code == "insufficient_funds"
    assert err.http_status == 422


def test_invalid_transition_preserves_details():
    err = InvalidTransition("nope", details={"from": "pending", "to": "released"})
    payload = err.to_dict()
    assert payload["code"] == "invalid_transition"
    assert payload["details"]["from"] == "pending"
