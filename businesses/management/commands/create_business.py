from getpass import getpass

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from businesses.services import create_business


class Command(BaseCommand):
    help = (
        "Create a business with its own database. Examples:\n"
        "  create_business soap \"Al's Soap Co\" --owner admin\n"
        "  create_business main \"Acme\" --owner admin --from-file db.sqlite3"
    )

    def add_arguments(self, parser):
        parser.add_argument('slug', help="Internal code; names the database file, e.g. soap.")
        parser.add_argument('name', help="Display name.")
        parser.add_argument('--owner', required=True,
                            help="The business's superuser username (unique across all businesses, no '@').")
        parser.add_argument('--suffix', help="Employee username suffix; defaults to the name's initials.")
        parser.add_argument('--from-file',
                            help="Copy this SQLite database in as the business's data; --owner must be its only superuser.")

    def handle(self, slug, name, owner, suffix=None, from_file=None, **options):
        password = None if from_file else self._ask_password(owner)
        try:
            business = create_business(
                slug, name, owner, owner_password=password, suffix=suffix, source_file=from_file,
            )
        except ValidationError as e:
            raise CommandError("; ".join(e.messages))
        self.stdout.write(self.style.SUCCESS(
            f"Created {business.name}. Owner signs in as '{business.owner_username}'; "
            f"employees as name@{business.suffix}."
        ))

    @staticmethod
    def _ask_password(username):
        password = getpass(f"Password for {username}: ")
        if password != getpass("Again: "):
            raise CommandError("Passwords did not match.")
        try:
            validate_password(password, User(username=username))
        except ValidationError as e:
            raise CommandError(" ".join(e.messages))
        return password
