from django.db import transaction
from django.core.exceptions import ValidationError
from .models import ProductionBatch


@transaction.atomic
def create_production_batch(item, quantity_produced, production_date, created_by, expiry_date=None, note=''):
    if quantity_produced <= 0:
        raise ValidationError("Quantity produced must be positive.")

    last_batch = ProductionBatch.objects.order_by('-id').first()
    next_number = (last_batch.id + 1) if last_batch else 1
    batch_code = f"BATCH-{next_number:06d}"

    batch = ProductionBatch.objects.create(
        item=item,
        batch_code=batch_code,
        quantity_produced=quantity_produced,
        production_date=production_date,
        expiry_date=expiry_date,
        note=note,
        created_by=created_by,
    )

    from inventory.services import create_stock_movement
    create_stock_movement(
        item=item,
        movement_type='production',
        quantity=quantity_produced,
        note=f"Production batch {batch_code}",
        created_by=created_by,
        source=batch,
    )

    return batch