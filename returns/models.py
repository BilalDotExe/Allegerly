from django.conf import settings
from django.db import models


class ReturnRecord(models.Model):
    """
    Source of a customer-return credit note (one-to-one from CreditNote).

    The return *service* (stock + credit note creation) is Phase 3.
    The row exists now so InvoiceLine.returned_qty and CreditNote can link.
    """

    invoice_line = models.ForeignKey(
        'invoices.InvoiceLine',
        on_delete=models.PROTECT,
        related_name='return_records',
    )
    quantity = models.PositiveIntegerField()
    date_returned = models.DateField()
    is_restockable = models.BooleanField(default=True)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Return {self.quantity} of {self.invoice_line}'
