from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter(name="usd")
def usd(value):
    """Render a money amount as $1,234.50.

    Templates used to print `${{ value }}`, which gave `$1234.5` — no thousands
    separator and a ragged number of decimals. USD is the only currency this app
    handles, so the symbol is hardcoded on purpose.
    """
    if value is None or value == "":
        return "—"
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return value
    sign = "-" if amount < 0 else ""
    return f"{sign}${abs(amount):,.2f}"
