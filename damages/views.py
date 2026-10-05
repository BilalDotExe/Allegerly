from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import redirect, render

from .forms import DamageReportForm
from .models import DamageReport
from .services import log_damage


@login_required
def damage_list(request):
    reports = DamageReport.objects.select_related("item", "invoice_line__invoice", "created_by").order_by("-date_reported", "-created_at")
    page_obj = Paginator(reports, 25).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return render(request, "damages/list.html", {"page_obj": page_obj, "pagination_query": query.urlencode()})


@login_required
def damage_create(request):
    form = DamageReportForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            log_damage(
                item=data["item"], quantity=data["quantity"],
                date_reported=data["date_reported"], created_by=request.user,
                invoice_line=data["invoice_line"], note=data["note"], request=request,
            )
            messages.success(request, "Damage report recorded.")
            return redirect("damages:list")
        except ValidationError as e:
            messages.error(request, e.message)
    return render(request, "damages/form.html", {"form": form, "title": "New Damage Report"})
