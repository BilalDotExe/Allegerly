from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import render, get_object_or_404, redirect

from core.money import money
from invoices.services import (
    allocate_oldest_first, open_invoices_oldest_first, record_customer_payment,
)
from core.models import CompanyProfile
from .models import Customer
from .forms import CustomerForm, ReceivePaymentForm
from .statement import build_statement
from core.pagination import paginate
from core.permissions import FULL_ACCESS_GROUPS, group_required
from core.utils import format_us_phone
from reports.utils import export_csv


@group_required(*FULL_ACCESS_GROUPS)
def customer_list(request):
    customers = Customer.objects.order_by("name")
    export_params = request.GET.copy()
    export_params["export"] = "csv"
    export_query = export_params.urlencode()
    if request.GET.get("export") == "csv":
        return export_csv(
            "customers.csv",
            ["Name", "Phone", "Email", "Balance", "Status"],
            [[
                customer.name,
                format_us_phone(customer.phone),
                customer.email,
                customer.outstanding_balance(),
                "Active" if customer.is_active else "Inactive",
            ] for customer in customers],
        )
    page_obj, pagination_query = paginate(request, customers)
    return render(request, "customers/list.html", {
        "page_obj": page_obj,
        "pagination_query": pagination_query,
        "export_query": export_query,
    })


@group_required(*FULL_ACCESS_GROUPS)
def customer_create(request):
    form = CustomerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Customer created.")
        return redirect("customers:list")
    return render(request, "customers/form.html", {"form": form, "title": "New Customer"})


@group_required(*FULL_ACCESS_GROUPS)
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    invoices = customer.invoices.prefetch_related("lines").order_by("-issue_date", "-created_at")
    return render(request, "customers/detail.html", {
        "customer": customer,
        "invoices": invoices,
        "can_receive_payment": bool(open_invoices_oldest_first(customer)),
    })


@group_required(*FULL_ACCESS_GROUPS)
def customer_statement_csv(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    rows, closing_balance = build_statement(customer)
    return export_csv(
        f"statement-{customer.name.replace(' ', '-').lower()}.csv",
        ["Date", "Description", "Reference", "Charge", "Payment/Credit", "Balance"],
        [[
            row.date, row.description, row.reference,
            row.debit or "", row.credit or "", row.balance,
        ] for row in rows] + [["", "", "", "", "Balance due", closing_balance]],
    )


@group_required(*FULL_ACCESS_GROUPS)
def customer_statement_print(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    rows, closing_balance = build_statement(customer)
    return render(request, "customers/statement_print.html", {
        "customer": customer,
        "rows": rows,
        "closing_balance": closing_balance,
        "company": CompanyProfile.load(),
    })


@group_required(*FULL_ACCESS_GROUPS)
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    form = CustomerForm(request.POST or None, instance=customer)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Customer updated.")
        return redirect("customers:detail", pk=pk)
    return render(request, "customers/form.html", {"form": form, "title": "Edit Customer"})


def _parse_amount(raw):
    """A row amount from POST: blank means 0. Returns (Decimal, error message or None)."""
    raw = (raw or "").strip().replace(",", "").lstrip("$")
    if not raw:
        return Decimal("0.00"), None
    try:
        value = money(Decimal(raw))
    except (InvalidOperation, ValueError):
        return Decimal("0.00"), "Enter a number."
    if value < 0:
        return Decimal("0.00"), "Can't be negative."
    return value, None


@group_required(*FULL_ACCESS_GROUPS)
def customer_receive_payment(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    invoices = open_invoices_oldest_first(customer)
    form = ReceivePaymentForm(request.POST or None)
    rows = [{"invoice": inv, "value": "", "error": None} for inv in invoices]
    extra_error = None

    if request.method == "POST":
        amounts = {}
        for row in rows:
            row["value"] = request.POST.get(f"pay_{row['invoice'].pk}", "").strip()
            amount, row["error"] = _parse_amount(row["value"])
            if not row["error"] and amount > row["invoice"].balance_due:
                row["error"] = f"More than the ${row['invoice'].balance_due} owed."
            if amount > 0:
                amounts[row["invoice"]] = amount

        if form.is_valid() and not any(r["error"] for r in rows):
            received = form.cleaned_data["amount_received"]
            if not amounts:
                # Nothing typed against individual invoices: apply the lump sum oldest first.
                if not received:
                    extra_error = "Enter an amount received, or an amount against at least one invoice."
                else:
                    allocation, leftover = allocate_oldest_first(invoices, received)
                    if leftover > 0:
                        extra_error = (
                            f"${received} is more than the ${customer.outstanding_balance()} this customer owes."
                        )
                    amounts = {inv: allocation[inv.pk] for inv in invoices if inv.pk in allocation}
            elif received and money(received) != sum(amounts.values()):
                extra_error = (
                    f"Amount received (${money(received)}) doesn't match the invoice amounts "
                    f"(${sum(amounts.values())}). Clear the invoice amounts to apply it oldest first."
                )

            if not extra_error:
                try:
                    record_customer_payment(
                        customer, amounts,
                        method=form.cleaned_data["method"],
                        payment_date=form.cleaned_data["payment_date"],
                        user=request.user,
                        note=form.cleaned_data.get("note", ""),
                        request=request,
                    )
                except ValidationError as e:
                    extra_error = e.messages[0]
                else:
                    count = len(amounts)
                    messages.success(
                        request,
                        f"Payment of ${sum(amounts.values())} recorded across "
                        f"{count} invoice{'s' if count != 1 else ''}.",
                    )
                    return redirect("customers:detail", pk=pk)

    return render(request, "customers/receive_payment.html", {
        "customer": customer,
        "form": form,
        "rows": rows,
        "extra_error": extra_error,
        "total_owed": sum((inv.balance_due for inv in invoices), Decimal("0.00")),
    })
