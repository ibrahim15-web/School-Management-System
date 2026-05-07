from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def get_day(dictionary, key):
    """Return list of slots for a given day key from the day_map dict."""
    return dictionary.get(key, [])