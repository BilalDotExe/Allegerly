from .navigation import build_navigation
from .permissions import is_admin, is_employee


def account(request):
    employee = is_employee(request.user)
    context = {
        "can_edit_company": is_admin(request.user),
        "is_employee": employee,
    }
    if request.user.is_authenticated:
        context.update(build_navigation(request, employee))
    return context
