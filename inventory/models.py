from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum


class Item(models.Model):
    sku = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2)
    sale_price = models.DecimalField(max_digits=10, decimal_places=2)
    reorder_level = models.PositiveIntegerField(default=10)
    has_expiry = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def current_stock(self):
        result = self.movements.aggregate(total=Sum('quantity'))
        return result['total'] or 0

    def is_low_stock(self):
        return self.current_stock() <= self.reorder_level

    def __str__(self):
        return f'{self.sku} - {self.name}'


# sale/damage/expired take stock out; purchase/return/production put stock in.
# adjustment is signed either way (manual or void reversal).
NEGATIVE_MOVEMENT_TYPES = frozenset({'sale', 'damage', 'expired'})
POSITIVE_MOVEMENT_TYPES = frozenset({'purchase', 'return', 'production'})


class StockMovementQuerySet(models.QuerySet):
    def delete(self):
        raise ValidationError('Stock movements are append-only and cannot be deleted.')


class StockMovement(models.Model):
    MOVEMENT_TYPES = [
        ('purchase', 'Purchase'),
        ('sale', 'Sale'),
        ('damage', 'Damage Write-off'),
        ('return', 'Return Restock'),
        ('expired', 'Expired Write-off'),
        ('adjustment', 'Manual Adjustment'),
        ('production', 'Production'),
    ]

    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name='movements')
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    quantity = models.IntegerField(help_text='Positive for stock in, negative for stock out')
    note = models.CharField(max_length=255, blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    # Optional pointer to the document that caused this row (invoice, later damage, etc.)
    content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, null=True, blank=True
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    source = GenericForeignKey('content_type', 'object_id')

    objects = StockMovementQuerySet.as_manager()

    class Meta:
        ordering = ['created_at', 'id']

    def clean(self):
        if self.quantity == 0:
            raise ValidationError('Stock movement quantity cannot be zero.')
        if self.movement_type in NEGATIVE_MOVEMENT_TYPES and self.quantity > 0:
            raise ValidationError(f'{self.movement_type} movements must have a negative quantity.')
        if self.movement_type in POSITIVE_MOVEMENT_TYPES and self.quantity < 0:
            raise ValidationError(f'{self.movement_type} movements must have a positive quantity.')

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError('Stock movements are append-only and cannot be updated.')
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Stock movements are append-only and cannot be deleted.')

    def __str__(self):
        return f'{self.item.sku} | {self.movement_type} | {self.quantity}'
