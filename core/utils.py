import re
import secrets
import string

from django.utils import timezone
from datetime import timedelta
from production.models import ProductionBatch


def format_us_phone(value):
    """
    Format a US phone number for display: (555) 123-4567.
    A leading country code 1 (11 digits) is dropped. Anything that isn't a
    plain 10/11-digit US number (extensions, foreign numbers, partial input)
    is returned unchanged rather than mangled.
    """
    if not value:
        return value
    digits = re.sub(r"\D", "", str(value))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[0:3]}) {digits[3:6]}-{digits[6:10]}"
    return value


def generate_temp_password(length=8):
    """An 8-character alphanumeric password with upper, lower and digit chars.

    One char is drawn from each required category first (so Django's
    NumericPasswordValidator never sees an all-digit result and the "upper and
    lower case" requirement always holds), then the rest is filled randomly
    and shuffled so the fixed categories aren't always in the same position.
    Uses `secrets`, not `random` — this is a credential, not a UI value.
    """
    if length < 3:
        raise ValueError("need at least 3 characters for upper+lower+digit")
    categories = (string.ascii_uppercase, string.ascii_lowercase, string.digits)
    chars = [secrets.choice(pool) for pool in categories]
    pool = string.ascii_uppercase + string.ascii_lowercase + string.digits
    chars += [secrets.choice(pool) for _ in range(length - len(chars))]
    for i in range(len(chars) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        chars[i], chars[j] = chars[j], chars[i]
    return "".join(chars)


def get_expiring_batches(days=30):
    today = timezone.now().date()
    cutoff = today + timedelta(days=days)
    return ProductionBatch.objects.filter(
        expiry_date__isnull=False,
        expiry_date__gte=today,
        expiry_date__lte=cutoff
    ).order_by('expiry_date')
