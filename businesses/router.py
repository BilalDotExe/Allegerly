from django.db import DEFAULT_DB_ALIAS

from .db import active_db

# Shared by every business: the business list itself, login sessions (needed
# before we know which business you are) and django-axes lockouts.
CONTROL_APPS = frozenset({'businesses', 'sessions', 'axes'})


class BusinessRouter:
    """Sends everything except the control apps to the active business's database."""

    def db_for_read(self, model, **hints):
        if model._meta.app_label in CONTROL_APPS:
            return DEFAULT_DB_ALIAS
        return active_db()

    db_for_write = db_for_read

    def allow_migrate(self, db, app_label, **hints):
        if app_label in CONTROL_APPS:
            return db == DEFAULT_DB_ALIAS
        return None
