"""Escrow value objects (placeholder — expanded as the domain grows)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ReleaseAmounts:
    total: Decimal
    commission: Decimal
    freelancer: Decimal
