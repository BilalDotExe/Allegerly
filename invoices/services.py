from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Invoice, Payment
from audit.services import log as audit_log


@transaction.atomic
def issue_invoice(invoice: Invoice, user, request=None):
    if invoice.status != 'draft':
        raise ValidationError("Only draft invoices can be issued.")
    if not invoice.lines.exists():
        raise ValidationError("Cannot issue an invoice with no lines.")

    for line in invoice.lines.all():
        if line.item.current_stock() < line.quantity:
            raise ValidationError(f"Not enough stock for {line.item.name}.")

    invoice.status = 'issued'
    invoice.save(update_fields=['status'])
    audit_log(user, 'invoice_issued', invoice, request=request)

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
    # Auto-mark as paid if total is zero
    if invoice.total == 0:
        invoice.status = 'paid'
        invoice.save(update_fields=['status'])
        audit_log(user, 'invoice_paid', invoice, request=request)
    return invoice


@transaction.atomic
def void_invoice(invoice: Invoice, user, reason: str, request=None):
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
    audit_log(user, 'invoice_voided', invoice, changes={'reason': reason}, request=request)
    return invoice


@transaction.atomic
def apply_credit(credit_note, invoice, amount, user, request=None):
    from .models import CreditApplication
    if invoice.status not in ('issued', 'paid'):
        raise ValidationError("Credit can only be applied to issued or paid invoices.")
    if credit_note.customer != invoice.customer:
        raise ValidationError("Credit note and invoice must belong to the same customer.")
    if credit_note.is_refunded:
        raise ValidationError("Cannot apply a refunded credit note.")
    if credit_note.is_applied:
        raise ValidationError("This credit note has no remaining balance.")
    if amount <= 0:
        raise ValidationError("Amount must be positive.")
    if amount > credit_note.remaining_amount:
        raise ValidationError("Amount exceeds credit note remaining balance.")
    if amount > invoice.balance_due:
        raise ValidationError("Amount exceeds invoice balance due.")

    CreditApplication.objects.create(
        credit_note=credit_note,
        invoice=invoice,
        amount=amount,
        created_by=user,
    )

    credit_note.remaining_amount -= amount
    credit_note.save()
    audit_log(user, 'credit_applied', credit_note, changes={'amount': str(amount), 'invoice': invoice.invoice_number}, request=request)

@transaction.atomic
def record_payment(invoice: Invoice, amount, method: str, payment_date, user, note: str = '', request=None):
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

    audit_log(user, 'payment_recorded', payment, changes={'amount': str(amount), 'method': method}, request=request)

    if invoice.balance_due <= 0:
        invoice.status = 'paid'
        invoice.save(update_fields=['status'])
        audit_log(user, 'invoice_paid', invoice, request=request)

    return payment
