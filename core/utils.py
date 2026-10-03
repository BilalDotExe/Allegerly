from django.utils import timezone
from datetime import timedelta
from production.models import ProductionBatch


def get_expiring_batches(days=30):
    cutoff = timezone.now().date() + timedelta(days=days)
    return ProductionBatch.objects.filter(
        expiry_date__isnull=False,
        expiry_date__lte=cutoff
    ).order_by('expiry_date')