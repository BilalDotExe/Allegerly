"""Which business's database the current request (or command) is using."""

import copy
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

from django.db import DEFAULT_DB_ALIAS, connections, transaction

_active_alias = ContextVar('active_business_db', default=None)


def active_db():
    """Alias of the active business's database, or None, meaning 'default'."""
    return _active_alias.get()


def connect(business):
    """Register the business's SQLite file as a Django connection; return its alias."""
    alias = business.db_alias
    if alias not in connections.settings:
        config = copy.deepcopy(connections.settings[DEFAULT_DB_ALIAS])
        config['NAME'] = str(business.db_path)
        connections.settings[alias] = config
    return alias


def activate(business):
    """Route queries to this business (None for 'default'). Returns a token for reset()."""
    return _active_alias.set(connect(business) if business else None)


def reset(token):
    _active_alias.reset(token)


@contextmanager
def business_context(business):
    """Run a block against one business's database, e.g. in a management command."""
    token = activate(business)
    try:
        yield
    finally:
        reset(token)


def atomic(func=None):
    """transaction.atomic on the active business's database.

    Plain transaction.atomic always opens its transaction on 'default', so a
    business's writes would run outside any transaction at all. Use this
    instead, as `@atomic` or `with atomic():`.
    """
    if func is None:
        return transaction.atomic(using=active_db())

    @wraps(func)
    def inner(*args, **kwargs):
        with transaction.atomic(using=active_db()):
            return func(*args, **kwargs)
    return inner
