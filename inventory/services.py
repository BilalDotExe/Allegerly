"""Stock primitives. Higher-level flows (issue, damage, …) call these inside atomic()."""

from django.contrib.contenttypes.models import ContentType

from inventory.models import StockMovement


def create_stock_movement(*, item, movement_type, quantity, user, note='', source=None):
    content_type = None
    object_id = None
    if source is not None:
        content_type = ContentType.objects.get_for_model(source, for_concrete_model=False)
        object_id = source.pk
    return StockMovement.objects.create(
        item=item,
        movement_type=movement_type,
        quantity=quantity,
        note=note or '',
        created_by=user,
        content_type=content_type,
        object_id=object_id,
    )
