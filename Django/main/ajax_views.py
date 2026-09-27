from collections import defaultdict

from .views import get_current_site
from django.http import JsonResponse, HttpResponse
from django.urls import reverse

from .forms import *

from os import environ

YT_API_KEY = environ["YOUTUBE_API_KEY"]


def disclaimer(request):
    if get_current_site(request).id == 2:
        return JsonResponse({"txt": "Russia"}, status=200)
    else:
        return JsonResponse({"txt": "2014"}, status=200)


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
            "fight__contest__start_date", "fight__contest__end_date", "fight__contest__id", "fight__number").exclude(
            fight__method__in=["NW", "WU"])
        site = get_current_site(request).id
        if site == 2:
            fight_versions.filter(fight__contest__event__site = get_current_site(request).id)
        rank = 1000
        fights = [{"name": "Initial Rank", "rank": 1000, "year": None, "event_name": None, "href": None}]
        history = [1000]
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

    except:
        return JsonResponse({"robot_slug": robot_slug}, status=400)


def yt_video_status(_, fight_id):
    fight = Fight.objects.get(pk=fight_id)
    return JsonResponse(fight.get_youtube_data(), status=200)


def win_method_statistics(request):
    robot = request.GET.get("robot") or None
    contest = request.GET.get("contest") or None
    event = request.GET.get("event") or None
    franchise = request.GET.get("franchise") or None
    fights = Fight.objects.filter(fight_type__in=["FC", "NS"])

    if robot is not None:
        won = request.GET.get("won") or None
        if won is None:
            return HttpResponse("Malformed Request, won parameter required if robot selected", status=400)
        won = True if won == "True" or won == "1" or won == "true" else False
        fights_query = fights.filter(fight_version__version__robot__slug=robot, fight_version__won=won)
        fights = []
        if won:
            for fight in fights_query:
                if fight.fight_version_set.filter(won=True).count() < 2:
                    fights.append(fight)
        else:
            for fight in fights_query:
                if fight.fight_version_set.all().count() == 2:
                    fights.append(fight)

    elif contest is not None:
        try:
            contest = Contest.objects.get(pk=contest)
        except:
            return HttpResponse("Specified Contest not found", status=404)
        fights = fights.filter(contest=contest)

    elif event is not None:
        try:
            event = Event.objects.get(pk=event)
        except:
            return HttpResponse("Specified Event not found", status=404)
        fights = fights.filter(contest__event=event)

    elif franchise is not None:
        try:
            franchise = Franchise.objects.get(pk=franchise)
        except:
            return HttpResponse("Specified Franchise not found", status=404)
        fights = fights.filter(contest__event__franchise=franchise)

    else:
        pass
        # fights already set up above

    if len(fights) == 0:
        return HttpResponse("No fights exist for specified query", status=404)

    raw_data = [f.method for f in fights]
    json_data = defaultdict(int)
    for item in raw_data:
        json_data[item] += 1

    cluster_map = {
        "DK": "Knockout",
        "KO": "Knockout",
        "TO": "Knockout",
        "PN": "Control",
        "JD": "Decision",
        "CV": "Decision",
        "OA": "Control",
        "PT": "Control",
        "DR": "_",
        "WU": "_",
        "NW": "_",
        "NM": "_",
        "OT": "OT"
    }
    order = {
        "DK": 1,
        "KO": 2,
        "TO": 3,
        "PN": 10,
        "JD": 20,
        "CV": 21,
        "OA": 11,
        "PT": 12,
        "DR": 40,
        "WU": 41,
        "NW": 42,
        "NM": 43,
        "OT": 50
    }

    clusters = defaultdict(int)
    for k, v in json_data.items():
        clusters[cluster_map[k]] += v

    json_data = {k: v for k, v in sorted(json_data.items(), key=lambda x: order[x[0]])}
    json_data = {k: v for k, v in sorted(json_data.items(), key=lambda x: -clusters[cluster_map[x[0]]])}
    total = sum(json_data.values())
    for k in ["DR", "WU", "NW", "NM"]:
        if k in json_data:
            total -= json_data[k]
    json_data["pie_total"] = total
    return JsonResponse(json_data, status=200)