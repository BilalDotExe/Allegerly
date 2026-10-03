from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import render


class AllegderlyLoginView(LoginView):
    template_name = 'registration/login.html'


class AllegderlyLogoutView(LogoutView):
    next_page = 'login'


@login_required
def dashboard(request):
    return render(request, 'core/dashboard.html')