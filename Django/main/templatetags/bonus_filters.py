from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe

from main.models import *
from django.utils.html import format_html

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


@register.filter
def fight_result(fight, robot):
    return fight.result(robot)


@register.filter
def fight_opponents(fight, robot):
    return fight.opponents_string(robot)


@register.filter
def image_from_team(robot, team):
    return robot.get_image(team)


@register.filter
def name_from_team(robot, team):
    version = robot.get_representitive(team)
    if version.robot_name:
        return version.robot_name
    else:
        return robot.name


@register.filter
def generate_title(rob_or_ver, display_latin=True):
    flag = rob_or_ver.get_flag()
    country = rob_or_ver.country
    name = rob_or_ver.__str__()
    html_to_return = format_html('<div class="robot-title"> <img class="flag-image" src="{}" alt="{} Flag"> '
                                 '<span class="robot-title-text">{}', flag, country, name)
    latin = ""
    if display_latin and rob_or_ver.display_latin_name:
        if isinstance(rob_or_ver, Robot):
            latin = rob_or_ver.latin_name
        else:
            if rob_or_ver.latin_robot_name != "":
                latin = rob_or_ver.latin_robot_name
            else:
                latin = rob_or_ver.robot.latin_name
        html_to_return += format_html('<span class="alphanum"> ({}) </span>', latin)
    html_to_return += mark_safe('</span> </div>')
    return html_to_return
