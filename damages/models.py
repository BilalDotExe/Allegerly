from django.db import models
from django.conf import settings


class DamageReport(models.Model):
    """
    Logs an item damaged (in transit or in warehouse). A record only: it does
    not touch stock by itself, since the item may already be out of stock
    (sold on an invoice) or still sitting in inventory depending on when the
    damage happened. Stock is only ever moved by an explicit Stock Adjustment,
    which this can optionally be linked to for traceability once reconciled.

    Optionally references an invoice line for traceability and, if the
    customer paid for a damaged item, to issue a credit note for it.
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
    stock_movement = models.OneToOneField(
        'inventory.StockMovement',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='damage_report',
        help_text="Set once this damage has been reconciled with a manual stock adjustment.",
    )
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