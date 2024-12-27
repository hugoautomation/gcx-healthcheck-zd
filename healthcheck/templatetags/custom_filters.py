from django import template
import re

register = template.Library()


@register.filter
def split_camel_case(value):
    """
    Splits camel case string into separate words.
    Example: 'TicketForms' -> 'Ticket Forms'
    """
    return re.sub(r"(?<!^)(?=[A-Z])", " ", value)
