from django import template
from config.i18n import text

register = template.Library()


@register.simple_tag
def b(english, russian):
    return text(english, russian)
