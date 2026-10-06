from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from .models import Item, StockMovement, ExpiryWriteOff
from .forms import ItemForm, ExpiryWriteOffForm, StockAdjustmentForm
from inventory.services import adjust_stock
from reports.utils import export_csv


@login_required
def item_list(request):
    items = Item.objects.order_by("name")
    export_params = request.GET.copy()
    export_params["export"] = "csv"
    export_query = export_params.urlencode()
    if request.GET.get("export") == "csv":
        return export_csv(
            "items.csv",
            ["SKU", "Name", "Cost Price", "Sale Price", "Stock", "Reorder Level"],
            [[
                item.sku,
                item.name,
                item.cost_price,
                item.sale_price,
                item.current_stock(),
                item.reorder_level,
            ] for item in items],
        )
    return render(request, "inventory/list.html", {
        "items": items,
        "export_query": export_query,
    })


@login_required
def item_create(request):
    form = ItemForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Item created.")
        return redirect("inventory:list")
    return render(request, "inventory/form.html", {"form": form, "title": "New Item"})


@login_required
def item_detail(request, pk):
    item = get_object_or_404(Item, pk=pk)
    movements = item.movements.select_related("created_by").order_by("-created_at")[:50]
    return render(request, "inventory/detail.html", {"item": item, "movements": movements})


@login_required
def item_edit(request, pk):
    item = get_object_or_404(Item, pk=pk)
    form = ItemForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Item updated.")
        return redirect("inventory:detail", pk=pk)
    return render(request, "inventory/form.html", {"form": form, "title": "Edit Item"})


@login_required
def movements_list(request):
    movements = StockMovement.objects.select_related("item", "created_by").order_by("-created_at")[:200]
    export_params = request.GET.copy()
    export_params["export"] = "csv"
    export_query = export_params.urlencode()
    if request.GET.get("export") == "csv":
        return export_csv(
            "stock_movements.csv",
            ["Date", "Item SKU", "Type", "Quantity", "Note", "By"],
            [[
                movement.created_at.strftime("%Y-%m-%d %H:%M"),
                movement.item.sku,
                movement.get_movement_type_display(),
                movement.quantity,
                movement.note,
                movement.created_by,
            ] for movement in movements],
        )
    return render(request, "inventory/movements.html", {
        "movements": movements,
        "export_query": export_query,
    })


@login_required
def expiry_list(request):
    writeoffs = ExpiryWriteOff.objects.select_related("item", "created_by").order_by("-created_at")
    export_params = request.GET.copy()
    export_params["export"] = "csv"
    export_query = export_params.urlencode()
    if request.GET.get("export") == "csv":
        return export_csv(
            "expiry_writeoffs.csv",
            ["Date Noticed", "Item", "Quantity", "Loss Value", "Note", "By"],
            [[
                writeoff.date_noticed,
                writeoff.item.sku,
                writeoff.quantity,
                writeoff.loss_value,
                writeoff.note,
                writeoff.created_by,
            ] for writeoff in writeoffs],
        )
    return render(request, "inventory/expiry_list.html", {
        "writeoffs": writeoffs,
        "export_query": export_query,
    })


@login_required
def expiry_create(request):
    form = ExpiryWriteOffForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        writeoff = form.save(commit=False)
        writeoff.created_by = request.user
        writeoff.save()
        messages.success(request, "Expiry write-off recorded.")
        return redirect("inventory:expiry_list")
    return render(request, "inventory/expiry_form.html", {"form": form, "title": "New Expiry Write-off"})


@login_required
@permission_required("inventory.add_stockmovement", raise_exception=True)
def stock_adjust(request):
    form = StockAdjustmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        adjust_stock(
        item=form.cleaned_data["item"],
        quantity=form.cleaned_data["quantity"],
        reason=form.cleaned_data["note"],
        created_by=request.user,
    )
        messages.success(request, "Stock adjusted.")
        return redirect("inventory:list")
    return render(request, "inventory/adjust.html", {"form": form, "title": "Manual Stock Adjustment"})
