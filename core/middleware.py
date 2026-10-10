"""Cross-cutting request guards."""

from django.core.exceptions import PermissionDenied
from django.urls import Resolver404, resolve

from .permissions import GROUP_VIEW_ONLY

SAFE_METHODS = frozenset({'GET', 'HEAD', 'OPTIONS', 'TRACE'})

# Submitting these is not a business write, so ViewOnly must still be able to.
VIEW_ONLY_ALLOWED_URL_NAMES = frozenset({'login', 'logout'})


class ViewOnlyWriteGuard:
    """Blocks every unsafe request method for ViewOnly accounts.

    The group is specified as read-only, but that was enforced per-view, which
    meant a view added without the right decorator silently handed ViewOnly
    write access. Enforcing it here instead makes it impossible to forget.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._is_blocked(request):
            raise PermissionDenied("Read-only account.")
        return self.get_response(request)

    @staticmethod
    def _is_blocked(request):
        if request.method in SAFE_METHODS:
            return False
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated or user.is_superuser:
            return False
        if not user.groups.filter(name=GROUP_VIEW_ONLY).exists():
            return False
        try:
            url_name = resolve(request.path_info).url_name
        except Resolver404:
            return False  # Nothing routed here; let Django return its own 404.
        return url_name not in VIEW_ONLY_ALLOWED_URL_NAMES
