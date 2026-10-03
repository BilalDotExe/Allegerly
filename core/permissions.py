"""
Permission helpers based on the three staff groups.

Business rule: every view requires login AND membership in at least one
allowed group. Superusers bypass group checks so bootstrap admins work.
"""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

# Group names — must match the data migration exactly
GROUP_ADMIN = 'Admin'
GROUP_STAFF = 'Staff'
GROUP_VIEW_ONLY = 'ViewOnly'

ALL_STAFF_GROUPS = (GROUP_ADMIN, GROUP_STAFF, GROUP_VIEW_ONLY)


def user_in_groups(user, *group_names) -> bool:
    """True if user is a superuser or belongs to any of the named groups."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=group_names).exists()


def is_admin(user) -> bool:
    return user_in_groups(user, GROUP_ADMIN)


def is_staff_user(user) -> bool:
    """Admin or Staff — can perform write actions (not voids/adjustments)."""
    return user_in_groups(user, GROUP_ADMIN, GROUP_STAFF)


def can_view(user) -> bool:
    """Any of the three groups may view pages."""
    return user_in_groups(user, *ALL_STAFF_GROUPS)


def group_required(*group_names):
    """
    Decorator: login required + membership in at least one listed group.

    Usage:
        @group_required(GROUP_ADMIN, GROUP_STAFF)
        def my_view(request): ...
    """

    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not user_in_groups(request.user, *group_names):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
