"""Unit — Money value object + decimal helpers."""

from decimal import Decimal

import pytest

from common.money.decimal import quantize, to_decimal
from common.money.money import CurrencyMismatch, Money


class TestDecimalHelpers:
    def test_quantize_rounds_to_2dp_banker(self):
        # banker's rounding: .5 → nearest even
        assert quantize(Decimal("2.125")) == Decimal("2.12")
        assert quantize(Decimal("2.135")) == Decimal("2.14")

    def test_to_decimal_from_float_avoids_drift(self):
        assert to_decimal(0.1) == Decimal("0.10")

    def test_to_decimal_from_string(self):
        assert to_decimal("100.005") == Decimal("100.00")  # banker's round


class TestMoney:
    def test_amount_quantized(self):
        m = Money.from_decimal("10.999", "USD")
        assert m.amount == Decimal("11.00")

    def test_currency_uppercased(self):
        assert Money.from_decimal(5, "usd").currency == "USD"

    def test_add(self):
        a = Money.from_decimal("10.00", "USD")
        b = Money.from_decimal("2.50", "USD")
        assert (a + b).amount == Decimal("12.50")

    def test_sub(self):
        a = Money.from_decimal("10.00", "USD")
        b = Money.from_decimal("2.50", "USD")
        assert (a - b).amount == Decimal("7.50")

    def test_mul_by_decimal(self):
        a = Money.from_decimal("10.00", "USD")
        assert (a * Decimal("0.10")).amount == Decimal("1.00")

    def test_mul_by_float_rejected(self):
        with pytest.raises(TypeError):
            Money.from_decimal("10.00", "USD") * 0.1

    def test_currency_mismatch_blocks_arithmetic(self):
        a = Money.from_decimal("10.00", "USD")
        b = Money.from_decimal("10.00", "ETB")
        with pytest.raises(CurrencyMismatch):
            _ = a + b

    def test_negation(self):
        m = -Money.from_decimal("5.00", "USD")
        assert m.amount == Decimal("-5.00")

    def test_serialization(self):
        m = Money.from_decimal("12.34", "USD")
        assert m.to_dict() == {"amount": "12.34", "currency": "USD"}

    def test_immutable(self):
        m = Money.from_decimal("1.00", "USD")
        with pytest.raises(Exception):
            m.amount = Decimal("999")  # type: ignore[misc]

    def test_zero(self):
        assert Money.zero("USD").is_zero()
