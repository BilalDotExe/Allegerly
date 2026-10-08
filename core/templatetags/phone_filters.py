from django import template

from core.utils import format_us_phone

register = template.Library()


@register.filter(name="us_phone")
def us_phone(value):
    return format_us_phone(value)
