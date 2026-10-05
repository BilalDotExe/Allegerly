from django.db import transaction
from django.core.exceptions import ValidationError
from .models import ReturnRecord
from audit.services import log as audit_log


@transaction.atomic
def log_return(
    invoice_line, quantity, date_returned, created_by, is_restockable=True,
    note='', request=None, resolution="apply", refund_method=None,
):
    if quantity <= 0:
        raise ValidationError("Return quantity must be positive.")

    already_accounted = invoice_line.returned_qty + invoice_line.damaged_qty
    if already_accounted + quantity > invoice_line.quantity:
        raise ValidationError(
            "Return quantity exceeds remaining unaccounted quantity on this invoice line."
        )

    record = ReturnRecord.objects.create(
        invoice_line=invoice_line,
        quantity=quantity,
        date_returned=date_returned,
        is_restockable=is_restockable,
        note=note,
        created_by=created_by,
    )

    from invoices.models import CreditNote
    credit_note = CreditNote.objects.create(
        customer=invoice_line.invoice.customer,
        invoice=invoice_line.invoice,
        return_record=record,
        reason=f"Customer return: {invoice_line.item.name} x{quantity}",
        amount=quantity * invoice_line.unit_price,
        remaining_amount=quantity * invoice_line.unit_price,
        note=f"Return of {invoice_line.item.name} x{quantity}",
        created_by=created_by,
    )

    if resolution == "refund" and refund_method:
        credit_note.is_refunded = True
        credit_note.refund_method = refund_method
        credit_note.refund_date = date_returned
        credit_note.save()

    if is_restockable:
        from inventory.services import create_stock_movement
        create_stock_movement(
            item=invoice_line.item,
            movement_type='return',
            quantity=quantity,
            note=f"Restock from return record #{record.id}",
            created_by=created_by,
            source=record,
        )

    audit_log(created_by, 'return_logged', record, request=request)

    return record, credit_note
