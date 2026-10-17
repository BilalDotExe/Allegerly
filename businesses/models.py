from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models


def _no_at_sign(value):
    if '@' in value:
        raise ValidationError("Owner usernames can't contain '@'; that is how employee accounts are told apart.")


class Business(models.Model):
    """One business on this server. Its data lives in its own SQLite file.

    This table lives in the control database only; nothing inside a business's
    own database knows the other businesses exist.

    Sign-in finds the business from the username alone:
      - 'owner'      -> the business whose owner_username is 'owner'
      - 'john@trsc'  -> the business whose suffix is 'trsc'
    which is why both must be unique across every business.
    """

    slug = models.SlugField(
        max_length=40, unique=True,
        help_text="Internal code. Names the database file and is kept in the login session.",
    )
    name = models.CharField(max_length=120)
    owner_username = models.CharField(
        max_length=150, unique=True, validators=[_no_at_sign],
        help_text="The business's superuser. Unique across all businesses.",
    )
    suffix = models.CharField(
        max_length=12, unique=True,
        validators=[RegexValidator(r'^[a-z0-9]{2,12}$', "2-12 lowercase letters or digits.")],
        help_text="Added to every employee username (john@suffix). Cannot be changed.",
    )
    is_active = models.BooleanField(default=True, help_text="Inactive businesses cannot sign in.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'businesses'

    def __str__(self):
        return f"{self.name} ({self.slug})"

    def save(self, *args, **kwargs):
        self.slug = self.slug.lower()
        self.suffix = self.suffix.lower()
        if self.pk:
            stored = Business.objects.filter(pk=self.pk).values_list('suffix', flat=True).first()
            if stored is not None and stored != self.suffix:
                raise ValidationError("A business's suffix can't be changed; its employees' usernames depend on it.")
        super().save(*args, **kwargs)

    @classmethod
    def for_username(cls, username):
        """The active business this sign-in name belongs to, or None."""
        username = (username or '').strip()
        _, at, suffix = username.rpartition('@')
        if at:
            return cls.objects.filter(suffix=suffix.lower(), is_active=True).first()
        return cls.objects.filter(owner_username=username, is_active=True).first()

    @property
    def db_alias(self):
        return f'business_{self.slug}'

    @property
    def db_path(self):
        return Path(settings.BUSINESS_DB_DIR) / f'{self.slug}.sqlite3'
