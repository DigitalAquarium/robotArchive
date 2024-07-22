from math import log2

import pycountry
from django.db import models

COUNTRY_CHOICES = []
for c in pycountry.countries:
    COUNTRY_CHOICES.append((c.alpha_2, c.name))
COUNTRY_CHOICES.sort(key=lambda x: x[1])

BEST_FINISH_CHOICES = [
    (1, "Champion"),
    (2, "Runner Up"),
    (4, "Semi-Finalist"),
    (8, "Quarter-Finalist"),
    (16, "Round of 16"),
    (32, "Round of 32"),
    (64, "Qualifiers"),
    (128, "Alternate")
]

WEAPON_TYPE_CHOICES = [
    ("NM", "Meltybrain"),

    ("HH", "Horizontal Spinner"),
    ("HU", "Undercutter"),
    ("HO", "Overhead Spinner"),
    ("HS", "Shell Spinner"),
    ("HR", "Ring Spinner"),

    ("VV", "Vertical Spinner"),
    ("VD", "Drum Spinner"),
    ("VE", "Eggbeater"),

    ("SP", "Propeller Spinner"),
    ("SN", "Angled Spinner"),
    ("SR", "Articulated Spinner"),

    ("AA", "Axe"),
    ("AH", "Horizontal Axe"),
    ("AS", "Hammersaw"),

    ("ES", "Spear"),
    ("EC", "Cannon"),

    ("LL", "Lifter"),
    ("GG", "Grabber"),
    ("GH", "Horizontal Grabber"),
    ("GL", "Grabber-Lifter"),
    ("CC", "Crusher"),
    ("CH", "Horizontal Crusher"),

    ("FR", "Flipper"),
    ("FF", "Front-Hinged Flipper"),
    ("FS", "Side-Hinged Flipper"),

    # M Misc - now actually abrasive things
    ("MS", "Saw"),
    ("MN", "Chainsaw"),
    ("MD", "Drill"),

    ("IM", "Interchangeable / Multibot"),

]
WEAPON_TYPE_SIMILARITY = {
    "AH": ["AA", "GH", "CH"],
    "AS": ["AA", "AH", "MS"],
    "LL": ["GL"],
    "GG": ["GH", "GL", "CC", "CH"],
    "GH": ["GG", "CC", "CH", "AH"],
    "GL": ["GG", "LL"],
    "CC": ["GH", "GG", "CH"],
    "CH": ["GH", "GG", "CC", "AH"],
    "MS": ["MN", "MD", "AS"]
}


class BattleBot(models.Model):
    name = models.CharField(blank=False, max_length=255)
    image = models.ImageField(upload_to='images', blank=True)
    debut = models.PositiveSmallIntegerField(blank=False)
    weapon_type = country = models.CharField(max_length=2, choices=WEAPON_TYPE_CHOICES, blank=False)
    best_finish = models.PositiveSmallIntegerField(choices=BEST_FINISH_CHOICES, blank=False)
    country = models.CharField(max_length=2, choices=COUNTRY_CHOICES, blank=False, default="US")
    primaryColour = models.CharField(blank=False, max_length=20)
    secondaryColour = models.CharField(blank=True, max_length=20)

    def __str__(self):
        return self.name

    def match(self, otherBot):
        if otherBot.primaryColour == self.primaryColour or otherBot.primaryColour == self.secondaryColour:
            if otherBot.secondaryColour == self.primaryColour or otherBot.secondaryColour == self.secondaryColour:
                colour = "match"
            else:
                colour = "close"
        else:
            if otherBot.secondaryColour == self.primaryColour or otherBot.secondaryColour == self.secondaryColour:
                colour = "close"
            else:
                colour = "fail"

        if otherBot.debut == self.debut:
            debut = "match"
        elif abs(otherBot.debut - self.debut) == 1:
            debut = "close"
        else:
            debut = "fail"

        if otherBot.weapon_type == self.weapon_type:
            weapon = "match"
        elif otherBot.weapon_type in WEAPON_TYPE_SIMILARITY.keys():
            if self.weapon_type in WEAPON_TYPE_SIMILARITY[otherBot.weapon_type]:
                weapon = "close"
            else:
                weapon = "fail"
        elif otherBot.weapon_type[0] == self.weapon_type[0]:
            weapon = "close"
        else:
            weapon = "fail"

        if otherBot.best_finish == self.best_finish:
            finish = "match"
        elif abs(log2(otherBot.best_finish) - log2(self.best_finish)) == 1:
            finish = "close"
        else:
            finish = "fail"

        response = {
            "victory": otherBot == self,
            "letter": "match" if otherBot.name[0] == self.name[0] else "fail",
            "debut": debut,
            "weapon": weapon,
            "finish": finish,
            "country": "match" if otherBot.country == self.country else "fail",
            "colour": colour,
        }
        return response


class HiddenBot(models.Model):
    day = models.CharField(unique=True,blank=False, max_length=3)
    bot = models.ForeignKey("BattleBot", on_delete=models.SET_NULL, null=True)
    def __str__(self):
        return "Hidden bot for " + self.day + " " + ("NULL" if not self.bot else str(self.bot))
