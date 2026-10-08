from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import Vendor
from .forms import VendorForm
from core.pagination import paginate
from core.permissions import FULL_ACCESS_GROUPS, group_required
from core.utils import format_us_phone
from reports.utils import export_csv


@group_required(*FULL_ACCESS_GROUPS)
def vendor_list(request):
    vendors = Vendor.objects.order_by("name")
    export_params = request.GET.copy()
    export_params["export"] = "csv"
    export_query = export_params.urlencode()
    if request.GET.get("export") == "csv":
        return export_csv(
            "vendors.csv",
            ["Name", "Contact person", "Phone", "Email", "Category", "Tax ID", "Terms", "Amount Owed", "Status"],
            [[
                vendor.name,
                vendor.contact_person,
                format_us_phone(vendor.phone),
                vendor.email,
                vendor.get_category_display(),
                vendor.tax_id,
                vendor.get_payment_terms_display(),
                vendor.outstanding_payable(),
                "Active" if vendor.is_active else "Inactive",
            ] for vendor in vendors],
        )
    page_obj, pagination_query = paginate(request, vendors)
    return render(request, "vendors/list.html", {
        "page_obj": page_obj,
        "pagination_query": pagination_query,
        "export_query": export_query,
    })


@group_required(*FULL_ACCESS_GROUPS)
def vendor_create(request):
    form = VendorForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Vendor created.")
        return redirect("vendors:list")
    return render(request, "vendors/form.html", {"form": form, "title": "New Vendor"})


@group_required(*FULL_ACCESS_GROUPS)
def vendor_detail(request, pk):
    vendor = get_object_or_404(Vendor, pk=pk)
    return render(request, "vendors/detail.html", {
        "vendor": vendor,
        "recent_orders": vendor.purchase_orders.all()[:10],
    })


@group_required(*FULL_ACCESS_GROUPS)
def vendor_edit(request, pk):
    vendor = get_object_or_404(Vendor, pk=pk)
    form = VendorForm(request.POST or None, instance=vendor)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Vendor updated.")
        return redirect("vendors:detail", pk=pk)
    return render(request, "vendors/form.html", {"form": form, "title": "Edit Vendor"})
