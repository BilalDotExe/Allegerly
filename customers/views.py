from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Customer
from .forms import CustomerForm
from reports.utils import export_csv


@login_required
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
                customer.phone,
                customer.email,
                customer.balance,
                "Active" if customer.is_active else "Inactive",
            ] for customer in customers],
        )
    return render(request, "customers/list.html", {
        "customers": customers,
        "export_query": export_query,
    })


@login_required
def customer_create(request):
    form = CustomerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Customer created.")
        return redirect("customers:list")
    return render(request, "customers/form.html", {"form": form, "title": "New Customer"})


@login_required
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    return render(request, "customers/detail.html", {"customer": customer})


@login_required
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    form = CustomerForm(request.POST or None, instance=customer)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Customer updated.")
        return redirect("customers:detail", pk=pk)
    return render(request, "customers/form.html", {"form": form, "title": "Edit Customer"})
