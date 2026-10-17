from django.core.management.base import BaseCommand

from businesses.models import Business
from businesses.services import migrate_business


class Command(BaseCommand):
    help = "Apply migrations to every business's database. Run after `migrate` on each update."

    def handle(self, **options):
        for business in Business.objects.all():
            migrate_business(business)
            self.stdout.write(f"Migrated {business}")
        self.stdout.write(self.style.SUCCESS("All businesses are up to date."))
