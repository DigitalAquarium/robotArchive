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
    #try:
    robot = Robot.objects.get(slug=robot_slug)
    fight_versions = Fight_Version.objects.filter(version__robot=robot,
                                                  fight__fight_type__in=["FC", "NS"]).order_by(
        "fight__contest__start_date", "fight__contest__end_date", "fight__contest__id", "fight__number").exclude(
        fight__method__in=["NW", "WU"])
    rank = 1000
    fights = [{"name": "Initial Rank", "rank": 1000, "year": None, "event_name": None, "href": None}]
    history = [1000]
    print(1000 + sum([x.ranking_change for x in fight_versions]))
    thingy = Fight_Version.objects.filter(version__robot=robot)
    calculated_rank = 1000 + sum([x.ranking_change for x in thingy])
    print("~~~~~~~~~~~~~~~~~~~~~~~~~~~" +str(robot) + " " + str(thingy[0].version.robot.ranking) + " " + str(
        calculated_rank) + "~~~~~~~~~~~~~~~~~~~~~~~~~~~")

    '''test_fvs = thingy.exclude(fight__fight_type__in=["FC", "NS"],fight__method__in=
                              ["KO","DK","JD","CV","TO","OA","PT","DR","NM","OT"])
    print(len(thingy),len(fight_versions))
    for fv in test_fvs:
        print(fv.fight,fv.fight.fight_type,fv.ranking_change)'''
    for fv in fight_versions:
        rank += fv.ranking_change

        fight = {'name': str(fv.fight),
                 'rank': rank,
                 'year': fv.fight.contest.event.start_date.year,
                 'event_name': fv.fight.contest.event.name,
                 'href': reverse("main:fightDetail", args=[fv.fight.id])
                 }
        fights.append(fight)
        history.append(rank)
    return JsonResponse({"fights": fights, "history": history}, status=200)

    #except:
   #     return JsonResponse({"robot_slug": robot_slug}, status=400)
