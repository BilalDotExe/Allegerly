from django.core.management.base import BaseCommand, CommandError

from businesses.models import Business
from django.db import connections


class Command(BaseCommand):
    help = "Permanently delete a business and its database file."

    def add_arguments(self, parser):
        parser.add_argument('slug', help="The business's slug, e.g. soap.")
        parser.add_argument(
            '--yes', action='store_true',
            help="Skip the confirmation prompt.",
        )

    def handle(self, slug, yes=False, **options):
        try:
            business = Business.objects.get(slug=slug)
        except Business.DoesNotExist:
            raise CommandError(f"No business with slug '{slug}'.")

        self.stdout.write(f"Business : {business.name}")
        self.stdout.write(f"Database : {business.db_path}")
        self.stdout.write(self.style.WARNING("This cannot be undone."))

        if not yes:
            confirm = input("Type the slug to confirm: ").strip()
            if confirm != slug:
                raise CommandError("Aborted — slug did not match.")

        path = business.db_path
        alias = business.db_alias

        # Close Django's connection to the file before deleting it.
        if alias in connections.settings:
            connections[alias].close()
            del connections.settings[alias]

        business.delete()

        if path.exists():
            path.unlink()
            self.stdout.write(f"Deleted {path}")
        else:
            self.stdout.write(self.style.WARNING(f"Database file not found at {path} — skipped."))

        self.stdout.write(self.style.SUCCESS(f"Business '{slug}' removed."))
