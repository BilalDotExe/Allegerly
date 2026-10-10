from businesses.db import atomic
from django.core.exceptions import ValidationError
from .models import DamageReport
from audit.services import log as audit_log


@atomic
def log_damage(
    item, quantity, date_reported, created_by, invoice_line=None, note='', request=None,
    issue_credit=False, resolution='apply', refund_method=None,
):
    """Record a damage report. Does not touch stock — see the module docstring.

    If issue_credit is set (only meaningful with an invoice_line), also issues
    a credit note for the damaged quantity, same as a non-restockable return:
    the customer paid for items that arrived damaged, so they get a credit
    for that portion instead of a physical return.
    """
    if quantity <= 0:
        raise ValidationError("Damage quantity must be positive.")

    if invoice_line is not None:
        already_accounted = invoice_line.returned_qty + invoice_line.damaged_qty
        if already_accounted + quantity > invoice_line.quantity:
            raise ValidationError(
                "Damage quantity exceeds remaining unaccounted quantity on this invoice line."
            )
    elif issue_credit:
        raise ValidationError("An invoice line is required to issue a credit note.")

    report = DamageReport.objects.create(
        item=item,
        invoice_line=invoice_line,
        quantity=quantity,
        date_reported=date_reported,
        note=note,
        created_by=created_by,
    )

    credit_note = None
    if issue_credit and invoice_line is not None:
        from invoices.models import CreditNote
        amount = invoice_line.credit_amount_for(quantity)
        credit_note = CreditNote.objects.create(
            customer=invoice_line.invoice.customer,
            invoice=invoice_line.invoice,
            damage_report=report,
            reason=f"Damaged item: {invoice_line.item.name} x{quantity}",
            amount=amount,
            remaining_amount=amount,
            note=note,
            created_by=created_by,
        )
        audit_log(
            created_by, 'credit_issued', credit_note,
            changes={'amount': str(amount), 'source': f"damage report #{report.pk}"},
            request=request,
        )
        if resolution == "refund" and refund_method:
            credit_note.is_refunded = True
            credit_note.refund_method = refund_method
            credit_note.refund_date = date_reported
            credit_note.save()
            audit_log(
                created_by, 'credit_refunded', credit_note,
                changes={'method': refund_method, 'amount': str(amount)}, request=request,
            )

    audit_log(created_by, 'damage_logged', report, request=request)

    return report, credit_note
