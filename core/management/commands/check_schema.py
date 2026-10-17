"""Compare the models against the database that is actually on this machine.

The test suite builds a fresh database from the migrations, so it cannot see a
real database that has drifted — for example a column left behind by a
migration whose file was lost. Such a column is invisible until someone tries
to save a record and the insert fails on a NOT NULL constraint.

Run this after restoring a backup, after copying a database between machines,
or whenever saving a record fails for no obvious reason:

    python manage.py check_schema
"""

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import connection

LOCAL_APPS = {
    'core', 'customers', 'vendors', 'purchasing', 'expenses', 'inventory',
    'invoices', 'damages', 'returns', 'production', 'reports', 'audit',
}


class Command(BaseCommand):
    help = 'Check that every model matches the database on this machine.'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute("select name from sqlite_master where type='table'")
            tables = {row[0] for row in cursor.fetchall()}

        problems = []
        for model in apps.get_models():
            if model._meta.app_label not in LOCAL_APPS:
                continue

            table = model._meta.db_table
            if table not in tables:
                problems.append(f'{table}: table is missing from the database')
                continue

            with connection.cursor() as cursor:
                cursor.execute(f'pragma table_info({table})')
                live = {r[1]: {'notnull': r[3], 'default': r[4]} for r in cursor.fetchall()}

            declared = {field.column for field in model._meta.local_fields}

            for column in sorted(declared - set(live)):
                problems.append(f'{table}.{column}: the model has this field, the database has no column')

            for column in sorted(set(live) - declared):
                info = live[column]
                if info['notnull'] and info['default'] is None:
                    problems.append(
                        f'{table}.{column}: column is NOT NULL but no model field sets it — '
                        f'saving a new record here will fail'
                    )
                else:
                    problems.append(f'{table}.{column}: left-over column, no model field (harmless)')

        if not problems:
            self.stdout.write(self.style.SUCCESS('Every model matches this database.'))
            return

        for problem in problems:
            self.stdout.write(self.style.WARNING(problem))
        self.stdout.write('')
        self.stdout.write(f'{len(problems)} difference(s) found.')
