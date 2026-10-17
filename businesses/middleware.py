from django.contrib.auth import SESSION_KEY as USER_SESSION_KEY

from .db import activate, reset
from .models import Business

BUSINESS_SESSION_KEY = '_business'


class BusinessMiddleware:
    """Points every query in the request at the signed-in user's business.

    Must sit after SessionMiddleware and before AuthenticationMiddleware, so the
    user is looked up in the right business's database.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.business = self._business_for(request)
        token = activate(request.business)
        try:
            return self.get_response(request)
        finally:
            reset(token)

    @staticmethod
    def _business_for(request):
        slug = request.session.get(BUSINESS_SESSION_KEY)
        if slug:
            business = Business.objects.filter(slug=slug, is_active=True).first()
            if business is None:
                request.session.flush()  # Business removed or deactivated: sign out.
            return business
        # With no businesses set up the app runs on 'default' as a single
        # business. Once any exist, a signed-in session must name one.
        if USER_SESSION_KEY in request.session and Business.objects.exists():
            request.session.flush()
        return None
