from django.contrib.auth.forms import AuthenticationForm

from .db import activate
from .models import Business


class BusinessLoginForm(AuthenticationForm):
    """Plain username + password; the username says which business it belongs to."""

    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login': "Username or password is incorrect.",
    }

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.business_obj = None

    def clean(self):
        if Business.objects.exists():
            username = (self.cleaned_data.get('username') or '').strip()
            self.business_obj = Business.for_username(username)
            if self.business_obj is None:
                raise self.get_invalid_login_error()
            # Employee usernames are stored lowercase; owners keep their case.
            self.cleaned_data['username'] = username.lower() if '@' in username else username
            # Left active for the rest of this request so the user, last_login
            # and the session all land in this business. The middleware resets it.
            activate(self.business_obj)
        return super().clean()
