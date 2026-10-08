from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Sum, Value
from django.db.models.functions import Coalesce

from core.money import money
from core.numbering import next_sequential_code
from invoices.models import Payment
from vendors.models import Vendor

_LINE_TOTAL = ExpressionWrapper(
    F('quantity') * F('unit_cost'),
    output_field=DecimalField(max_digits=14, decimal_places=2),
)
_ZERO = Value(Decimal('0.00'), output_field=DecimalField(max_digits=14, decimal_places=2))

# Receiving state only. Whether the vendor has been paid is tracked separately
# (payment_status) because payment can happen before, during or after delivery.
_ALLOWED_STATUS_TRANSITIONS = {
    'draft': frozenset({'ordered', 'cancelled'}),
    'ordered': frozenset({'partial', 'received', 'cancelled'}),
    'partial': frozenset({'received'}),
    'received': frozenset(),
    'cancelled': frozenset(),
}

EDITABLE_STATUSES = ('draft', 'ordered', 'partial')

# Vendor and number are fixed once the order leaves draft.
_LOCKED_AFTER_DRAFT = ('vendor_id', 'po_number', 'created_by_id')


class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('ordered', 'Ordered'),
        ('partial', 'Partially received'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled'),
    ]

    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name='purchase_orders')
    po_number = models.CharField(max_length=50, unique=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    order_date = models.DateField()
    expected_date = models.DateField('Expected delivery', null=True, blank=True)
    vendor_reference = models.CharField(
        'Vendor reference', max_length=100, blank=True,
        help_text="The vendor's own invoice or order number, if they gave you one.",
    )
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    shipping_cost = models.DecimalField(
        'Shipping / other charges', max_digits=10, decimal_places=2, default=Decimal('0.00'),
    )
    notes = models.TextField(blank=True, null=True)
    cancel_reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', 'id']

    def clean(self):
        errors = {}
        if self.tax_percent is not None and self.tax_percent < 0:
            errors['tax_percent'] = 'Tax percent cannot be negative.'
        if self.shipping_cost is not None and self.shipping_cost < 0:
            errors['shipping_cost'] = 'Shipping cannot be negative.'
        if self.order_date and self.expected_date and self.expected_date < self.order_date:
            errors['expected_date'] = 'Expected delivery cannot be before the order date.'
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        creating = self.pk is None
        if creating and not self.po_number:
            with transaction.atomic():
                self.po_number = next_sequential_code(PurchaseOrder.objects, 'po_number', 'PO-')
                self.full_clean()
                super().save(*args, **kwargs)
            return

        if not creating:
            original = PurchaseOrder.objects.get(pk=self.pk)
            if original.status in ('received', 'cancelled'):
                for field in ('vendor_id', 'po_number', 'order_date', 'expected_date', 'vendor_reference',
                              'tax_percent', 'shipping_cost', 'notes', 'created_by_id'):
                    if getattr(self, field) != getattr(original, field):
                        raise ValidationError(f'A {original.status} purchase order cannot be edited.')
            if original.status != 'draft':
                for field in _LOCKED_AFTER_DRAFT:
                    if getattr(self, field) != getattr(original, field):
                        raise ValidationError('The vendor cannot be changed once the order has been placed.')
            if self.status != original.status:
                allowed = _ALLOWED_STATUS_TRANSITIONS.get(original.status, frozenset())
                if self.status not in allowed:
                    raise ValidationError(
                        f'Cannot change purchase order status from {original.status} to {self.status}.'
                    )

        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Purchase orders cannot be deleted. Cancel them instead.')

    @property
    def is_editable(self):
        return self.status in EDITABLE_STATUSES

    @property
    def can_receive(self):
        return self.status in ('ordered', 'partial')

    @property
    def subtotal(self):
        total = self.lines.aggregate(total=Coalesce(Sum(_LINE_TOTAL), _ZERO))['total']
        return money(total)

    @property
    def tax_amount(self):
        return money(self.subtotal * (self.tax_percent or Decimal('0')) / Decimal('100'))

    @property
    def total(self):
        return money(self.subtotal + self.tax_amount + (self.shipping_cost or Decimal('0')))

    @property
    def total_paid(self):
        total = self.payments.aggregate(total=Coalesce(Sum('amount'), _ZERO))['total']
        return money(total)

    @property
    def balance_due(self):
        return money(self.total - self.total_paid)

    @property
    def payment_status(self):
        if self.total_paid == 0 and self.total > 0:
            return 'unpaid'
        return 'paid' if self.balance_due <= 0 else 'partial'

    @property
    def payment_status_display(self):
        return {'unpaid': 'Unpaid', 'partial': 'Partly paid', 'paid': 'Paid'}[self.payment_status]

    @property
    def qty_ordered(self):
        return self.lines.aggregate(total=Sum('quantity'))['total'] or 0

    @property
    def qty_received(self):
        return GoodsReceiptLine.objects.filter(po_line__purchase_order=self).aggregate(
            total=Sum('quantity'))['total'] or 0

    def __str__(self):
        return f'{self.po_number} - {self.vendor.name}'


class PurchaseOrderLine(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='lines')
    item_name = models.CharField(
        'Item name', max_length=200,
        help_text='What you are buying. Free text - purchases are not limited to things you resell.',
    )
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_cost = models.DecimalField(
        'Buying price', max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0'))],
    )

    @property
    def line_total(self):
        return money(self.quantity * self.unit_cost)

    @property
    def received_qty(self):
        if not self.pk:
            return 0
        return self.receipt_lines.aggregate(total=Sum('quantity'))['total'] or 0

    @property
    def outstanding_qty(self):
        return max(self.quantity - self.received_qty, 0)

    def clean(self):
        if self.pk and self.quantity is not None and self.quantity < self.received_qty:
            raise ValidationError(
                {'quantity': f'{self.received_qty} already received - quantity cannot go lower.'}
            )

    def save(self, *args, **kwargs):
        if not self.purchase_order.is_editable:
            raise ValidationError(f'A {self.purchase_order.status} purchase order cannot be edited.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if not self.purchase_order.is_editable:
            raise ValidationError(f'A {self.purchase_order.status} purchase order cannot be edited.')
        if self.received_qty:
            raise ValidationError('A line that has been received cannot be removed.')
        super().delete(*args, **kwargs)

    def __str__(self):
        return f'{self.purchase_order.po_number} | {self.item_name} x{self.quantity}'


class GoodsReceipt(models.Model):
    """One delivery against a purchase order. Append-only, like stock movements."""

    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name='receipts')
    receipt_number = models.CharField(max_length=50, unique=True, blank=True)
    received_date = models.DateField()
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', 'id']

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError('Goods receipts cannot be edited.')
        with transaction.atomic():
            self.receipt_number = next_sequential_code(GoodsReceipt.objects, 'receipt_number', 'GR-')
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Goods receipts cannot be deleted.')

    @property
    def total_value(self):
        return money(sum((line.line_total for line in self.lines.all()), Decimal('0')))

    def __str__(self):
        return f'{self.receipt_number} for {self.purchase_order.po_number}'


class GoodsReceiptLine(models.Model):
    receipt = models.ForeignKey(GoodsReceipt, on_delete=models.CASCADE, related_name='lines')
    po_line = models.ForeignKey(PurchaseOrderLine, on_delete=models.PROTECT, related_name='receipt_lines')
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def line_total(self):
        return money(self.quantity * self.unit_cost)

    def __str__(self):
        return f'{self.receipt.receipt_number} | {self.po_line.item_name} x{self.quantity}'


class PurchasePayment(models.Model):
    PAYMENT_METHODS = Payment.PAYMENT_METHODS

    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    payment_date = models.DateField()
    reference = models.CharField(
        max_length=100, blank=True, help_text='Cheque number or bank transfer reference.',
    )
    note = models.CharField(max_length=255, blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='purchase_payments_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['payment_date', 'id']

    def save(self, *args, **kwargs):
        if self.amount is not None:
            self.amount = money(self.amount)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Payments cannot be deleted.')

    def __str__(self):
        return f'Payment ${self.amount} on {self.purchase_order.po_number}'
