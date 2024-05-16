from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from datetime import date

from main.models import *

LAST_MAJOR_SITE_UPDATE = date(2024, 5, 29)

class StaticSitemap(Sitemap):
    priority = 0.1
    changefreq = "yearly"
    lastmod = LAST_MAJOR_SITE_UPDATE

    def items(self):
        return ["main:index", "main:hallOfFame", "main:credits"]

    def location(self, item):
        return reverse(item)


class IndexSitemap(Sitemap):
    priority = 0.2
    changefreq = "monthly"

    def items(self):
        return ["main:eventIndex", "main:robotIndex", "main:teamIndex", "main:franchiseIndex"]

    def location(self, item):
        return reverse(item)


class LeaderboardSitemap(Sitemap):
    def items(self):
        items = []
        for lb in Leaderboard.objects.values("year", "weight").order_by("-year").distinct():
            items.append("?weight=" + lb["weight"] + "&year=" + str(lb["year"]))
        return items

    def location(self, item):
        return reverse("main:leaderboard") + item


class EventSitemap(Sitemap):
    priority = 0.9
    changefreq = "yearly"

    def items(self):
        return Event.objects.all().order_by("start_date")

    def location(self, item):
        return reverse("main:eventDetail", args=[item.slug])

    def lastmod(self, item):
        return item.source_set.order_by("-last_accessed")[0].last_accessed


class RobotSitemap(Sitemap):
    priority = 0.9

    def items(self):
        return Robot.objects.all().order_by("name")

    def location(self, item):
        return reverse("main:robotDetail", args=[item.slug])

    def lastmod(self, item):
        try:
            return Source.objects.filter(event__contest__registration__version__robot=item).order_by("-last_accessed")[
                0].last_accessed
        except:
            return LAST_MAJOR_SITE_UPDATE


class TeamSitemap(Sitemap):
    priority = 0.6

    def items(self):
        return Team.objects.all().order_by("name")

    def location(self, item):
        return reverse("main:teamDetail", args=[item.slug])

    def lastmod(self, item):
        try:
            return Source.objects.filter(event__contest__registration__version__team=item).order_by("-last_accessed")[0].last_accessed
        except:
            return LAST_MAJOR_SITE_UPDATE


class FranchiseSitemap(Sitemap):
    priority = 0.4

    def items(self):
        return Franchise.objects.all().order_by("name")

    def location(self, item):
        return reverse("main:franchiseDetail", args=[item.slug])

    def lastmod(self, item):
        try:
            return Source.objects.filter(event__franchise=item).order_by("-last_accessed")[0].last_accessed
        except:
            return LAST_MAJOR_SITE_UPDATE

class ContestSitemap(Sitemap):
    priority = 0.4
    changefreq = "yearly"

    def items(self):
        return Contest.objects.all().order_by("start_date")

    def location(self, item):
        return reverse("main:contestDetail", args=[item.id])

    def lastmod(self, item):
        try:
            return Source.objects.filter(event__contest=item).order_by("-last_accessed")[0].last_accessed
        except:
            return LAST_MAJOR_SITE_UPDATE

