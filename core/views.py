from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import render
from django.utils import timezone

from damages.models import DamageReport
from inventory.models import Item
from invoices.models import Invoice
from .utils import get_expiring_batches


class AllegderlyLoginView(LoginView):
    template_name = 'registration/login.html'


class AllegderlyLogoutView(LogoutView):
    next_page = 'login'


@login_required
def dashboard(request):
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
    recent_damage_reports = DamageReport.objects.select_related("item").order_by("-created_at")[:10]
    expiring_batches = get_expiring_batches().select_related("item")[:10]
    return render(request, "core/dashboard.html", {
        "low_stock_items": low_stock_items,
        "outstanding_invoices": outstanding_invoices,
        "recent_damage_reports": recent_damage_reports,
        "expiring_batches": expiring_batches,
    })
