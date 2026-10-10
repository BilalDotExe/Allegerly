from django import template

from core.navigation import build_breadcrumbs

register = template.Library()


@register.simple_tag(takes_context=True)
def breadcrumb_trail(context):
    return build_breadcrumbs(context)
