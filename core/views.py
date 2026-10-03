from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import render

from core.permissions import ALL_STAFF_GROUPS, group_required


class AllegderlyLoginView(LoginView):
    template_name = 'registration/login.html'
    redirect_authenticated_user = True


class AllegderlyLogoutView(LogoutView):
    """Logout uses POST only (CSRF-protected) via the navbar form."""
    template_name = 'registration/logged_out.html'


@group_required(*ALL_STAFF_GROUPS)
def dashboard(request):
    """Placeholder dashboard — real alerts arrive in later phases."""
    return render(request, 'core/dashboard.html', {
        'page_title': 'Dashboard',
    })
