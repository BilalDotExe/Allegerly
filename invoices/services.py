from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Invoice, Payment


@transaction.atomic
def issue_invoice(invoice: Invoice, user):
    if invoice.status != 'draft':
        raise ValidationError("Only draft invoices can be issued.")
    if not invoice.lines.exists():
        raise ValidationError("Cannot issue an invoice with no lines.")

    for line in invoice.lines.all():
        if line.item.current_stock() < line.quantity:
            raise ValidationError(f"Not enough stock for {line.item.name}.")

    invoice.status = 'issued'
    invoice.save(update_fields=['status'])

    from inventory.services import create_stock_movement
    for line in invoice.lines.all():
        create_stock_movement(
            item=line.item,
            movement_type='sale',
            quantity=-line.quantity,
            note=f"Sale via {invoice.invoice_number}",
            created_by=user,
            source=invoice,
        )
    return invoice


@transaction.atomic
def void_invoice(invoice: Invoice, user, reason: str):
    if invoice.status not in ('issued', 'paid'):
        raise ValidationError("Only issued or paid invoices can be voided.")

    from inventory.services import create_stock_movement
    for line in invoice.lines.all():
        create_stock_movement(
            item=line.item,
            movement_type='adjustment',
            quantity=line.quantity,
            note=f"Reversal: void of {invoice.invoice_number} ({reason})",
            created_by=user,
            source=invoice,
        )

    invoice.status = 'voided'
    invoice.save(update_fields=['status'])
    return invoice


@transaction.atomic
def record_payment(invoice: Invoice, amount, method: str, payment_date, user, note: str = ''):
    if invoice.status not in ('issued', 'paid'):
        raise ValidationError("Cannot record payment on a draft or voided invoice.")
    if amount <= 0:
        raise ValidationError("Payment amount must be positive.")
    if amount > invoice.balance_due:
        raise ValidationError("Payment exceeds invoice balance due.")

    payment = Payment.objects.create(
        invoice=invoice,
        amount=amount,
        method=method,
        payment_date=payment_date,
        note=note,
        created_by=user,
    )

    if invoice.balance_due <= 0:
        invoice.status = 'paid'
        invoice.save(update_fields=['status'])

    return payment