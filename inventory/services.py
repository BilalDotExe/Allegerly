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

@transaction.atomic
def log_expiry(item, quantity, date_noticed, created_by, note=''):
    if quantity <= 0:
        raise ValueError("Expiry quantity must be positive.")
    if item.current_stock() < quantity:
        raise ValueError("Not enough stock to write off this quantity.")

    from .models import ExpiryWriteOff
    writeoff = ExpiryWriteOff.objects.create(
        item=item,
        quantity=quantity,
        date_noticed=date_noticed,
        note=note,
        created_by=created_by,
    )

    create_stock_movement(
        item=item,
        movement_type='expired',
        quantity=-quantity,
        note=f"Expiry write-off #{writeoff.id}",
        created_by=created_by,
        source=writeoff,
    )
    return writeoff


@transaction.atomic
def adjust_stock(item, quantity, reason, created_by):
    if quantity == 0:
        raise ValueError("Adjustment quantity cannot be zero.")
    if not reason:
        raise ValueError("A reason is required for manual stock adjustments.")

    return create_stock_movement(
        item=item,
        movement_type='adjustment',
        quantity=quantity,
        note=reason,
        created_by=created_by,
    )