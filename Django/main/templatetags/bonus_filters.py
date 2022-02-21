import re
from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()


@register.filter
@stringfilter
def page_url(get_data):
    get_data = re.sub("&?page=[0-9]*", "", get_data)
    if "?" not in get_data:
        get_data = "?" + get_data
    if len(get_data) > 1:
        get_data += "&"
    return get_data
