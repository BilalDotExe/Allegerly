from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render
from django.utils.dateparse import parse_date

from core.pagination import paginate
from reports.utils import export_csv

from .models import AuditLog


def _change_items(changes):
    if isinstance(changes, dict):
        return [(str(k).replace("_", " ").capitalize(), str(val)) for k, val in changes.items()]
    return [("Details", str(changes))] if changes else []


@login_required
@permission_required("audit.view_auditlog", raise_exception=True)
def audit_list(request):
    logs = AuditLog.objects.select_related("user").all()
    action = request.GET.get("action", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    if action:
        logs = logs.filter(action=action)
    parsed_from = parse_date(date_from) if date_from else None
    parsed_to = parse_date(date_to) if date_to else None
    if parsed_from:
        logs = logs.filter(timestamp__date__gte=parsed_from)
    if parsed_to:
        logs = logs.filter(timestamp__date__lte=parsed_to)

    export_params = request.GET.copy()
    export_params["export"] = "csv"
    export_query = export_params.urlencode()
    if request.GET.get("export") == "csv":
        return export_csv(
            "audit_log.csv",
            ["Timestamp", "User", "Action", "Object", "Changes", "IP"],
            [[
                entry.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                entry.user or "-",
                entry.action,
                f"{entry.object_type} #{entry.object_id}\n{entry.object_repr}",
                "; ".join(f"{k}: {val}" for k, val in _change_items(entry.changes)) or "-",
                entry.ip_address or "-",
            ] for entry in logs],
        )

    page_obj, pagination_query = paginate(request, logs)
    for entry in page_obj:
        entry.change_items = _change_items(entry.changes)
    actions = AuditLog.objects.order_by("action").values_list("action", flat=True).distinct()
    return render(request, "audit/list.html", {
        "page_obj": page_obj,
        "actions": actions,
        "selected_action": action,
        "date_from": date_from,
        "date_to": date_to,
        "pagination_query": pagination_query,
        "export_query": export_query,
    })
