from django.db import models
from django.conf import settings


class ReturnRecord(models.Model):
    """
    A normal customer return. Always tied to an invoice line.
    Creates a credit note. Restocks only if marked restockable.
    """

    invoice_line = models.ForeignKey(
        'invoices.InvoiceLine',
        on_delete=models.PROTECT,
        related_name='return_records'
    )
    quantity = models.PositiveIntegerField()
    date_returned = models.DateField()
    is_restockable = models.BooleanField(default=True)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Return: {self.invoice_line.item.name} x{self.quantity} on {self.date_returned}"