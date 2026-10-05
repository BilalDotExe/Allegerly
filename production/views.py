from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import redirect, render

from .forms import ProductionBatchForm
from .models import ProductionBatch
from .services import create_production_batch


@login_required
def production_list(request):
    batches = ProductionBatch.objects.select_related("item", "created_by").order_by("-production_date", "-created_at")
    page_obj = Paginator(batches, 25).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return render(request, "production/list.html", {"page_obj": page_obj, "pagination_query": query.urlencode()})


@login_required
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
