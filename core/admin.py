from django.contrib.admin import AdminSite
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import PermissionDenied, ValidationError

from core.permissions import is_admin


class AllegderlyAdminAuthenticationForm(AdminAuthenticationForm):
    """Admin login must match the Admin group, not Django's is_staff flag."""

    def confirm_login_allowed(self, user):
        # Skip AdminAuthenticationForm's is_staff check; groups are the source of truth.
        AuthenticationForm.confirm_login_allowed(self, user)
        if not is_admin(user):
            raise ValidationError(
                self.error_messages["invalid_login"],
                code="invalid_login",
                params={"username": self.username_field.verbose_name},
            )


class AllegderlyAdminSite(AdminSite):
    """
    /admin/ is Admin-group only (plus superusers).

    Staff and ViewOnly use the main app, not Django admin. Spec: every view
    checks group permission — is_staff is not enough.
    """

    site_header = "Allegderly administration"
    site_title = "Allegderly admin"
    index_title = "Site administration"
    login_form = AllegderlyAdminAuthenticationForm

    def has_permission(self, request):
        return request.user.is_active and is_admin(request.user)

    def admin_view(self, view, cacheable=False):
        wrapped = super().admin_view(view, cacheable=cacheable)

        def inner(request, *args, **kwargs):
            # Logged-in Staff/ViewOnly should get 403, not the admin login form.
            if request.user.is_authenticated and not self.has_permission(request):
                raise PermissionDenied
            return wrapped(request, *args, **kwargs)

        return inner
