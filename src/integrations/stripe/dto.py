"""Stripe-specific raw response wrappers (kept thin; main DTOs live in common.patterns.ports)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class StripeIntent:
    id: str
    status: str
    client_secret: str | None
    raw: dict[str, Any]
