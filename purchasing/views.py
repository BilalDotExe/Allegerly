from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from core.models import CompanyProfile
from core.pagination import paginate
from reports.utils import export_csv
from .forms import (
    CancelOrderForm,
    PurchaseOrderFilterForm,
    PurchaseOrderForm,
    PurchaseOrderLineFormSet,
    PurchasePaymentForm,
    ReceiveHeaderForm,
    ReceiveLineForm,
)
from .models import PurchaseOrder
from .services import (
    cancel_order,
    close_order,
    create_order,
    place_order,
    receive_goods,
    record_purchase_payment,
    update_order,
)


def _error_text(exc):
    return " ".join(exc.messages)


@login_required
def po_list(request):
    orders = PurchaseOrder.objects.select_related("vendor").prefetch_related("payments")
    form = PurchaseOrderFilterForm(request.GET or None)
    if form.is_valid():
        if form.cleaned_data.get("start_date"):
            orders = orders.filter(order_date__gte=form.cleaned_data["start_date"])
        if form.cleaned_data.get("end_date"):
            orders = orders.filter(order_date__lte=form.cleaned_data["end_date"])
        if form.cleaned_data.get("status"):
            orders = orders.filter(status=form.cleaned_data["status"])

    export_params = request.GET.copy()
    export_params["export"] = "csv"
    export_query = export_params.urlencode()
    if request.GET.get("export") == "csv":
        return export_csv(
            "purchase_orders.csv",
            ["PO Number", "Vendor", "Status", "Payment", "Order Date", "Expected", "Total", "Balance Due"],
            [[o.po_number, o.vendor.name, o.get_status_display(), o.payment_status_display,
              o.order_date, o.expected_date or "", o.total, o.balance_due] for o in orders],
        )

    page_obj, pagination_query = paginate(request, orders)
    return render(request, "purchasing/list.html", {
        "page_obj": page_obj,
        "pagination_query": pagination_query,
        "form": form,
        "export_query": export_query,
    })


@login_required
def po_create(request):
    initial = {}
    if request.GET.get("vendor", "").isdigit():
        initial["vendor"] = request.GET["vendor"]
    form = PurchaseOrderForm(request.POST or None, initial=initial)
    formset = PurchaseOrderLineFormSet(request.POST or None)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        try:
            po = create_order(form, formset, request.user, request=request)
        except ValidationError as e:
            messages.error(request, _error_text(e))
        else:
            messages.success(request, f"Purchase order {po.po_number} created.")
            return redirect("purchasing:detail", pk=po.pk)
    return render(request, "purchasing/form.html", {"form": form, "formset": formset, "title": "New Purchase Order"})


@login_required
def po_detail(request, pk):
    po = get_object_or_404(PurchaseOrder.objects.select_related("vendor", "created_by"), pk=pk)
    return render(request, "purchasing/detail.html", {
        "po": po,
        "lines": po.lines.all(),
        "receipts": po.receipts.prefetch_related("lines__po_line"),
        "payments": po.payments.select_related("created_by"),
    })


@login_required
def po_edit(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    if not po.is_editable:
        messages.error(request, f"A {po.get_status_display().lower()} purchase order can no longer be edited.")
        return redirect("purchasing:detail", pk=pk)
    form = PurchaseOrderForm(request.POST or None, instance=po)
    formset = PurchaseOrderLineFormSet(request.POST or None, instance=po)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        try:
            update_order(form, formset, request.user, request=request)
        except ValidationError as e:
            messages.error(request, _error_text(e))
        else:
            messages.success(request, f"Purchase order {po.po_number} updated.")
            return redirect("purchasing:detail", pk=pk)
    return render(request, "purchasing/form.html", {
        "form": form, "formset": formset, "title": f"Edit {po.po_number}", "po": po,
    })


@login_required
def po_place(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    if request.method == "POST":
        try:
            place_order(po, request.user, request=request)
            messages.success(request, f"Purchase order {po.po_number} placed.")
        except ValidationError as e:
            messages.error(request, _error_text(e))
    return redirect("purchasing:detail", pk=pk)


@login_required
def po_receive(request, pk):
    po = get_object_or_404(PurchaseOrder.objects.select_related("vendor"), pk=pk)
    if not po.can_receive:
        messages.error(request, "Only ordered or partially received purchase orders can receive goods.")
        return redirect("purchasing:detail", pk=pk)

    outstanding = [line for line in po.lines.all() if line.outstanding_qty > 0]
    posted = request.POST if request.method == "POST" else None
    header = ReceiveHeaderForm(posted)
    line_forms = [
        (line, ReceiveLineForm(posted, prefix=f"line{line.pk}", po_line=line))
        for line in outstanding
    ]
    if request.method == "POST" and header.is_valid() and all(f.is_valid() for _, f in line_forms):
        entries = [
            {
                "po_line": line,
                "quantity": f.cleaned_data["quantity"],
                "unit_cost": f.cleaned_data["unit_cost"],
            }
            for line, f in line_forms
        ]
        try:
            receipt = receive_goods(
                po, header.cleaned_data["received_date"], entries, request.user,
                note=header.cleaned_data["note"],
                request=request,
            )
        except ValidationError as e:
            messages.error(request, _error_text(e))
        else:
            messages.success(request, f"{receipt.receipt_number} recorded.")
            return redirect("purchasing:detail", pk=pk)
    return render(request, "purchasing/receive.html", {"po": po, "header": header, "line_forms": line_forms})


@login_required
def po_close(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    if request.method == "POST":
        try:
            close_order(po, request.user, request=request)
            messages.success(request, f"{po.po_number} closed as received.")
        except ValidationError as e:
            messages.error(request, _error_text(e))
    return redirect("purchasing:detail", pk=pk)


@login_required
@permission_required("purchasing.change_purchaseorder", raise_exception=True)
def po_cancel(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    form = CancelOrderForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            cancel_order(po, request.user, form.cleaned_data["reason"], request=request)
            messages.success(request, f"Purchase order {po.po_number} cancelled.")
            return redirect("purchasing:detail", pk=pk)
        except ValidationError as e:
            messages.error(request, _error_text(e))
    return render(request, "purchasing/cancel_form.html", {"form": form, "po": po})


@login_required
def po_payment(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    if po.status in ("draft", "cancelled") or po.balance_due <= 0:
        messages.error(request, "This purchase order cannot take a payment right now.")
        return redirect("purchasing:detail", pk=pk)
    form = PurchasePaymentForm(request.POST or None, initial={"amount": po.balance_due})
    if request.method == "POST" and form.is_valid():
        try:
            record_purchase_payment(
                po,
                amount=form.cleaned_data["amount"],
                method=form.cleaned_data["method"],
                payment_date=form.cleaned_data["payment_date"],
                user=request.user,
                reference=form.cleaned_data.get("reference", ""),
                note=form.cleaned_data.get("note", ""),
                request=request,
            )
            messages.success(request, "Payment recorded.")
            return redirect("purchasing:detail", pk=pk)
        except ValidationError as e:
            messages.error(request, _error_text(e))
    return render(request, "purchasing/payment_form.html", {"form": form, "po": po})


@login_required
def po_print(request, pk):
    po = get_object_or_404(PurchaseOrder.objects.select_related("vendor", "created_by"), pk=pk)
    if po.status in ("draft", "cancelled"):
        messages.error(
            request,
            "Only placed purchase orders can be viewed in full or printed. "
            f"This one is {po.get_status_display().lower()}.",
        )
        return redirect("purchasing:detail", pk=pk)
    return render(request, "purchasing/print.html", {
        "po": po,
        "lines": po.lines.all(),
        "payments": po.payments.all(),
        "company": CompanyProfile.load(),
    })
