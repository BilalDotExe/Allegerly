from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from core.pagination import paginate
from core.permissions import FULL_ACCESS_GROUPS, group_required
from reports.forms import DateRangeForm
from reports.utils import export_csv
from .forms import BLANK_GROUP, ExpenseLineFormSet, ExpenseReportForm, group_line_forms
from .models import DEFAULT_CATEGORIES, ExpenseLine, ExpenseReport
from .services import create_report, update_report


def _unique_sorted(values):
    """Case-insensitive de-dupe that keeps the first spelling seen."""
    seen = {}
    for value in values:
        value = (value or "").strip()
        if value:
            seen.setdefault(value.lower(), value)
    return sorted(seen.values(), key=str.lower)


def _form_context(formset):
    """Category dropdown choices (starter list + everything typed before), plus
    the formset's rows grouped into category sections."""
    categories = _unique_sorted([
        *DEFAULT_CATEGORIES,
        *ExpenseLine.objects.exclude(category="").values_list("category", flat=True).distinct(),
    ])
    return {
        "category_options": categories,
        "groups": group_line_forms(formset, categories),
        "blank_group": BLANK_GROUP,
    }


@group_required(*FULL_ACCESS_GROUPS)
def expense_list(request):
    reports = ExpenseReport.objects.prefetch_related("lines")
    form = DateRangeForm(request.GET or None)
    if form.is_valid():
        if form.cleaned_data.get("start_date"):
            reports = reports.filter(report_date__gte=form.cleaned_data["start_date"])
        if form.cleaned_data.get("end_date"):
            reports = reports.filter(report_date__lte=form.cleaned_data["end_date"])

    export_params = request.GET.copy()
    export_params["export"] = "csv"
    export_query = export_params.urlencode()
    if request.GET.get("export") == "csv":
        return export_csv(
            "expense_reports.csv",
            ["Report", "Name", "Date", "Lines", "Total"],
            [[r.report_number, r.name, r.report_date, len(r.lines.all()), r.total] for r in reports],
        )

    page_obj, pagination_query = paginate(request, reports)
    return render(request, "expenses/list.html", {
        "page_obj": page_obj,
        "pagination_query": pagination_query,
        "form": form,
        "export_query": export_query,
    })


@group_required(*FULL_ACCESS_GROUPS)
def expense_create(request):
    form = ExpenseReportForm(request.POST or None)
    formset = ExpenseLineFormSet(request.POST or None)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        try:
            report = create_report(form, formset, request.user, request=request)
        except ValidationError as e:
            messages.error(request, " ".join(e.messages))
        else:
            messages.success(request, f"Expense report {report.report_number} saved.")
            return redirect("expenses:detail", pk=report.pk)
    return render(request, "expenses/form.html", {
        "form": form, "formset": formset, "title": "New Expense", **_form_context(formset),
    })


@group_required(*FULL_ACCESS_GROUPS)
def expense_detail(request, pk):
    report = get_object_or_404(ExpenseReport.objects.select_related("created_by"), pk=pk)
    return render(request, "expenses/detail.html", {
        "expense_report": report,
        "groups": report.grouped_lines(),
        "line_count": report.lines.count(),
    })


@group_required(*FULL_ACCESS_GROUPS)
def expense_edit(request, pk):
    report = get_object_or_404(ExpenseReport, pk=pk)
    form = ExpenseReportForm(request.POST or None, instance=report)
    formset = ExpenseLineFormSet(request.POST or None, instance=report)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        try:
            update_report(form, formset, request.user, request=request)
        except ValidationError as e:
            messages.error(request, " ".join(e.messages))
        else:
            messages.success(request, f"Expense report {report.report_number} updated.")
            return redirect("expenses:detail", pk=pk)
    return render(request, "expenses/form.html", {
        "form": form, "formset": formset, "title": f"Edit {report.report_number}",
        "expense_report": report, **_form_context(formset),
    })
