from django.db import models
from customers.models import Customer
from inventory.models import Item, StockMovement


class Invoice(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('issued', 'Issued'),
        ('paid', 'Paid'),
        ('voided', 'Voided'),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='invoices')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    invoice_number = models.CharField(max_length=50, unique=True)
    issue_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def total(self):
        return sum(line.line_total for line in self.lines.all())

    @property
    def total_paid(self):
        return sum(p.amount for p in self.payments.all())

    @property
    def balance_due(self):
        return self.total - self.total_paid

    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.customer.name}"


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='lines')
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name='invoice_lines')
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    has_return = models.BooleanField(default=False)
    has_damage = models.BooleanField(default=False)

    @property
    def line_total(self):
        return self.quantity * self.unit_price

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
    created_by = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment ${self.amount} on {self.invoice.invoice_number}"


class CreditNote(models.Model):
    REASON_CHOICES = [
        ('damage', 'Damaged Goods'),
        ('return', 'Customer Return'),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='credit_notes')
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='credit_notes')
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    remaining_amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_applied = models.BooleanField(default=False)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Credit Note ${self.amount} for {self.customer.name}"