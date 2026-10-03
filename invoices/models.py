from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Sum, Value
from django.db.models.functions import Coalesce

from core.money import money, zero_money
from customers.models import Customer
from inventory.models import Item


_LINE_TOTAL = ExpressionWrapper(
    F('quantity') * F('unit_price'),
    output_field=DecimalField(max_digits=14, decimal_places=2),
)

# After draft, only status may change (issue / pay / void / reopen after voiding a payment).
_LOCKED_INVOICE_FIELDS = (
    'customer_id',
    'invoice_number',
    'tax_percent',
    'issue_date',
    'due_date',
    'notes',
    'created_by_id',
)

_ALLOWED_STATUS_TRANSITIONS = {
    'draft': frozenset({'issued'}),
    'issued': frozenset({'paid', 'voided'}),
    'paid': frozenset({'issued', 'voided'}),
    'voided': frozenset(),
}


def _next_sequential_code(model, field, prefix):
    """
    INV-000001 / CN-000001. Must run inside transaction.atomic so
    select_for_update serialises two staff creating invoices at once.
    """
    last = (
        model.objects.select_for_update()
        .filter(**{f'{field}__startswith': prefix})
        .order_by(f'-{field}')
        .first()
    )
    n = 1
    if last:
        suffix = getattr(last, field).rsplit('-', 1)[-1]
        try:
            n = int(suffix) + 1
        except ValueError:
            n = 1
    return f'{prefix}{n:06d}'


class Invoice(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('issued', 'Issued'),
        ('paid', 'Paid'),
        ('voided', 'Voided'),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='invoices')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    invoice_number = models.CharField(max_length=50, unique=True, blank=True)
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    issue_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', 'id']

    def clean(self):
        if self.tax_percent is not None and self.tax_percent < 0:
            raise ValidationError({'tax_percent': 'Tax percent cannot be negative.'})

    def save(self, *args, **kwargs):
        creating = self.pk is None
        if creating and not self.invoice_number:
            with transaction.atomic():
                self.invoice_number = _next_sequential_code(Invoice, 'invoice_number', 'INV-')
                self.full_clean()
                super().save(*args, **kwargs)
            return

        if not creating:
            original = Invoice.objects.get(pk=self.pk)
            if original.status != 'draft':
                for field in _LOCKED_INVOICE_FIELDS:
                    if getattr(self, field) != getattr(original, field):
                        raise ValidationError(
                            'Issued invoices cannot be edited. Void the invoice to fix mistakes.'
                        )
            if self.status != original.status:
                allowed = _ALLOWED_STATUS_TRANSITIONS.get(original.status, frozenset())
                if self.status not in allowed:
                    raise ValidationError(
                        f'Cannot change invoice status from {original.status} to {self.status}.'
                    )

        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Invoices cannot be deleted. Void them instead.')

    @property
    def subtotal(self):
        total = self.lines.aggregate(total=Coalesce(Sum(_LINE_TOTAL), Value(0)))['total']
        return money(total)

    @property
    def tax_amount(self):
        return money(self.subtotal * (self.tax_percent or Decimal('0')) / Decimal('100'))

    @property
    def total(self):
        return money(self.subtotal + self.tax_amount)

    @property
    def total_paid(self):
        total = self.payments.filter(is_voided=False).aggregate(
            total=Coalesce(Sum('amount'), Value(0))
        )['total']
        return money(total)

    @property
    def total_credits_applied(self):
        total = self.credit_applications.aggregate(
            total=Coalesce(Sum('amount'), Value(0))
        )['total']
        return money(total)

    @property
    def balance_due(self):
        return money(self.total - self.total_paid - self.total_credits_applied)

    def __str__(self):
        return f'Invoice {self.invoice_number} - {self.customer.name}'

class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='lines')
    item = models.ForeignKey('inventory.Item', on_delete=models.PROTECT, related_name='invoice_lines')
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def line_total(self):
        return self.quantity * self.unit_price

    @property
    def returned_qty(self):
        from django.db.models import Sum
        result = self.return_records.aggregate(total=Sum('quantity'))
        return result['total'] or 0

    @property
    def damaged_qty(self):
        from django.db.models import Sum
        result = self.damage_records.aggregate(total=Sum('quantity'))
        return result['total'] or 0

    @property
    def available_qty(self):
        return self.quantity - self.returned_qty - self.damaged_qty

    def __str__(self):
        return f"{self.invoice.invoice_number} | {self.item.name} x{self.quantity}"


class Payment(models.Model):
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
    ]

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    payment_date = models.DateField()
    note = models.CharField(max_length=255, blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='payments_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_voided = models.BooleanField(default=False)
    void_reason = models.CharField(max_length=255, blank=True, null=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='payments_voided',
    )

    def save(self, *args, **kwargs):
        if self.amount is not None:
            self.amount = money(self.amount)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Payments cannot be deleted. Void them instead.')

    def __str__(self):
        return f'Payment ${self.amount} on {self.invoice.invoice_number}'


class CreditNote(models.Model):
    REFUND_METHODS = Payment.PAYMENT_METHODS

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='credit_notes')
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='credit_notes')
    return_record = models.OneToOneField(
        'returns.ReturnRecord',
        on_delete=models.PROTECT,
        related_name='credit_note',
        null=True,
        blank=True,
    )
    credit_number = models.CharField(max_length=50, unique=True, blank=True)
    reason = models.CharField(max_length=255, blank=True, null=True, help_text="Optional free-text reason")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    remaining_amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_applied = models.BooleanField(default=False)
    is_refunded = models.BooleanField(default=False)
    refund_method = models.CharField(max_length=20, choices=REFUND_METHODS, blank=True, null=True)
    refund_date = models.DateField(blank=True, null=True)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        if self.amount is not None:
            self.amount = money(self.amount)
        creating = self.pk is None
        if creating and self.remaining_amount in (None, ''):
            self.remaining_amount = self.amount
        elif self.remaining_amount is not None:
            self.remaining_amount = money(self.remaining_amount)
        self.is_applied = self.remaining_amount == zero_money()
        if creating and not self.credit_number:
            with transaction.atomic():
                self.credit_number = _next_sequential_code(CreditNote, 'credit_number', 'CN-')
                super().save(*args, **kwargs)
            return
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Credit notes cannot be deleted.')

    def __str__(self):
        return f'{self.credit_number} ${self.amount} for {self.customer.name}'


class CreditApplication(models.Model):
    credit_note = models.ForeignKey(
        CreditNote, on_delete=models.PROTECT, related_name='applications'
    )
    invoice = models.ForeignKey(
        Invoice, on_delete=models.PROTECT, related_name='credit_applications'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.amount is not None:
            self.amount = money(self.amount)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Credit applications cannot be deleted.')

    def __str__(self):
        return f'{self.amount} from {self.credit_note.credit_number} to {self.invoice.invoice_number}'
