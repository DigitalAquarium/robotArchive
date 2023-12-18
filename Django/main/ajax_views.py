from django.http import JsonResponse
from django.urls import reverse

from .forms import *


def get_location(request):
    id = request.GET.get("id") or ""
    try:
        id = int(id)
        l = Location.objects.get(id=id)
        return JsonResponse({"name": l.name, "latitude": l.latitude, "longitude": l.longitude}, status=200)
    except:
        return JsonResponse({"id": id}, status=400)


def get_history(request):
    robot_slug = request.GET.get("robot_slug")
    try:
        robot = Robot.objects.get(slug=robot_slug)
        fight_versions = Fight_Version.objects.filter(version__robot=robot,
                                                      fight__fight_type__in=["FC", "NS"]).order_by(
            "fight__contest__event__start_date", "fight__contest__id", "fight__number")
        rank = 1000
        fights = [{"name": "Initial Rank", "rank": 1000, "year": None, "event_name": None, "href": None}]
        history = [1000]
        for fv in fight_versions:
            rank += fv.ranking_change
            fight = {}
            fight['name'] = str(fv.fight)
            fight['rank'] = rank
            fight['year'] = fv.fight.contest.event.start_date.year
            fight['event_name'] = fv.fight.contest.event.name
            fight['href'] = reverse("main:fightDetail", args=[fv.fight.id])
            fights.append(fight)
            history.append(rank)
        return JsonResponse({"fights": fights, "history": history}, status=200)

    except:
        return JsonResponse({"robot_slug": robot_slug}, status=400)
