from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import redirect, render

from reports.forms import DateRangeForm
from reports.utils import export_csv

from .forms import DamageReportForm
from .models import DamageReport
from .services import log_damage


@login_required
def damage_list(request):
    reports = DamageReport.objects.select_related("item", "invoice_line__invoice", "created_by").order_by("-date_reported", "-created_at")
    form = DateRangeForm(request.GET or None)
    if form.is_valid():
        start_date = form.cleaned_data.get("start_date")
        end_date = form.cleaned_data.get("end_date")
        if start_date:
            reports = reports.filter(date_reported__gte=start_date)
        if end_date:
            reports = reports.filter(date_reported__lte=end_date)

    export_params = request.GET.copy()
    export_params["export"] = "csv"
    export_query = export_params.urlencode()
    if request.GET.get("export") == "csv":
        return export_csv(
            "damages.csv",
            ["Date", "Item SKU", "Item Name", "Quantity", "Loss Value", "Note", "Reported By"],
            [[report.date_reported, report.item.sku, report.item.name, report.quantity,
              report.loss_value, report.note, report.created_by] for report in reports],
        )

    page_obj = Paginator(reports, 25).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return render(request, "damages/list.html", {
        "page_obj": page_obj,
        "pagination_query": query.urlencode(),
        "form": form,
        "export_query": export_query,
    })


@login_required
def damage_create(request):
    form = DamageReportForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            log_damage(
                item=data["item"], quantity=data["quantity"],
                date_reported=data["date_reported"], created_by=request.user,
                invoice_line=data["invoice_line"], note=data["note"], request=request,
            )
            messages.success(request, "Damage report recorded.")
            return redirect("damages:list")
        except ValidationError as e:
            messages.error(request, e.message)
    return render(request, "damages/form.html", {"form": form, "title": "New Damage Report"})
