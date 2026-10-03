"""
Create the three permission groups used across the app.

Admin  — full access (voids, stock adjustments, audit log)
Staff  — day-to-day create/record actions (no voids or adjustments)
ViewOnly — read-only on all pages
"""

from django.contrib.auth.models import Group
from django.db import migrations

GROUP_NAMES = ('Admin', 'Staff', 'ViewOnly')


def create_groups(apps, schema_editor):
    for name in GROUP_NAMES:
        Group.objects.get_or_create(name=name)


def remove_groups(apps, schema_editor):
    Group.objects.filter(name__in=GROUP_NAMES).delete()


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        # auth.Group must exist before we create rows in it
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(create_groups, remove_groups),
    ]
