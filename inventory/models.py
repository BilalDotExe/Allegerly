from django.db import models

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
        from django.db.models import Sum
        result = self.movements.aggregate(total=Sum('quantity'))
        return result['total'] or 0

    def is_low_stock(self):
        return self.current_stock() <= self.reorder_level

    def __str__(self):
        return f"{self.sku} - {self.name}"


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
    quantity = models.IntegerField(help_text="Positive for stock in, negative for stock out")
    note = models.CharField(max_length=255, blank=True, null=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.item.sku} | {self.movement_type} | {self.quantity}"