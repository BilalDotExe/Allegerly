from django.db import transaction
from django.core.exceptions import ValidationError
from .models import DamageReport


@transaction.atomic
def log_damage(item, quantity, date_reported, created_by, invoice_line=None, note=''):
    if quantity <= 0:
        raise ValidationError("Damage quantity must be positive.")

    if invoice_line is not None:
        already_accounted = invoice_line.returned_qty + invoice_line.damaged_qty
        if already_accounted + quantity > invoice_line.quantity:
            raise ValidationError(
                "Damage quantity exceeds remaining unaccounted quantity on this invoice line."
            )

    if item.current_stock() < quantity:
        raise ValidationError("Not enough stock to log this damage.")

    report = DamageReport.objects.create(
        item=item,
        invoice_line=invoice_line,
        quantity=quantity,
        date_reported=date_reported,
        note=note,
        created_by=created_by,
    )

    from inventory.services import create_stock_movement
    create_stock_movement(
        item=item,
        movement_type='damaged',
        quantity=-quantity,
        note=f"Damage report #{report.id}" + (f" ({note})" if note else ""),
        created_by=created_by,
        source=report,
    )

    return report