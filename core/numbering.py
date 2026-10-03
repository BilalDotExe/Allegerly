"""Sequential document codes (INV-000001, CN-000001, …) generated under a row lock."""

from django.db import transaction


def next_sequential_code(queryset, field_name, prefix, width=6) -> str:
    """
    Return the next zero-padded code for this prefix.

    Must be called inside transaction.atomic(). select_for_update()
    serialises concurrent issuers so two invoices cannot share a number.
    """
    last = (
        queryset.select_for_update()
        .filter(**{f'{field_name}__startswith': prefix})
        .order_by(f'-{field_name}')
        .values_list(field_name, flat=True)
        .first()
    )
    n = 1
    if last:
        suffix = last[len(prefix):]
        try:
            n = int(suffix) + 1
        except ValueError:
            n = 1
    return f'{prefix}{n:0{width}d}'
