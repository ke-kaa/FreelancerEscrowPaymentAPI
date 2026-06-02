"""
Decimal helpers for financial math.

All currency amounts use `Decimal` quantized to 2 fractional digits with
ROUND_HALF_EVEN (banker's rounding) to avoid systemic rounding bias.

Refs: ARCHITECTURE_AUDIT.md §8
"""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal

CENTS = Decimal("0.01")


def quantize(value: Decimal) -> Decimal:
    return value.quantize(CENTS, rounding=ROUND_HALF_EVEN)


def to_decimal(value: int | float | str | Decimal) -> Decimal:
    """Coerce to a quantized Decimal. Floats go through str() to avoid drift."""
    if isinstance(value, Decimal):
        return quantize(value)
    if isinstance(value, float):
        return quantize(Decimal(str(value)))
    return quantize(Decimal(value))
