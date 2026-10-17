"""
Safety net for the read-only role.

Business rule: ViewOnly users can look at everything but change nothing.
Individual views already check groups, but a view that forgets would let a
ViewOnly user write. This blocks every write request (POST, PUT, PATCH,
DELETE) from a user whose only role is ViewOnly.
"""

from django.core.exceptions import PermissionDenied
from django.urls import resolve

from .permissions import GROUP_ADMIN, GROUP_EMPLOYEE, GROUP_STAFF, GROUP_VIEW_ONLY

WRITE_METHODS = ('POST', 'PUT', 'PATCH', 'DELETE')

# Logging out is a POST, and a ViewOnly user must still be able to do it.
ALLOWED_URL_NAMES = ('logout',)


class ViewOnlyWriteGuard:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in WRITE_METHODS and self._is_view_only(request.user):
            if not self._is_allowed_url(request):
                raise PermissionDenied
        return self.get_response(request)

    @staticmethod
    def _is_view_only(user):
        if not user.is_authenticated or user.is_superuser:
            return False
        names = set(user.groups.values_list('name', flat=True))
        # Only block people whose sole role is ViewOnly
        return GROUP_VIEW_ONLY in names and not names & {
            GROUP_ADMIN, GROUP_STAFF, GROUP_EMPLOYEE,
        }

    @staticmethod
    def _is_allowed_url(request):
        try:
            return resolve(request.path_info).url_name in ALLOWED_URL_NAMES
        except Exception:
            return False
