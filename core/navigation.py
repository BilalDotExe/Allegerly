"""Sidebar structure and breadcrumb trail, built once here so the templates stay dumb."""

from django.urls import reverse

from .permissions import is_employee

# (url_name -> (section label, list url name)) per app namespace; a few
# url_names override the namespace default because they belong to another section.
_SECTIONS = {
    'customers': ('Customers', 'customers:list'),
    'vendors': ('Vendors', 'vendors:list'),
    'purchasing': ('Purchase Orders', 'purchasing:list'),
    'inventory': ('Items', 'inventory:list'),
    'invoices': ('Invoices', 'invoices:list'),
    'production': ('Production Batches', 'production:list'),
    'returns': ('Returns', 'returns:list'),
    'damages': ('Damage Reports', 'damages:list'),
    'reports': ('Reports', 'reports:index'),
    'audit': ('Audit Log', 'audit:list'),
}
_SECTION_OVERRIDES = {
    'movements': ('Stock Movements', 'inventory:movements'),
    'adjust': ('Stock Adjustment', 'inventory:adjust'),
    'expiry_list': ('Expiry Write-offs', 'inventory:expiry_list'),
    'expiry_create': ('Expiry Write-offs', 'inventory:expiry_list'),
    'credit_list': ('Credit Notes', 'invoices:credit_list'),
    'credit_detail': ('Credit Notes', 'invoices:credit_list'),
    'credit_apply': ('Credit Notes', 'invoices:credit_list'),
    'credit_refund': ('Credit Notes', 'invoices:credit_list'),
}
_PLAIN_PAGES = {
    'account_settings': 'Company settings',
    'employee_list': 'Employee accounts',
    'employee_create': 'Employee accounts',
    'employee_reset_password': 'Employee accounts',
    'employee_toggle_active': 'Employee accounts',
    'employee_delete': 'Employee accounts',
}
_LEAF_LABELS = {
    'create': 'New', 'edit': 'Edit', 'print': 'Print view', 'issue': 'Issue', 'void': 'Void',
    'payment': 'Record payment', 'receive_payment': 'Receive payment', 'statement': 'Statement',
    'statement_csv': 'Statement', 'place': 'Place order', 'receive': 'Receive goods',
    'close': 'Close', 'cancel': 'Cancel', 'credit_apply': 'Apply credit',
    'credit_refund': 'Mark refunded', 'expiry_create': 'New write-off',
    'sales': 'Sales', 'outstanding': 'Outstanding', 'stock': 'Stock', 'damages': 'Damages',
    'returns': 'Returns', 'expiry': 'Expiry', 'production': 'Production',
    'employee_create': 'New employee', 'employee_reset_password': 'Reset password',
}
# Context variable -> attribute holding a detail page's own name.
_OBJECT_LABELS = (
    ('invoice', 'invoice_number'), ('credit', 'credit_number'), ('po', 'po_number'),
    ('customer', 'name'), ('vendor', 'name'), ('item', 'name'),
)
# Detail pages the breadcrumb should link back to when you are one level deeper.
_DETAIL_URLS = {
    'invoices': 'invoices:detail', 'purchasing': 'purchasing:detail',
    'customers': 'customers:detail', 'vendors': 'vendors:detail',
    'inventory': 'inventory:detail',
}


def _object_label(context):
    for var, attr in _OBJECT_LABELS:
        obj = context.get(var)
        if obj is not None and getattr(obj, 'pk', None) and hasattr(obj, attr):
            return str(getattr(obj, attr))
    return None


def build_breadcrumbs(context):
    """List of {'label', 'url'} dicts; the last one has url=None (current page)."""
    request = context['request']
    match = request.resolver_match
    if match is None:
        return []
    name, ns = match.url_name, match.namespace
    home = {'label': 'Dashboard', 'url': reverse('dashboard'), 'home': True}
    if name == 'dashboard':
        return [{'label': 'Dashboard', 'url': None, 'home': True}]
    if name in _PLAIN_PAGES:
        if name in ('account_settings', 'employee_list'):
            return [home, {'label': _PLAIN_PAGES[name], 'url': None}]
        return [
            home,
            {'label': _PLAIN_PAGES[name], 'url': reverse('employee_list')},
            {'label': _LEAF_LABELS.get(name, name.replace('employee_', '').replace('_', ' ').title()), 'url': None},
        ]

    label, list_name = _SECTION_OVERRIDES.get(name) or _SECTIONS.get(ns) or (ns.title() if ns else 'Page', None)
    section_url = reverse(list_name) if list_name else None
    is_list = bool(list_name) and reverse(list_name) == request.path
    crumbs = [home, {'label': label, 'url': None if is_list else section_url}]
    if is_list:
        return crumbs

    obj = _object_label(context)
    if name in ('detail', 'credit_detail'):
        crumbs.append({'label': obj or 'Details', 'url': None})
    else:
        pk = match.kwargs.get('pk')
        detail_name = 'invoices:credit_detail' if name in ('credit_apply', 'credit_refund') else _DETAIL_URLS.get(ns)
        if pk and obj and detail_name:
            crumbs.append({'label': obj, 'url': reverse(detail_name, args=[pk])})
        crumbs.append({'label': _LEAF_LABELS.get(name, name.replace('_', ' ').title()), 'url': None})
    return crumbs


def _item(request, label, icon, url_name, active, show=True):
    return {'label': label, 'icon': icon, 'url': reverse(url_name), 'active': active, 'show': show}


def build_sidebar(request):
    """Grouped sidebar. Empty groups are dropped; the group holding the current page is open."""
    user = request.user
    match = request.resolver_match
    if not user.is_authenticated or match is None:
        return []
    ns, name = match.namespace, match.url_name
    full = not is_employee(user)
    credit = name in ('credit_list', 'credit_detail', 'credit_apply', 'credit_refund')
    inv_other = ns == 'inventory' and name not in ('movements', 'expiry_list', 'expiry_create', 'adjust')

    groups = [
        ('Sales', [
            _item(request, 'Invoices', 'document-text', 'invoices:list', ns == 'invoices' and not credit),
            _item(request, 'Customers', 'users', 'customers:list', ns == 'customers', full),
            _item(request, 'Returns', 'arrow-uturn-left', 'returns:list', ns == 'returns'),
        ]),
        ('Purchasing', [
            _item(request, 'Purchase Orders', 'clipboard-list', 'purchasing:list', ns == 'purchasing'),
            _item(request, 'Vendors', 'building-storefront', 'vendors:list', ns == 'vendors', full),
        ]),
        ('Inventory', [
            _item(request, 'Items', 'cube', 'inventory:list', inv_other, full),
            _item(request, 'Production Batches', 'beaker', 'production:list', ns == 'production', full),
            _item(request, 'Stock Movements', 'arrows-right-left', 'inventory:movements', name == 'movements', full),
            _item(request, 'Stock Adjustment', 'adjustments', 'inventory:adjust', name == 'adjust',
                  user.has_perm('inventory.add_stockmovement')),
        ]),
        ('Reports', [
            _item(request, 'Credit Notes', 'arrow-path', 'invoices:credit_list', credit),
            _item(request, 'Damage Reports', 'exclamation-triangle', 'damages:list', ns == 'damages'),
            _item(request, 'Expiry Write-offs', 'clock', 'inventory:expiry_list',
                  name in ('expiry_list', 'expiry_create'), full),
        ]),
        ('Insights', [
            _item(request, 'Reports', 'chart-bar', 'reports:index', ns == 'reports', full),
            _item(request, 'Audit Log', 'magnifying-glass', 'audit:list', ns == 'audit', user.has_perm('audit.view_auditlog')),
        ]),
    ]
    result = []
    for label, items in groups:
        visible = [i for i in items if i['show']]
        if visible:
            result.append({'label': label, 'items': visible, 'open': any(i['active'] for i in visible)})
    return result
