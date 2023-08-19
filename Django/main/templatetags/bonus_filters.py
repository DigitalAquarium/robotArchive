from django import template
from django.template.defaultfilters import stringfilter

from main.models import *

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
def fights_event_number(fights, this_fight):
    this_event_fights = fights.filter(contest__event=this_fight.contest.event)
    if this_event_fights.first() != this_fight:
        return -1
    else:
        return len(this_event_fights)


@register.filter
def fight_opponents(fight, robot):
    return fight.opponents_string(robot)


@register.filter
def image_from_team(robot,team):
    return robot.get_image(team)

@register.filter
def name_from_team(robot,team):
    version = robot.get_representitive(team)
    if version.robot_name:
        return version.robot_name
    else:
        return robot.name