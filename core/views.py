from django.contrib import messages
from django.contrib.auth.models import Group, User
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from inventory.models import Item
from .forms import CompanyProfileForm, EmployeeCreateForm, EmployeePasswordResetForm
from .models import CompanyProfile
from .permissions import (
    ALL_GROUPS, GROUP_ADMIN, GROUP_EMPLOYEE, group_required, is_employee, superuser_required,
)
from invoices.models import Invoice
from .dashboard_data import build_dashboard, build_employee_dashboard, parse_range
from .utils import generate_temp_password, get_expiring_batches


class AllegderlyLoginView(LoginView):
    template_name = 'registration/login.html'


class AllegderlyLogoutView(LogoutView):
    next_page = 'login'


@group_required(GROUP_ADMIN)
def account_settings(request):
    form = CompanyProfileForm(request.POST or None, instance=CompanyProfile.load())
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Company settings saved.")
        return redirect("account_settings")
    return render(request, "core/account_settings.html", {"form": form})


def _employee_accounts():
    # is_superuser=False is deliberate, not redundant with the Employee-group
    # filter: a superuser who was also (for whatever reason) added to the
    # Employee group must never show up here to be deactivated or deleted —
    # that would lock the account owner out of their own login.
    return User.objects.filter(groups__name=GROUP_EMPLOYEE, is_superuser=False)


@superuser_required
def employee_list(request):
    employees = _employee_accounts().order_by("username")
    # One-time reveal: popped from the session so a refresh never shows it twice.
    reveal = request.session.pop("reveal_password", None)
    reveal_employee = None
    reveal_password = None
    if reveal:
        reveal_employee = next((e for e in employees if e.pk == reveal.get("user_id")), None)
        reveal_password = reveal.get("password") if reveal_employee else None
    return render(request, "core/employee_list.html", {
        "employees": employees,
        "reveal_password": reveal_password,
        "reveal_employee": reveal_employee,
    })


@superuser_required
def employee_create(request):
    form = EmployeeCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        password = form.cleaned_data["password"] or generate_temp_password()
        employee = User.objects.create_user(
            username=form.cleaned_data["username"],
            first_name=form.cleaned_data["first_name"],
            last_name=form.cleaned_data["last_name"],
            password=password,
        )
        employee_group, _ = Group.objects.get_or_create(name=GROUP_EMPLOYEE)
        employee.groups.add(employee_group)
        request.session["reveal_password"] = {"user_id": employee.pk, "password": password}
        messages.success(request, f'Employee account "{employee.username}" created.')
        return redirect("employee_list")
    return render(request, "core/employee_form.html", {"form": form, "title": "New Employee Account"})


@superuser_required
def employee_reset_password(request, pk):
    employee = get_object_or_404(_employee_accounts(), pk=pk)
    form = EmployeePasswordResetForm(request.POST or None, employee=employee)
    if request.method == "POST" and form.is_valid():
        password = form.cleaned_data["password"] or generate_temp_password()
        employee.set_password(password)
        employee.save(update_fields=["password"])
        request.session["reveal_password"] = {"user_id": employee.pk, "password": password}
        messages.success(request, f'Password reset for "{employee.username}".')
        return redirect("employee_list")
    return render(request, "core/employee_password_form.html", {"form": form, "employee": employee})


@superuser_required
@require_POST
def employee_toggle_active(request, pk):
    employee = get_object_or_404(_employee_accounts(), pk=pk)
    employee.is_active = not employee.is_active
    employee.save(update_fields=["is_active"])
    messages.success(
        request,
        f'Employee account "{employee.username}" '
        f'{"reactivated" if employee.is_active else "deactivated"}.',
    )
    return redirect("employee_list")


@superuser_required
@require_POST
def employee_delete(request, pk):
    employee = get_object_or_404(_employee_accounts(), pk=pk)
    username = employee.username
    try:
        employee.delete()
        messages.success(request, f'Employee account "{username}" deleted.')
    except ProtectedError:
        # Append-only records (invoices, POs, returns, damage reports) block
        # deleting whoever created them — deactivating keeps that history intact.
        messages.error(
            request,
            f'"{username}" has created records (invoices, purchase orders, returns or '
            f'damage reports) and can\'t be deleted. Deactivate the account instead.',
        )
    return redirect("employee_list")


@group_required(*ALL_GROUPS)
def dashboard(request):
    if is_employee(request.user):
        return render(request, "core/dashboard_employee.html", build_employee_dashboard())
    items = Item.objects.all().order_by("name")
    low_stock_items = [item for item in items if item.is_low_stock()]
    today = timezone.localdate()
    outstanding_invoices = list(
        Invoice.objects.select_related("customer")
        .filter(status__in=("issued", "paid"))
        .order_by("due_date", "-created_at")
    )
    outstanding_invoices = [invoice for invoice in outstanding_invoices if invoice.balance_due > 0]
    for invoice in outstanding_invoices:
        invoice.days_overdue = max((today - invoice.due_date).days, 0) if invoice.due_date else 0
    expiring_batches = get_expiring_batches().select_related("item")[:6]
    context = build_dashboard(parse_range(request.GET.get("range")), today)
    return render(request, "core/dashboard.html", {
        **context,
        "low_stock_items": low_stock_items[:6],
        "low_stock_total": len(low_stock_items),
        "outstanding_invoices": outstanding_invoices[:6],
        "outstanding_total": len(outstanding_invoices),
        "expiring_batches": expiring_batches,
    })
