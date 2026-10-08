from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from core.pagination import PAGE_SIZE
from core.permissions import FULL_ACCESS_GROUPS, group_required
from django.shortcuts import redirect, render

from .forms import ProductionBatchForm
from .models import ProductionBatch
from .services import create_production_batch
from reports.utils import export_csv


@group_required(*FULL_ACCESS_GROUPS)
def production_list(request):
    batches = ProductionBatch.objects.select_related("item", "created_by").order_by("-production_date", "-created_at")
    export_params = request.GET.copy()
    export_params["export"] = "csv"
    export_query = export_params.urlencode()
    if request.GET.get("export") == "csv":
        return export_csv(
            "production_batches.csv",
            ["Batch", "Item", "Quantity", "Production Date", "Expiry Date", "Note", "By"],
            [[
                batch.batch_code,
                batch.item.name,
                batch.quantity_produced,
                batch.production_date,
                batch.expiry_date,
                batch.note,
                batch.created_by,
            ] for batch in batches],
        )

    page_obj = Paginator(batches, PAGE_SIZE).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return render(request, "production/list.html", {
        "page_obj": page_obj,
        "pagination_query": query.urlencode(),
        "export_query": export_query,
    })


@group_required(*FULL_ACCESS_GROUPS)
def production_create(request):
    form = ProductionBatchForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            batch = create_production_batch(
                item=data["item"], quantity_produced=data["quantity_produced"],
                production_date=data["production_date"], created_by=request.user,
                expiry_date=data["expiry_date"], note=data["note"], request=request,
            )
            messages.success(request, f"Production batch {batch.batch_code} recorded.")
            return redirect("production:list")
        except ValidationError as e:
            messages.error(request, e.message)
    return render(request, "production/form.html", {"form": form, "title": "New Production Batch"})
