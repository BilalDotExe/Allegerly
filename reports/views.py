from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import DecimalField, ExpressionWrapper, F, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import render

from core.money import money
from damages.models import DamageReport
from inventory.models import ExpiryWriteOff, Item
from invoices.models import Invoice
from production.models import ProductionBatch
from returns.models import ReturnRecord

from .forms import DateRangeForm
from .utils import export_csv


ZERO_MONEY = Decimal("0.00")
MONEY_FIELD = DecimalField(max_digits=14, decimal_places=2)


def _date_range(request):
    form = DateRangeForm(request.GET or None)
    if form.is_valid():
        return form, form.cleaned_data.get("start_date"), form.cleaned_data.get("end_date")
    return form, None, None


def _apply_date_range(queryset, field, start_date, end_date):
    if start_date:
        queryset = queryset.filter(**{f"{field}__gte": start_date})
    if end_date:
        queryset = queryset.filter(**{f"{field}__lte": end_date})
    return queryset


def _export_query(request):
    query = request.GET.copy()
    query["export"] = "csv"
    return query.urlencode()


def _report_context(request, form, **context):
    return {"form": form, "export_query": _export_query(request), **context}


@login_required
def report_index(request):
    reports = [
        ("Sales", "Revenue from issued and paid invoices.", "reports:sales"),
        ("Outstanding Invoices", "Balances due and days overdue.", "reports:outstanding"),
        ("Stock Levels", "Current stock and low stock items.", "reports:stock"),
        ("Damages", "Recorded damaged stock and loss value.", "reports:damages"),
        ("Returns", "Returned quantities by item and customer.", "reports:returns"),
        ("Expiry", "Expired stock write-offs and loss value.", "reports:expiry"),
        ("Production", "Production batches and quantities produced.", "reports:production"),
    ]
    return render(request, "reports/index.html", {"reports": reports})


@login_required
def sales_report(request):
    form, start_date, end_date = _date_range(request)
    invoices = Invoice.objects.filter(status__in=["issued", "paid"]).select_related("customer")
    invoices = _apply_date_range(invoices, "issue_date", start_date, end_date)
    invoices = invoices.annotate(
        report_subtotal=Coalesce(
            Sum(
                ExpressionWrapper(
                    F("lines__quantity") * F("lines__unit_price"),
                    output_field=MONEY_FIELD,
                )
            ),
            Value(ZERO_MONEY, output_field=MONEY_FIELD),
            output_field=MONEY_FIELD,
        )
    ).order_by("issue_date", "invoice_number")
    invoice_list = list(invoices)
    total_revenue = sum((invoice.report_subtotal for invoice in invoice_list), ZERO_MONEY)

    if request.GET.get("export") == "csv":
        rows = []
        for invoice in invoice_list:
            tax = money(invoice.report_subtotal * invoice.tax_percent / Decimal("100"))
            rows.append([
                invoice.invoice_number,
                invoice.customer.name,
                invoice.issue_date,
                invoice.report_subtotal,
                tax,
                money(invoice.report_subtotal + tax),
            ])
        return export_csv(
            "sales.csv",
            ["Invoice Number", "Customer", "Issue Date", "Subtotal", "Tax", "Total"],
            rows,
        )

    return render(request, "reports/sales.html", _report_context(
        request, form, invoices=invoice_list, total_revenue=total_revenue
    ))


@login_required
def outstanding_report(request):
    form, start_date, end_date = _date_range(request)
    queryset = Invoice.objects.filter(status__in=["issued", "paid"]).select_related("customer")
    queryset = _apply_date_range(queryset, "issue_date", start_date, end_date)
    invoices = [invoice for invoice in queryset.order_by("due_date", "invoice_number") if invoice.balance_due > 0]
    today = date.today()
    buckets = {"0-30 days": 0, "31-60 days": 0, "61+ days": 0, "No due date": 0}
    for invoice in invoices:
        invoice.days_overdue = max(0, (today - invoice.due_date).days) if invoice.due_date else None
        if invoice.days_overdue is None:
            invoice.bucket = "No due date"
        elif invoice.days_overdue <= 30:
            invoice.bucket = "0-30 days"
        elif invoice.days_overdue <= 60:
            invoice.bucket = "31-60 days"
        else:
            invoice.bucket = "61+ days"
        buckets[invoice.bucket] += 1

    if request.GET.get("export") == "csv":
        return export_csv(
            "outstanding.csv",
            ["Invoice Number", "Customer", "Issue Date", "Due Date", "Total", "Balance Due", "Days Overdue", "Bucket"],
            [[
                invoice.invoice_number,
                invoice.customer.name,
                invoice.issue_date,
                invoice.due_date,
                invoice.total,
                invoice.balance_due,
                invoice.days_overdue,
                invoice.bucket,
            ] for invoice in invoices],
        )

    return render(request, "reports/outstanding.html", _report_context(
        request, form, invoices=invoices, buckets=buckets
    ))


@login_required
def stock_report(request):
    form, _, _ = _date_range(request)
    items = list(Item.objects.all().order_by("name"))
    for item in items:
        item.report_current_stock = item.current_stock()
        item.report_is_low_stock = item.is_low_stock()
    low_stock_count = sum(item.report_is_low_stock for item in items)

    if request.GET.get("export") == "csv":
        return export_csv(
            "stock_levels.csv",
            ["SKU", "Name", "Current Stock", "Reorder Level", "Low Stock"],
            [[item.sku, item.name, item.report_current_stock, item.reorder_level, item.report_is_low_stock] for item in items],
        )

    return render(request, "reports/stock_levels.html", _report_context(
        request, form, items=items, low_stock_count=low_stock_count
    ))


@login_required
def damages_report(request):
    form, start_date, end_date = _date_range(request)
    queryset = DamageReport.objects.select_related("item", "created_by")
    queryset = _apply_date_range(queryset, "date_reported", start_date, end_date)
    records = list(queryset.order_by("-date_reported", "item__name"))
    summary = {}
    for record in records:
        item_summary = summary.setdefault(record.item, {"count": 0, "total_qty": 0, "total_loss": ZERO_MONEY})
        item_summary["count"] += 1
        item_summary["total_qty"] += record.quantity
        item_summary["total_loss"] += record.loss_value

    if request.GET.get("export") == "csv":
        return export_csv(
            "damages.csv",
            ["Date", "Item SKU", "Item Name", "Quantity", "Loss Value", "Note", "Reported By"],
            [[record.date_reported, record.item.sku, record.item.name, record.quantity, record.loss_value, record.note, record.created_by] for record in records],
        )

    return render(request, "reports/damages.html", _report_context(
        request, form, records=records, summary=summary
    ))


@login_required
def returns_report(request):
    form, start_date, end_date = _date_range(request)
    queryset = ReturnRecord.objects.select_related(
        "invoice_line__item", "invoice_line__invoice__customer", "created_by"
    )
    queryset = _apply_date_range(queryset, "date_returned", start_date, end_date)
    records = list(queryset.order_by("-date_returned"))
    by_item = defaultdict(int)
    by_customer = defaultdict(int)
    for record in records:
        by_item[record.invoice_line.item.name] += record.quantity
        by_customer[record.invoice_line.invoice.customer.name] += record.quantity
    by_item = dict(by_item)
    by_customer = dict(by_customer)

    if request.GET.get("export") == "csv":
        return export_csv(
            "returns.csv",
            ["Date", "Item", "Customer", "Invoice", "Quantity", "Restockable", "Note"],
            [[
                record.date_returned,
                record.invoice_line.item.name,
                record.invoice_line.invoice.customer.name,
                record.invoice_line.invoice.invoice_number,
                record.quantity,
                record.is_restockable,
                record.note,
            ] for record in records],
        )

    return render(request, "reports/returns.html", _report_context(
        request, form, records=records, by_item=by_item, by_customer=by_customer
    ))


@login_required
def expiry_report(request):
    form, start_date, end_date = _date_range(request)
    queryset = ExpiryWriteOff.objects.select_related("item", "created_by")
    queryset = _apply_date_range(queryset, "date_noticed", start_date, end_date)
    records = list(queryset.order_by("-date_noticed", "item__name"))
    total_qty = sum(record.quantity for record in records)
    total_loss_value = sum((record.loss_value for record in records), ZERO_MONEY)

    if request.GET.get("export") == "csv":
        return export_csv(
            "expiry.csv",
            ["Date Noticed", "Item SKU", "Item Name", "Quantity", "Loss Value", "Note", "By"],
            [[record.date_noticed, record.item.sku, record.item.name, record.quantity, record.loss_value, record.note, record.created_by] for record in records],
        )

    return render(request, "reports/expiry.html", _report_context(
        request, form, records=records, total_qty=total_qty, total_loss_value=total_loss_value
    ))


@login_required
def production_report(request):
    form, start_date, end_date = _date_range(request)
    queryset = ProductionBatch.objects.select_related("item", "created_by")
    queryset = _apply_date_range(queryset, "production_date", start_date, end_date)
    records = list(queryset.order_by("-production_date", "batch_code"))
    total_produced = sum(record.quantity_produced for record in records)

    if request.GET.get("export") == "csv":
        return export_csv(
            "production.csv",
            ["Batch Code", "Item", "Quantity Produced", "Production Date", "Expiry Date", "Note", "By"],
            [[record.batch_code, record.item.name, record.quantity_produced, record.production_date, record.expiry_date, record.note, record.created_by] for record in records],
        )

    return render(request, "reports/production.html", _report_context(
        request, form, records=records, total_produced=total_produced
    ))
