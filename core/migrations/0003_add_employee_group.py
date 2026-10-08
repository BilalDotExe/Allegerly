"""
Add the Employee group: a narrower role bolted on after Admin/Staff/ViewOnly.

Employee accounts can only make invoices, manage purchase orders, handle
returns and make damage reports — no customers, vendors, items, production,
reports or audit log. Enforced in code (core.permissions), this migration
just makes sure the row exists.
"""

from django.contrib.auth.models import Group
from django.db import migrations

GROUP_NAME = 'Employee'


def create_group(apps, schema_editor):
    Group.objects.get_or_create(name=GROUP_NAME)


def remove_group(apps, schema_editor):
    Group.objects.filter(name=GROUP_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_customer_contact_and_addresses'),
    ]

    operations = [
        migrations.RunPython(create_group, remove_group),
    ]
