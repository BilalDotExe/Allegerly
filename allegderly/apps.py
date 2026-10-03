from django.contrib.admin.apps import AdminConfig


class AllegderlyAdminConfig(AdminConfig):
    """Swap Django's default admin site for one that checks the Admin group."""

    default_site = 'core.admin.AllegderlyAdminSite'
