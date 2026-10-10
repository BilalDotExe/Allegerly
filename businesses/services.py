import re
import sqlite3
from contextlib import closing
from pathlib import Path

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import connections

from core.permissions import GROUP_ADMIN, GROUP_STAFF, GROUP_VIEW_ONLY
from .db import business_context, connect
from .models import Business

# Created by an old migration but no longer used; a new business starts without them.
UNUSED_GROUPS = (GROUP_ADMIN, GROUP_STAFF, GROUP_VIEW_ONLY)


def default_suffix(name):
    """Initials of the business name: 'Totally Real Shipping Co' -> 'trsc'."""
    words = re.findall(r'[A-Za-z0-9]+', name)
    suffix = ''.join(word[0] for word in words).lower()
    return suffix if len(suffix) >= 2 else ''.join(words).lower()[:4]


def create_business(slug, name, owner_username, owner_password=None, suffix=None, source_file=None):
    """Create a business and its database.

    Without source_file the business starts empty, with a new superuser
    (owner_username / owner_password). With it, that SQLite database is copied
    in as the business's data and owner_username must already be its only
    superuser; its other accounts are renamed to name@suffix.
    """
    business = Business(
        slug=slug, name=name, owner_username=owner_username,
        suffix=(suffix or default_suffix(name)).lower(),
    )
    business.full_clean()
    path = business.db_path
    if path.exists():
        raise ValidationError(f"{path} already exists.")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if source_file:
            _copy_sqlite(Path(source_file), path)
        migrate_business(business)
        with business_context(business):
            if source_file:
                _adopt_users(business)
            else:
                Group.objects.filter(name__in=UNUSED_GROUPS).delete()
                User.objects.create_superuser(owner_username, '', owner_password)
    except Exception:
        connections[business.db_alias].close()
        path.unlink(missing_ok=True)
        raise
    business.save()
    return business


def migrate_business(business):
    """Bring one business's database up to the latest migrations."""
    alias = connect(business)
    # The context makes data migrations (e.g. group seeding) write here too.
    with business_context(business):
        call_command('migrate', database=alias, interactive=False, verbosity=0)


def _adopt_users(business):
    superusers = list(User.objects.filter(is_superuser=True).values_list('username', flat=True))
    if superusers != [business.owner_username]:
        raise ValidationError(
            f"The database must have exactly one superuser, '{business.owner_username}'; "
            f"it has: {', '.join(superusers) or 'none'}."
        )
    for user in User.objects.filter(is_superuser=False).exclude(username__contains='@'):
        user.username = f'{user.username.lower()}@{business.suffix}'
        user.save(update_fields=['username'])


def _copy_sqlite(source, target):
    # sqlite3.connect would quietly create an empty file for a wrong path.
    if not source.is_file():
        raise ValidationError(f"{source} does not exist.")
    # The backup API gives a consistent copy even if the source is in use.
    with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(target)) as dst:
        src.backup(dst)
