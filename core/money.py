"""Shared money helpers — always Decimal, never float."""

from decimal import Decimal, ROUND_HALF_UP

TWOPLACES = Decimal('0.01')


def money(value) -> Decimal:
    """Round any numeric value to 2 decimal places (USD cents)."""
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def zero_money() -> Decimal:
    return Decimal('0.00')
