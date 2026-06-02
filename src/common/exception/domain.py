"""
Domain exceptions — raised by services to signal a business-rule violation.

These are NOT DRF exceptions. The custom DRF handler in `common.exception.handler`
maps them to a consistent JSON envelope: `{code, message, details}`.

Refs: ARCHITECTURE_AUDIT.md §6, §13
"""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Base class for business-rule violations."""

    code: str = "domain_error"
    http_status: int = 400

    def __init__(self, message: str = "", *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message or self.code)
        self.message = message or self.code
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


class InsufficientFunds(DomainError):
    code = "insufficient_funds"
    http_status = 422


class InvalidTransition(DomainError):
    code = "invalid_transition"
    http_status = 409


class IdempotencyConflict(DomainError):
    code = "idempotency_conflict"
    http_status = 409


class ProviderError(DomainError):
    code = "provider_error"
    http_status = 502
