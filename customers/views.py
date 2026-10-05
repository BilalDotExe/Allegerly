from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Customer
from .forms import CustomerForm


@login_required
def customer_list(request):
    customers = Customer.objects.order_by("name")
    return render(request, "customers/list.html", {"customers": customers})


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