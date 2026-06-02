"""
Money — value object pairing a Decimal amount with a currency.

Forbids implicit cross-currency arithmetic. Amounts quantized to 2dp.

Refs: ARCHITECTURE_AUDIT.md §8
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Self

from common.money.decimal import quantize, to_decimal


class CurrencyMismatch(ValueError):
    """Raised when arithmetic is attempted across two different currencies."""


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", quantize(self.amount))
        object.__setattr__(self, "currency", self.currency.upper())

    @classmethod
    def from_decimal(cls, value: int | float | str | Decimal, currency: str) -> Self:
        return cls(amount=to_decimal(value), currency=currency)

    @classmethod
    def zero(cls, currency: str) -> Self:
        return cls(amount=Decimal("0.00"), currency=currency)

    def _check(self, other: Money) -> None:
        if self.currency != other.currency:
            raise CurrencyMismatch(f"{self.currency} vs {other.currency}")

    def __add__(self, other: Money) -> Money:
        self._check(other)
        return Money(amount=self.amount + other.amount, currency=self.currency)

    def __sub__(self, other: Money) -> Money:
        self._check(other)
        return Money(amount=self.amount - other.amount, currency=self.currency)

    def __mul__(self, scalar: int | Decimal) -> Money:
        if isinstance(scalar, float):
            raise TypeError("Use Decimal for Money multiplication, not float.")
        return Money(amount=self.amount * Decimal(scalar), currency=self.currency)

    def __neg__(self) -> Money:
        return Money(amount=-self.amount, currency=self.currency)

    def __lt__(self, other: Money) -> bool:
        self._check(other)
        return self.amount < other.amount

    def __le__(self, other: Money) -> bool:
        self._check(other)
        return self.amount <= other.amount

    def is_positive(self) -> bool:
        return self.amount > 0

    def is_zero(self) -> bool:
        return self.amount == 0

    def to_dict(self) -> dict[str, str]:
        return {"amount": str(self.amount), "currency": self.currency}

    def __str__(self) -> str:
        return f"{self.amount} {self.currency}"
