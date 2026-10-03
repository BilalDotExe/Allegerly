from django.db import transaction
from .models import StockMovement


@transaction.atomic
def create_stock_movement(item, movement_type, quantity, note, created_by, source=None):
    if movement_type in ('sale', 'damaged', 'expired') and quantity > 0:
        raise ValueError(f"{movement_type} movements must be negative.")
    if movement_type in ('purchase', 'production', 'return') and quantity < 0:
        raise ValueError(f"{movement_type} movements must be positive.")

    movement = StockMovement(
        item=item,
        movement_type=movement_type,
        quantity=quantity,
        note=note,
        created_by=created_by,
    )
    if source is not None:
        from django.contrib.contenttypes.models import ContentType
        movement.content_type = ContentType.objects.get_for_model(source)
        movement.object_id = source.pk

    movement.full_clean()
    movement.save()
    return movement