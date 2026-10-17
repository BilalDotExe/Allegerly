import re
import sqlite3
from contextlib import closing
from pathlib import Path

import django.core.validators
from django.conf import settings
from django.db import migrations, models

import businesses.models


def _suffix_from(name):
    words = re.findall(r'[A-Za-z0-9]+', name)
    suffix = ''.join(word[0] for word in words).lower()
    if len(suffix) < 2:
        suffix = ''.join(words).lower()[:4]
    return suffix


def fill_existing(apps, schema_editor):
    """Give businesses created before this migration an owner and a suffix.

    The owner is the first superuser in the business's own database, and its
    other accounts are renamed to name@suffix so they can still sign in.
    """
    Business = apps.get_model('businesses', 'Business')
    taken = set()
    for business in Business.objects.order_by('pk'):
        suffix, n = _suffix_from(business.name), 1
        while suffix in taken:
            n += 1
            suffix = f'{_suffix_from(business.name)}{n}'
        taken.add(suffix)

        owner = f'owner-{business.slug}'
        path = Path(settings.BUSINESS_DB_DIR) / f'{business.slug}.sqlite3'
        if path.exists():
            with closing(sqlite3.connect(path)) as con, con:
                row = con.execute(
                    'SELECT username FROM auth_user WHERE is_superuser = 1 ORDER BY id LIMIT 1'
                ).fetchone()
                if row:
                    owner = row[0]
                con.execute(
                    "UPDATE auth_user SET username = lower(username) || ? "
                    "WHERE is_superuser = 0 AND username NOT LIKE '%@%'",
                    (f'@{suffix}',),
                )
        business.suffix = suffix
        business.owner_username = owner
        business.save(update_fields=['suffix', 'owner_username'])


class Migration(migrations.Migration):

    dependencies = [
        ('businesses', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='business',
            name='owner_username',
            field=models.CharField(max_length=150, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='business',
            name='suffix',
            field=models.CharField(max_length=12, null=True, unique=True),
        ),
        migrations.RunPython(fill_existing, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='business',
            name='owner_username',
            field=models.CharField(
                help_text='The business\'s superuser. Unique across all businesses.',
                max_length=150, unique=True, validators=[businesses.models._no_at_sign],
            ),
        ),
        migrations.AlterField(
            model_name='business',
            name='suffix',
            field=models.CharField(
                help_text='Added to every employee username (john@suffix). Cannot be changed.',
                max_length=12, unique=True,
                validators=[django.core.validators.RegexValidator('^[a-z0-9]{2,12}$', '2-12 lowercase letters or digits.')],
            ),
        ),
        migrations.AlterField(
            model_name='business',
            name='slug',
            field=models.SlugField(
                help_text='Internal code. Names the database file and is kept in the login session.',
                max_length=40, unique=True,
            ),
        ),
    ]
