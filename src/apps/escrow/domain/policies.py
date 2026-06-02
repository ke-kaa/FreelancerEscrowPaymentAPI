"""Escrow business policies — pure functions, no DB."""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings


def commission_rate() -> Decimal:
    """Platform commission rate as Decimal."""
    return Decimal(str(settings.PLATFORM_COMMISSION_RATE))


def commission_on(amount: Decimal) -> Decimal:
    """Commission deducted from a given release amount."""
    return (amount * commission_rate()).quantize(Decimal("0.01"))


def freelancer_payout(amount: Decimal) -> Decimal:
    """Net payout to the freelancer after commission."""
    return (amount - commission_on(amount)).quantize(Decimal("0.01"))


def resolve_release_status(remaining_balance: Decimal) -> str:
    """Status to set on successful release confirmation."""
    return "released" if remaining_balance == 0 else "partially_released"
