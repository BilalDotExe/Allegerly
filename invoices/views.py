from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from .models import Invoice, CreditNote
from .forms import InvoiceForm, InvoiceLineFormSet, PaymentForm, VoidInvoiceForm, MarkRefundedForm
from .services import issue_invoice, void_invoice, record_payment, apply_credit
from audit.services import log as audit_log


def _pagination_query(request):
    query = request.GET.copy()
    query.pop("page", None)
    return query.urlencode()


@login_required
def invoice_list(request):
    invoices = Invoice.objects.select_related("customer").order_by("-created_at")
    page_obj = Paginator(invoices, 25).get_page(request.GET.get("page"))
    return render(request, "invoices/list.html", {"page_obj": page_obj, "pagination_query": _pagination_query(request)})


@login_required
def invoice_create(request):
    form = InvoiceForm(request.POST or None)
    formset = InvoiceLineFormSet(request.POST or None)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        invoice = form.save(commit=False)
        invoice.created_by = request.user
        invoice.save()
        formset.instance = invoice
        formset.save()
        messages.success(request, f"Invoice {invoice.invoice_number} created.")
        return redirect("invoices:detail", pk=invoice.pk)
    return render(request, "invoices/form.html", {
        "form": form,
        "formset": formset,
        "title": "New Invoice",
    })


@login_required
def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related("customer", "created_by"), pk=pk)
    lines = invoice.lines.select_related("item")
    payments = invoice.payments.select_related("created_by")
    credit_notes = invoice.credit_notes.select_related("customer")
    return render(request, "invoices/detail.html", {
        "invoice": invoice,
        "lines": lines,
        "payments": payments,
        "credit_notes": credit_notes,
    })


@login_required
def invoice_issue(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if request.method == "POST":
        try:
            issue_invoice(invoice, request.user, request=request)
            messages.success(request, f"Invoice {invoice.invoice_number} issued.")
        except ValidationError as e:
            messages.error(request, e.message)
    return redirect("invoices:detail", pk=pk)


@login_required
@permission_required("invoices.change_invoice", raise_exception=True)
def invoice_void(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    form = VoidInvoiceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            void_invoice(invoice, request.user, form.cleaned_data["reason"], request=request)
            messages.success(request, f"Invoice {invoice.invoice_number} voided.")
            return redirect("invoices:detail", pk=pk)
        except ValidationError as e:
            messages.error(request, e.message)
    return render(request, "invoices/void_form.html", {"form": form, "invoice": invoice})


@login_required
def payment_create(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    form = PaymentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            record_payment(
                invoice=invoice,
                amount=form.cleaned_data["amount"],
                method=form.cleaned_data["method"],
                payment_date=form.cleaned_data["payment_date"],
                user=request.user,
                note=form.cleaned_data.get("note", ""),
                request=request,
            )
            messages.success(request, "Payment recorded.")
            return redirect("invoices:detail", pk=pk)
        except ValidationError as e:
            messages.error(request, e.message)
    return render(request, "invoices/payment_form.html", {"form": form, "invoice": invoice})


@login_required
def credit_list(request):
    credits = CreditNote.objects.select_related("customer", "invoice").order_by("-created_at")
    page_obj = Paginator(credits, 25).get_page(request.GET.get("page"))
    return render(request, "invoices/credit_list.html", {"page_obj": page_obj, "pagination_query": _pagination_query(request)})


@login_required
def credit_detail(request, pk):
    credit = get_object_or_404(CreditNote.objects.select_related("customer", "invoice"), pk=pk)
    applications = credit.applications.select_related("invoice")
    return render(request, "invoices/credit_detail.html", {
        "credit": credit,
        "applications": applications,
    })


@login_required
def credit_apply(request, pk):
    credit = get_object_or_404(CreditNote, pk=pk)

    # Build a simple form to pick an invoice and amount
    from django import forms as django_forms
    from core.forms import BootstrapForm
    class _ApplyForm(BootstrapForm):
        invoice = django_forms.ModelChoiceField(
            queryset=Invoice.objects.filter(
                customer=credit.customer,
                status__in=["issued", "paid"]
            )
        )
        amount = django_forms.DecimalField(max_digits=10, decimal_places=2)

    form = _ApplyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            apply_credit(
                credit_note=credit,
                invoice=form.cleaned_data["invoice"],
                amount=form.cleaned_data["amount"],
                user=request.user,
                request=request,
            )
            messages.success(request, "Credit applied.")
            return redirect("invoices:credit_detail", pk=pk)
        except ValidationError as e:
            messages.error(request, e.message)
    return render(request, "invoices/credit_apply.html", {"form": form, "credit": credit})


@login_required
@permission_required("invoices.change_creditnote", raise_exception=True)
def credit_mark_refunded(request, pk):
    credit = get_object_or_404(CreditNote, pk=pk)
    form = MarkRefundedForm(request.POST or None)
    if not credit.is_applied or credit.is_refunded:
        messages.error(request, "Only fully applied, unrefunded credit notes can be marked refunded.")
        return redirect("invoices:credit_detail", pk=pk)
    if request.method == "POST" and form.is_valid():
        credit.is_refunded = True
        credit.refund_method = form.cleaned_data["refund_method"]
        credit.refund_date = form.cleaned_data["refund_date"]
        credit.save()
        audit_log(request.user, "credit_refunded", credit, changes={"method": credit.refund_method}, request=request)
        messages.success(request, "Credit note marked as refunded.")
        return redirect("invoices:credit_detail", pk=pk)
    return render(request, "invoices/credit_refund.html", {"form": form, "credit": credit})
