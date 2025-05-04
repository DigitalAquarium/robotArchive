import time

from .views import get_current_site
from django.http import JsonResponse
from django.urls import reverse
from django.utils.html import escape

from .forms import *

from googleapiclient.discovery import build
import googleapiclient.errors
from os import environ

YT_API_KEY = environ["YOUTUBE_API_KEY"]


def disclaimer(request):
    if get_current_site(request).id == 2:
        return JsonResponse({"txt": "Russia"}, status=200)
    else:
        return JsonResponse({"txt": "2006"}, status=200)


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
                                                      fight__contest__event__site=get_current_site(request).id,
                                                      fight__fight_type__in=["FC", "NS"]).order_by(
            "fight__contest__start_date", "fight__contest__end_date", "fight__contest__id", "fight__number").exclude(
            fight__method__in=["NW", "WU"])
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


def yt_video_status(request, fight_id):
    Fight.objects.filter(external_media__contains="youtube.com").update(media_type="YT")

    if request.ipinfo.ip == "127.0.0.1":
        req_country = "GB"
    else:
        req_country = request.ipinfo.country

    url = Fight.objects.get(pk=fight_id).external_media
    with build("youtube", "v3", developerKey=environ["YOUTUBE_API_KEY"]) as yt_api:
        if "?" in url:
            split_media = url[26:].split("?start=")
            t = int(split_media[1])
            vid_id = split_media[0]
        else:
            vid_id = url[26:]
            t = 0
        response = yt_api.videos().list(
            part="snippet,status,contentDetails",
            fields="items(snippet(title,thumbnails),status(embeddable),contentDetails(regionRestriction))",
            id=vid_id
        ).execute()

    allowed_countries = []
    blocked_countries = []
    embeddable = response['items'][0]["status"]["embeddable"]
    if len(response['items'][0]["contentDetails"]) > 0:
        if "allowed" in response['items'][0]["contentDetails"]["regionRestriction"]:
            allowed_countries = response['items'][0]["contentDetails"]["regionRestriction"]["allowed"]
        else:
            blocked_countries = response['items'][0]["contentDetails"]["regionRestriction"]["blocked"]
    thumb = list(response['items'][0]["snippet"]["thumbnails"].items())[-1][1]["url"]
    if t == 0:
        start = ""
    elif t < 60:
        start = str(t) + " seconds"
    elif t < 3600:
        start = str(t // 60) + "m"
        if t % 60 != 0:
            start += str(t % 60) + "s"
    else:
        start = str(t // 3600) + "h"
        if t % 3600 != 0:
            start += str(t % 3600) + "m"
        if t % 60 != 0:
            start += str(t % 60) + "s"
    title = response['items'][0]["snippet"]["title"]
    if start != "":
        title = title + " @ " + start
    title = escape(title)
    return JsonResponse({"allowed_countries": allowed_countries,
                         "blocked_countries": blocked_countries,
                         "embeddable": embeddable,
                         "title": title,
                         "thumb": thumb,
                         "url": "https://youtube.com/watch/" + vid_id + ("?t=" + str(t) if t else ""),
                         }, status=200)
