from django.db import models
from django.conf import settings


class DamageReport(models.Model):
    """
    Logs an item damaged (in transit or in warehouse).
    Always deducts from stock. Optionally references an invoice line
    for traceability only, it does not drive any calculation.
    No credit note is created here, replacements are handled manually
    via a new invoice.
    """

    item = models.ForeignKey(
        'inventory.Item',
        on_delete=models.PROTECT,
        related_name='damage_reports'
    )
    invoice_line = models.ForeignKey(
        'invoices.InvoiceLine',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='damage_records',
        help_text="Optional, for reference only"
    )
    quantity = models.PositiveIntegerField()
    date_reported = models.DateField()
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def loss_value(self):
        return self.quantity * self.item.cost_price

    def __str__(self):
        return f"Damage: {self.item.sku} x{self.quantity} on {self.date_reported}"