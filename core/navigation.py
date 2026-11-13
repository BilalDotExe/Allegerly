"""Sidebar groups and breadcrumbs, built from one table so the two always agree.

Each item lists the pages it owns in `match`: a bare namespace ("customers") owns
every page in that app, "namespace:url_name" owns just that page.
"""
from django.urls import reverse

NAV_GROUPS = [
    {"key": "manage", "label": "Manage", "items": [
        {"label": "Customers", "icon": "fa-users", "url": "customers:list",
         "match": ["customers"], "staff_only": True},
        {"label": "Vendors", "icon": "fa-truck", "url": "vendors:list",
         "match": ["vendors"], "staff_only": True},
        {"label": "Purchase Orders", "icon": "fa-clipboard-list", "url": "purchasing:list",
         "match": ["purchasing"]},
        {"label": "Expenses", "icon": "fa-wallet", "url": "expenses:list",
         "match": ["expenses"], "staff_only": True},
        {"label": "Items", "icon": "fa-boxes-stacked", "url": "inventory:list",
         "match": ["inventory:list", "inventory:create", "inventory:detail", "inventory:edit"], "staff_only": True},
        {"label": "Invoices", "icon": "fa-file-invoice-dollar", "url": "invoices:list",
         "match": ["invoices:list", "invoices:create", "invoices:detail", "invoices:print",
                   "invoices:issue", "invoices:void", "invoices:payment"]},
        {"label": "Production Batches", "icon": "fa-flask", "url": "production:list",
         "match": ["production"], "staff_only": True},
    ]},
    {"key": "returns", "label": "Returns & write-offs", "items": [
        {"label": "Returns", "icon": "fa-rotate-left", "url": "returns:list", "match": ["returns"]},
        {"label": "Credit Notes", "icon": "fa-receipt", "url": "invoices:credit_list",
         "match": ["invoices:credit_list", "invoices:credit_detail", "invoices:credit_apply", "invoices:credit_refund"]},
        {"label": "Damage Reports", "icon": "fa-triangle-exclamation", "url": "damages:list", "match": ["damages"]},
        {"label": "Expiry Write-offs", "icon": "fa-hourglass-end", "url": "inventory:expiry_list",
         "match": ["inventory:expiry_list", "inventory:expiry_create"], "staff_only": True},
    ]},
    {"key": "insights", "label": "Insights", "items": [
        {"label": "Stock Movements", "icon": "fa-right-left", "url": "inventory:movements",
         "match": ["inventory:movements"], "staff_only": True},
        {"label": "Reports", "icon": "fa-chart-column", "url": "reports:index", "match": ["reports"], "staff_only": True},
        {"label": "Stock Adjustment", "icon": "fa-sliders", "url": "inventory:adjust",
         "match": ["inventory:adjust"], "perm": "inventory.add_stockmovement"},
        {"label": "Audit Log", "icon": "fa-clock-rotate-left", "url": "audit:list", "match": ["audit"], "perm": "audit.view_auditlog"},
    ]},
]

# Pages reached from the account menu rather than the sidebar.
ACCOUNT_PAGES = {
    "account_settings": [("Company settings", None)],
    "employee_list": [("Employee accounts", None)],
    "employee_create": [("Employee accounts", "employee_list"), ("New", None)],
    "employee_reset_password": [("Employee accounts", "employee_list"), ("Reset password", None)],
}

# The last breadcrumb for pages below a section's list page.
LEAF_LABELS = {
    "create": "New", "expiry_create": "New", "detail": "Details", "credit_detail": "Details",
    "edit": "Edit", "print": "Print", "payment": "Payment", "receive_payment": "Receive payment",
    "statement": "Statement", "credit_apply": "Apply credit", "credit_refund": "Refund",
    "issue": "Issue", "void": "Void", "place": "Place order", "receive": "Receive",
    "close": "Close", "cancel": "Cancel", "stock": "Stock levels",
}


def _owns(item, namespace, url_name):
    return f"{namespace}:{url_name}" in item["match"] or namespace in item["match"]


def _visible(item, user, employee):
    if item.get("staff_only") and employee:
        return False
    return not item.get("perm") or user.has_perm(item["perm"])


def build_navigation(request, employee):
    """`nav_groups`, `nav_dashboard_active` and `breadcrumbs` for the templates.

    `employee` is passed in (not looked up) so a page asks the database once.
    """
    user = request.user
    match = request.resolver_match
    namespace = (match.namespace if match else "") or ""
    url_name = (match.url_name if match else "") or ""

    groups, breadcrumbs = [], []
    for group in NAV_GROUPS:
        items = []
        for item in group["items"]:
            if not _visible(item, user, employee):
                continue
            active = bool(match) and _owns(item, namespace, url_name)
            items.append({**item, "href": reverse(item["url"]), "active": active})
            if active:
                breadcrumbs = [{"label": group["label"], "href": None},
                               {"label": item["label"], "href": reverse(item["url"])}]
                if url_name != item["url"].split(":")[1]:
                    leaf = LEAF_LABELS.get(url_name, url_name.replace("_", " ").capitalize())
                    breadcrumbs.append({"label": leaf, "href": None})
        if items:
            groups.append({"key": group["key"], "label": group["label"], "items": items,
                           "has_active": any(i["active"] for i in items)})

    if not breadcrumbs:
        if url_name in ACCOUNT_PAGES:
            breadcrumbs = [{"label": "Account", "href": None}] + [
                {"label": label, "href": reverse(name) if name else None} for label, name in ACCOUNT_PAGES[url_name]]
        else:
            breadcrumbs = [{"label": "Dashboard", "href": None}]
    breadcrumbs[-1]["href"] = None  # the current page is never a link

    return {"nav_groups": groups, "nav_dashboard_active": url_name == "dashboard" and not namespace,
            "breadcrumbs": breadcrumbs}
