from .models import CompanyProfile
from .navigation import build_sidebar
from .permissions import is_admin, is_employee


def account(request):
    context = {
        "can_edit_company": is_admin(request.user),
        "is_employee": is_employee(request.user),
    }
    if request.user.is_authenticated:
        name = CompanyProfile.load().name.strip() or "Allegderly"
        context.update({
            "company_name": name,
            "company_initial": name[0].upper(),
            "sidebar_groups": build_sidebar(request),
        })
    return context
