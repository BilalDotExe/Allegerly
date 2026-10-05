from .models import AuditLog


def log(user, action, obj=None, changes=None, request=None):
    ip_address = None
    if request is not None:
        ip_address = request.META.get('REMOTE_ADDR')

    AuditLog.objects.create(
        user=user,
        action=action,
        object_type=obj.__class__.__name__ if obj else '',
        object_id=str(obj.pk) if obj else None,
        object_repr=str(obj) if obj else '',
        changes=changes,
        ip_address=ip_address,
    )