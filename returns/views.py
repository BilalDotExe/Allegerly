from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import redirect, render

from reports.forms import DateRangeForm
from reports.utils import export_csv

from .forms import ReturnRecordForm
from .models import ReturnRecord
from .services import log_return


@login_required
def return_list(request):
    records = ReturnRecord.objects.select_related(
        "invoice_line__invoice", "invoice_line__invoice__customer", "invoice_line__item", "created_by"
    ).order_by("-date_returned", "-created_at")
    form = DateRangeForm(request.GET or None)
    if form.is_valid():
        start_date = form.cleaned_data.get("start_date")
        end_date = form.cleaned_data.get("end_date")
        if start_date:
            records = records.filter(date_returned__gte=start_date)
        if end_date:
            records = records.filter(date_returned__lte=end_date)

    export_params = request.GET.copy()
    export_params["export"] = "csv"
    export_query = export_params.urlencode()
    if request.GET.get("export") == "csv":
        return export_csv(
            "returns.csv",
            ["Date", "Item", "Customer", "Invoice", "Quantity", "Restockable", "Note"],
            [[record.date_returned, record.invoice_line.item.name,
              record.invoice_line.invoice.customer.name, record.invoice_line.invoice.invoice_number,
              record.quantity, record.is_restockable, record.note] for record in records],
        )

    page_obj = Paginator(records, 25).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return render(request, "returns/list.html", {
        "page_obj": page_obj,
        "pagination_query": query.urlencode(),
        "form": form,
        "export_query": export_query,
    })


@login_required
def return_create(request):
    form = ReturnRecordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            record, credit = log_return(
                invoice_line=data["invoice_line"], quantity=data["quantity"],
                date_returned=data["date_returned"], created_by=request.user,
                is_restockable=data["is_restockable"], note=data["note"], request=request,
                resolution=data["resolution"], refund_method=data["refund_method"],
            )
            messages.success(request, f"Return recorded; credit note {credit.credit_number} created.")
            return redirect("returns:list")
        except ValidationError as e:
            messages.error(request, e.message)
    return render(request, "returns/form.html", {"form": form, "title": "New Return"})
