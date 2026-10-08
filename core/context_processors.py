from .permissions import is_admin, is_employee


def account(request):
    return {
        "can_edit_company": is_admin(request.user),
        "is_employee": is_employee(request.user),
    }
