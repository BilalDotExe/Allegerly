"""Shared list pagination: one page size for every list screen."""

from django.core.paginator import Paginator

PAGE_SIZE = 10


def paginate(request, queryset, per_page=PAGE_SIZE):
    """Return (page_obj, query_string_without_page) for list templates."""
    page_obj = Paginator(queryset, per_page).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return page_obj, query.urlencode()
