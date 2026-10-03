from django.db import models
from django.conf import settings


class ProductionBatch(models.Model):
    """
    Records a manufacturing run. Batch tracking exists only here,
    at production level. Sales, returns and damages are NOT linked
    to batches since boxes carry no batch labels.
    """

    item = models.ForeignKey(
        'inventory.Item',
        on_delete=models.PROTECT,
        related_name='production_batches'
    )
    batch_code = models.CharField(max_length=50, unique=True, blank=True)
    quantity_produced = models.PositiveIntegerField()
    production_date = models.DateField()
    expiry_date = models.DateField(blank=True, null=True)
    note = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.batch_code} - {self.item.name} x{self.quantity_produced}"