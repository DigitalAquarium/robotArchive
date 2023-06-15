import re
import pycountry
import datetime
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify
import uuid

FULL_COMBAT = 'FC'
SPORTSMAN = 'SP'
PLASTIC = 'PL'
NON_COMBAT = 'NC'
FIGHT_TYPE_CHOICES = [
    (FULL_COMBAT, "Full Combat"),
    (SPORTSMAN, "Sportsman"),
    (PLASTIC, "Plastic"),
    (NON_COMBAT, "Non-Combat"),
]

COUNTRY_CHOICES = []
for country in pycountry.countries:
    COUNTRY_CHOICES.append((country.alpha_2, country.name))
COUNTRY_CHOICES.extend([
    ('XE', "England"),
    ('XS', "Scotland"),
    ('XW', "Wales"),
    ('XI', "Northern Ireland"),
])
COUNTRY_CHOICES.sort(key=lambda x: x[1])
COUNTRY_CHOICES = [('XX', "Unspecified")] + COUNTRY_CHOICES

LEADERBOARD_WEIGHTS = [
    ("A", "UK Antweight / US Fairyweight"),
    ("U", "US Antweight"),
    ("B", "Beetleweight"),
    ("Y", "Hobbyweight"),
    ("F", "Featherweight"),
    ("L", "Lightweight"),
    ("M", "Middleweight"),
    ("H", "Heavyweight"),
    ("S", "Super Heavyweight"),
    ("X", "Not Leaderboard Valid"),
]


def get_flag(code):
    return settings.STATIC_URL + "flags/4x3/" + code.lower() + ".svg"

def make_slug(slug_text,queryset):
    SLUG_LENGTH = 50
    slug_text = slugify(slug_text[:50])
    if queryset.filter(slug=slug_text).count() > 0:
        uu = "-" + str(uuid.uuid4())
        slug_text = slug_text[:50-len(uu)] + uu
    return slug_text


class Person(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    email = models.EmailField()
    public = models.BooleanField(default=True)

    def can_edit(self, user):
        p = Person.objects.get(user=user)
        return p == self or user.is_staff

    def __str__(self):
        if self.public:
            return self.name
        elif self.user is not None:
            return self.user.__str__()
        else:
            return "Unidentified Person#" + str(self.pk)


class Team(models.Model):
    name = models.CharField(max_length=255)
    logo = models.ImageField(upload_to='team_logos/%Y/', blank=True)
    country = models.CharField(max_length=2, choices=COUNTRY_CHOICES, blank=False, default="XX")
    members = models.ManyToManyField(Person, through="Person_Team")
    slug = models.SlugField(max_length=50)

    def __str__(self):
        return self.name

    def get_flag(self):
        return get_flag(self.country)

    def get_logo_url(self):
        if self.logo:
            return self.logo.url
        if Version.objects.filter(team=self).count() > 0:
            for version in Version.objects.filter(team=self).order_by("-last_fought"):
                if version.image:
                    return version.image.url
        return settings.STATIC_URL + "unknown.png"

    def robots(self):
        return Robot.objects.filter(version__team=self).distinct()

    def can_edit(self, user):
        p = Person.objects.get(user=user)
        return p in self.members.all() or user.is_staff

    def slugify(self):
        if self.slug is not None and self.slug != "": return self.slug
        slug_text = self.name
        if slug_text[:5].lower() == "team ":
            slug_text = slug_text[5:]
        self.slug = make_slug(slug_text,Team.objects.all())
        self.save()
        return self.slug


class Weight_Class(models.Model):
    LEADERBOARD_VALID = [(150, "UK Antweight / US Fairyweight"),
                         (454, "US Antweight"),
                         (1361, "Beetleweight"),
                         (6000, "Hobbyweight"),  # Should this be 5553 to remove 15lbs
                         (13608, "Featherweight"),
                         (27212, "Lightweight"),
                         (50000, "Middleweight"),
                         (100000, "Heavyweight"),
                         (154221, "Super Heavyweight"),
                         ]
    LEADERBOARD_VALID_GRAMS = [x[0] for x in LEADERBOARD_VALID]
    name = models.CharField(max_length=30)
    weight_grams = models.PositiveIntegerField()
    recommended = models.BooleanField(default=False)

    class Meta:
        ordering = ["-recommended", "weight_grams"]

    def __str__(self):
        return self.name + ": " + self.weight_string()

    def weight_string(self):
        if self.weight_grams < 400:
            return str(self.weight_grams) + "g"
        elif self.weight_grams < 1000:
            if self.weight_grams == 454:
                return "1lb"
            else:
                return str(self.weight_grams) + "g"
        elif self.weight_grams < 20000:
            if self.weight_grams % 1000 == 0:
                return str(self.weight_grams // 1000) + "kg"
            elif self.weight_grams % 10 == 0:
                return str(round(self.weight_grams / 1000, 1)) + "kg"
            else:
                return str(self.to_lbs()) + "lbs"
        else:
            if self.weight_grams % 1000 == 0:
                return str(self.weight_grams // 1000) + "kg"
            else:
                return str(self.to_lbs()) + "lbs"

    def metric_string(self):
        if self.weight_grams < 1000:
            return str(self.weight_grams) + "g"
        elif self.weight_grams < 10000:
            return str(round(self.weight_grams / 1000, 2)) + "kg"
        elif self.weight_grams < 20000:
            return str(round(self.weight_grams / 1000, 1)) + "kg"
        else:
            return str(round(self.weight_grams / 1000)) + "kg"

    def imperial_string(self):
        if self.weight_grams < 454:
            return str(self.weight_grams) + "g"
        elif self.weight_grams == 454:
            return "1lb"
        else:
            return str(self.to_lbs()) + "lbs"

    def to_lbs(self):
        return round(self.weight_grams / 453.59237)

    def find_lb_class(self):
        grams = self.weight_grams
        BOUNDARY_AMOUNT = 0.21
        nearest_weight_class = min(Weight_Class.LEADERBOARD_VALID_GRAMS, key=lambda x: abs(x - grams))
        if abs(nearest_weight_class - grams) <= nearest_weight_class * BOUNDARY_AMOUNT:
            # This class is close enough to a valid weight class
            return LEADERBOARD_WEIGHTS[Weight_Class.LEADERBOARD_VALID_GRAMS.index(nearest_weight_class)][0]
        else:
            return "X"

    def __eq__(self, other):
        if isinstance(other, Weight_Class):
            return self.weight_grams == other.weight_grams
        else:
            return self.weight_grams == other

    def __lt__(self, other):
        if isinstance(other, Weight_Class):
            return self.weight_grams < other.weight_grams
        else:
            return self.weight_grams < other

    def __le__(self, other):
        if isinstance(other, Weight_Class):
            return self.weight_grams <= other.weight_grams
        else:
            return self.weight_grams <= other

    def __gt__(self, other):
        if isinstance(other, Weight_Class):
            return self.weight_grams > other.weight_grams
        else:
            return self.weight_grams > other

    def __ge__(self, other):
        if isinstance(other, Weight_Class):
            return self.weight_grams >= other.weight_grams
        else:
            return self.weight_grams >= other


class Robot(models.Model):
    RANKING_DEFAULT = 1000
    name = models.CharField(max_length=255)
    name_alphanum = models.CharField(max_length=255, blank=True)
    slug = models.SlugField(max_length=60, allow_unicode=True)
    requires_translation = models.BooleanField(default=False)

    country = models.CharField(max_length=2, choices=COUNTRY_CHOICES, blank=False, default="XX")
    description = models.TextField(blank=True)
    wins = models.IntegerField(default=0)
    losses = models.IntegerField(default=0)
    ranking = models.FloatField(default=RANKING_DEFAULT)
    lb_weight_class = models.CharField(max_length=1, choices=LEADERBOARD_WEIGHTS, default="X")
    opt_out = models.BooleanField(default=False)  # for opting out of rankings
    first_fought = models.DateField(blank=True, null=True)
    last_fought = models.DateField(blank=True, null=True)

    def __str__(self):
        return self.name

    def slugify(self):
        if self.slug is not None and self.slug != "": return self.slug
        def try_save_slug(slug):
            if Robot.objects.filter(slug=slug).count() == 0:
                self.slug = slug
                self.save()
                return True
            else:
                return False

        SLUG_LEN = 60
        # <38 chars of name>-<2 wc>-<12 country>-<5 hex number> = 38 + 2 + 12 + 5 + 3 (dashes) = 60 else:
        # <23 chars of name> + "-" + <uuid 36> = 60
        if self.slug != "":
            return self.slug
        if self.country[0] not in ["XE","XS","XW","XI","XX"]:
            if self.country not in ["GB","US","KP","KR","CD","RU","SY"] and len(pycountry.countries.get(alpha_2=self.country).name) <= 12:
                countryslug = slugify(pycountry.countries.get(alpha_2=self.country).name)
            elif self.country in ["GB","US","KP","KR","CD","RU","SY"]:
                if self.country == "GB":
                    countryslug = "uk"
                elif self.country == "US":
                    countryslug = "usa"
                elif self.country == "KP":
                    countryslug = "north-korea"
                elif self.country == "KR":
                    countryslug = "south-korea"
                elif self.country == "CD":
                    countryslug = "dr-congo"
                elif self.country == "RU":
                    countryslug = "russia"
                elif self.country == "SY":
                    countryslug = "syria"
            else:
                countryslug = self.country.lower()
        else:
            if self.country == "XE":
                countryslug = "england"
            elif self.country == "XS":
                countryslug = "scotland"
            elif self.country == "XW":
                countryslug = "wales"
            elif self.country == "XI":
                countryslug = "nireland"
            else:
                countryslug = "unknown"

        if self.lb_weight_class != "X":
            wc_slug = self.lb_weight_class.lower() + "w"
        else:
            wc_slug = self.version_set.first().weight_class.find_lb_class().lower() + "w"

        wc_slug = "-" + wc_slug
        countryslug = "-" + countryslug
        nameslug = slugify(self.name[:SLUG_LEN])
        if len(nameslug) == 0:
            nameslug = slugify(self.name_alphanum[:SLUG_LEN])
        slug = nameslug
        if try_save_slug(slug): return slug

        if Robot.objects.filter(slug=slug).exclude(country=self.country).count() == 0:
            slug = slug[:SLUG_LEN - 3] + wc_slug
            if try_save_slug(slug): return slug

        slug = nameslug[:SLUG_LEN - len(countryslug)] + countryslug
        if try_save_slug(slug): return slug

        slug = nameslug[:SLUG_LEN - len(countryslug) - len(wc_slug)] + countryslug + wc_slug
        if try_save_slug(slug): return slug

        if len(slug) >= 54:
            slug = nameslug[:SLUG_LEN - len(countryslug) - len(wc_slug) - 6] + countryslug + wc_slug

        count = Robot.objects.get(slug__contains=slug)
        count_slug = "-" + hex(count)[2:] # Should allow for over 1 million duplicate name, wc, country sets
        if len(count_slug) <= 5:
            if try_save_slug(slug + count_slug): return slug
            for i in range(2,count+2):
                #Try to grab slugs from any robots that have been deleted, as there can be a discrepancy between the amount of slugs avalible and the count
                count_slug = "-" + hex(i)[2:]
                if try_save_slug(slug + count_slug): return slug


        #Nuclear Option, If this is not unique then something has gone seriously wrong
        uuid_slug = "-" + str(uuid.uuid4())
        slug = nameslug[:SLUG_LEN-len(uuid_slug)] + uuid_slug
        self.slug = slug
        self.save()
        return slug

    @staticmethod
    def get_by_rough_weight(wc):
        BOUNDARY_AMOUNT = 0.21
        upper_bound = wc + (wc * BOUNDARY_AMOUNT)
        lower_bound = wc - (wc * BOUNDARY_AMOUNT)
        classes = Weight_Class.objects.filter(weight_grams__lte=upper_bound, weight_grams__gte=lower_bound)
        robs = Robot.objects.filter(version__weight_class__in=classes).distinct()
        return robs

    def set_alphanum(self, commit=True):
        self.name_alphanum = asciify(self.name, "Robot", self.id)
        if commit:
            self.save()

    def remove_rank_from(self, date):
        fvs = Fight_Version.objects.filter(version__robot=self, fight__contest__event__start_date__gte=date)
        for fv in fvs:
            self.ranking -= fv.ranking_change

    def get_flag(self):
        return get_flag(self.country)

    def awards(self):
        awards = []
        for ver in self.version_set.all():
            awards += Award.objects.filter(version=ver)
        return awards

    def can_edit(self, user):
        last = self.version_set.all().last()
        return last.can_edit(user) or user.is_staff


class Version(models.Model):
    robot_name = models.CharField(max_length=255, blank=True)
    robot_name_alphanum = models.CharField(max_length=255, blank=True)
    name = models.CharField(max_length=255, blank=True)
    requires_translation = models.BooleanField(default=False)

    country = models.CharField(max_length=2, choices=COUNTRY_CHOICES, blank=False, default="XX")
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='robot_images/%Y/', blank=True)
    weapon_type = models.CharField(max_length=20)
    first_fought = models.DateField(blank=True, null=True)
    last_fought = models.DateField(blank=True, null=True)

    robot = models.ForeignKey(Robot, on_delete=models.CASCADE)
    owner = models.ForeignKey(Person, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, blank=True, null=True)
    weight_class = models.ForeignKey(Weight_Class, on_delete=models.SET(1))

    def set_alphanum(self, commit=True):
        self.name_alphanum = asciify(self.name, "Version", self.id)
        self.robot_name_alphanum = asciify(self.robot_name, "Version", self.id)
        if commit:
            self.save()

    def get_alphanum(self):
        if self.robot_name != "":
            return self.robot_name_alphanum
        else:
            return self.robot.name_alphanum

    def get_flag(self):
        return get_flag(self.country)

    def __str__(self):
        if self.robot_name != "":
            return self.robot_name
        else:
            return self.robot.name

    def get_full_name(self):
        # TODO: check where __str__ is used and should use this instead
        if self.robot_name != "":
            return self.robot_name + " " + self.name
        else:
            return self.robot.name + " " + self.name

    def can_edit(self, user):
        return self.owner.can_edit(user) or self.robot.version_set.last().owner.can_edit(user)


class Franchise(models.Model):
    name = models.CharField(max_length=50)
    logo = models.ImageField(upload_to='franchise_logos/%Y/', blank=True)
    description = models.TextField(blank=True)
    members = models.ManyToManyField(Person, through="Person_Franchise")
    slug = models.SlugField(max_length=50)

    def slugify(self):
        if self.slug is not None and self.slug != "": return self.slug
        self.slug = make_slug(self.name, Franchise.objects.all())
        self.save()
        return self.slug

    def is_member(self, person):
        return len(Person_Franchise.objects.filter(person=person, franchise=self)) > 0

    def __str__(self):
        return self.name

    def can_edit(self, user):
        p = Person.objects.get(user=user)
        return p in self.members.all() or user.is_staff

    def get_logo_url(self):
        if self.logo:
            return self.logo.url
        if Event.objects.filter(franchise=self)[0].country != "XX":
            return Event.objects.filter(franchise=self)[0].get_flag()
        return settings.STATIC_URL + "unknown.png"


class Event(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='event_logos/%Y/', blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    registration_open = models.DateTimeField()
    registration_close = models.DateTimeField()
    country = models.CharField(max_length=2, choices=COUNTRY_CHOICES, blank=False, default="XX")
    latitude = models.FloatField()
    longitude = models.FloatField()
    location_name = models.CharField(max_length=255,default="Undefined")
    franchise = models.ForeignKey(Franchise, on_delete=models.CASCADE)
    slug = models.SlugField(max_length=50)

    def slugify(self):
        if self.slug is not None and self.slug != "": return self.slug
        self.slug = make_slug(self.name, Event.objects.all())
        self.save()
        return self.slug

    def __str__(self):
        return self.name

    def available_weight_classes(self):
        return Weight_Class.objects.filter(contest__event=self).distinct().order_by("weight_grams")

    @staticmethod
    def get_by_rough_weight(wc):
        upper_bound = wc + (wc * 0.21)
        lower_bound = wc - (wc * 0.21)
        classes = Weight_Class.objects.filter(weight_grams__lte=upper_bound, weight_grams__gte=lower_bound)
        return Event.objects.filter(contest__weight_class__in=classes).distinct()

    def get_flag(self):
        return get_flag(self.country)

    def is_registration_open(self):
        return self.registration_open < timezone.now() < self.registration_close and not self.is_registration_full()

    def is_registration_past(self):
        return timezone.now() > self.registration_close

    def is_registration_full(self):
        for c in self.contest_set.all():
            if not c.is_registration_full():
                return False
        return True

    def is_one_day(self):
        return self.start_date == self.end_date

    def can_edit(self, user):
        return self.franchise.can_edit(user)

    def get_logo_url(self): #TODO: Make a thing similar to this for robots & versoins?
        if self.logo:
            return self.logo.url
        if self.franchise.logo:
            return self.franchise.logo.url
        if self.country != "XX":
            return self.get_flag()
        return settings.STATIC_URL + "unknown.png"


class Contest(models.Model):
    name = models.CharField(max_length=255, blank=True)
    fight_type = models.CharField(max_length=2, choices=FIGHT_TYPE_CHOICES + [("MU", "Multiple Types")])
    # auto_awards = models.BooleanField()
    entries = models.PositiveSmallIntegerField(default=0)
    reserves = models.PositiveSmallIntegerField(default=0, blank=True)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    weight_class = models.ForeignKey(Weight_Class, on_delete=models.SET(1))

    def __str__(self):
        if self.name is not None and self.name != "":
            return self.name
        else:
            return self.weight_class.name

    def is_registration_open(self):
        return self.event.is_registration_open()

    def is_registration_past(self):
        return self.event.is_registration_past()

    def is_registration_full(self):
        return self.entries != 0 and (self.registration_set.count() >= self.entries + self.reserves)

    def can_edit(self, user):
        return self.event.franchise.can_edit(user)


class Registration(models.Model):  # Idea for future: Add a team limit to reservations.
    signup_time = models.DateTimeField(auto_now_add=True)
    approved = models.BooleanField(default=False)
    reserve = models.BooleanField(default=False)
    version = models.ForeignKey(Version, on_delete=models.CASCADE)
    signee = models.ForeignKey(Person, on_delete=models.CASCADE)
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE)

    def can_edit(self, user):
        return self.contest.can_edit(user)

    def can_delete(self, user):
        p = Person.objects.get(user=user)
        return self.can_edit or p == self.signee

    def __str__(self):
        return str(self.version) + " @ " + str(self.contest)


class Fight(models.Model):
    METHOD_CHOICES = [
        ("KO", "Knockout"),
        ("JD", "Judge's Decision"),
        ("TO", "Tap Out"),
        ("OA", "Out of the Arena"),
        ("PT", "Pit"),
        ("DR", "Draw"),
        ("WU", "Winner Unknown"),
        ("NW", "No Winner Declared"),
        ("NM", "Method not Declared"),
        ("OT", "Other Win Method")
    ]
    MEDIA_CHOICES = [
        ("XX", "No Media / Error"),
        ("LI", "Local Image"),
        ("EI", "External Image"),
        ("LV", "Local Video"),
        ("IF", "Iframe embed"),  # Such as YouTube or Vimeo
        ("IG", "Instagram"),
        ("TW", "Twitter"),
        ("TT", "Tiktok"),
        ("FB", "Facebook"),
        ("UN", "Unknown"),
    ]

    method = models.CharField(max_length=2, choices=METHOD_CHOICES, default="NM")
    name = models.CharField(max_length=255, blank=True)
    fight_type = models.CharField(max_length=2, choices=FIGHT_TYPE_CHOICES)
    number = models.IntegerField()
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE)
    competitors = models.ManyToManyField(Version, through="Fight_Version")
    media_type = models.CharField(max_length=2, choices=MEDIA_CHOICES, default="UN")
    internal_media = models.FileField(upload_to='fight_media/%Y/', blank=True)
    external_media = models.URLField(blank=True)

    def calculate(self, commit=True):
        K = 25
        fvs = self.fight_version_set.all()
        numBots = len(fvs)
        numWinners = len(self.winners())
        if self.fight_type == "FC" and (numWinners > 0 or self.method == "DR"):
            tag = False
            for fv in fvs:
                if fv.tag_team != 0:
                    tag = True
                    break

            if numBots == 2:
                q1 = 10 ** (fvs[0].version.robot.ranking / 400)
                q2 = 10 ** (fvs[1].version.robot.ranking / 400)
                expected1 = q1 / (q1 + q2)
                if fvs[0].won:
                    score1 = 1
                elif numWinners == 0:
                    score1 = 0.5
                else:
                    score1 = 0
                change = K * (score1 - expected1)
                fvs[0].version.robot.ranking += change
                fvs[0].ranking_change = change
                fvs[1].version.robot.ranking -= change
                fvs[1].ranking_change = -change

            elif not tag and numWinners > 0:
                # Take an amount of points for a loss against the average of the group, divided by the number of robots
                # off each robot and then add fair share of that back to the winners. makes it a low stakes loss, but
                # still a win equal to a normal fight if you're the only winner of the rumble
                averageRank = 0
                for fv in fvs:
                    averageRank += fv.version.robot.ranking / numBots
                averageQ = 10 ** (averageRank / 400)
                pool = 0
                for i in range(numBots):
                    q = 10 ** (fvs[i].version.robot.ranking / 400)
                    averageExpected = averageQ / (averageQ + q)
                    change = (K * (1 - averageExpected)) / numBots
                    pool += change
                    fvs[i].version.robot.ranking -= change
                    fvs[i].ranking_change = -change

                for i in range(numBots):  # Distribute this based on amount of elo maybe
                    if fvs[i].won == 1:
                        fvs[i].version.robot.ranking += pool / numWinners
                        fvs[i].ranking_change += pool / numWinners

            else:
                tteams = []
                tteams_key = {}
                for i in range(numBots):  # Sort fvs into teams in a 2D array
                    try:
                        tteams[tteams_key[fvs[i].tag_team]].append(fvs[i])
                    except KeyError:
                        tteams_key[fvs[i].tag_team] = len(tteams)
                        tteams.append([fvs[i]])

                tteamsAvg = []
                for tt in tteams:
                    tavg = 0
                    for fv in tt:
                        tavg += fv.version.robot.ranking
                    tavg /= len(tteams)
                    tteamsAvg.append(tavg)

                if len(tteams) == 2:
                    q1 = 10 ** (tteamsAvg[0] / 400)
                    q2 = 10 ** (tteamsAvg[1] / 400)
                    expected1 = q1 / (q1 + q2)
                    if tteams[0][0].won:
                        score1 = 1
                    elif numWinners == 0:
                        score1 = 0.5
                    else:
                        score1 = 0
                    change = K * (score1 - expected1)
                    for fv in tteams[0]:
                        fv.ranking_change = change / len(tteams[0])
                        fv.version.robot.ranking += change / len(tteams[0])
                    for fv in tteams[1]:
                        fv.ranking_change = -change / len(tteams[1])
                        fv.version.robot.ranking -= change / len(tteams[1])

                elif numWinners > 0:
                    averageRank = 0
                    for i in range(len(tteams)):
                        averageRank += tteamsAvg[i] / numBots
                    averageQ = 10 ** (averageRank / 400)
                    pool = 0
                    for i in range(len(tteams)):
                        q = 10 ** (tteamsAvg[i] / 400)
                        averageExpected = averageQ / (averageQ + q)
                        change = (K * (1 - averageExpected)) / len(tteams)
                        pool += change
                        for fv in tteams[i]:
                            fv.version.robot.ranking -= change
                            fv.ranking_change = -change

                    for i in range(len(tteams)):
                        if fvs[i].won == 1:
                            fvs[i].version.robot.ranking += pool / numWinners
                            fvs[i].ranking_change += pool / numWinners

        if numBots == 2 and numWinners == 1 and self.fight_type in ["FC", "SP", "PL"]:
            for fv in fvs:
                if fv.won:
                    fv.version.robot.wins += 1
                else:
                    fv.version.robot.losses += 1

        # Update when fought
        vupdateFlag = False
        for fv in fvs:
            if not fv.version.first_fought or fv.version.first_fought > fv.fight.contest.event.start_date:
                fv.version.first_fought = fv.fight.contest.event.start_date
                vupdateFlag = True
            if not fv.version.robot.first_fought or fv.version.robot.first_fought > fv.fight.contest.event.start_date:
                fv.version.robot.first_fought = fv.fight.contest.event.start_date

            if not fv.version.last_fought or fv.version.last_fought < fv.fight.contest.event.end_date:
                fv.version.last_fought = fv.fight.contest.event.end_date
                vupdateFlag = True
            if not fv.version.robot.last_fought or fv.version.robot.last_fought < fv.fight.contest.event.end_date:
                fv.version.robot.last_fought = fv.fight.contest.event.end_date

        if commit:
            for fv in fvs:
                if vupdateFlag:
                    fv.version.save()
                fv.version.robot.save()
                fv.save()
        return fvs

    def format_external_media(self):  # TODO: Youtube Shorts
        if re.match("(https?://)?(www\.)?youtu\.?be",
                    self.external_media) is not None and "/embed/" not in self.external_media:
            get_info = self.external_media[
                       re.match("(https?://)?(www\.)?youtu((\.be/)|(be\.com/watch))", self.external_media).end():]
            video_id = re.search("((\?v=)|(&v=))[a-zA-Z0-9\-_]*", get_info)
            if video_id is None:
                video_id = get_info[:11]
            else:
                video_id = video_id.group()[3:]

            start_time = re.search("((\?t=)|(&t=))[0-9]*", get_info)
            if start_time is None:
                start_time = ""
            else:
                start_time = "?start=" + start_time.group()[3:]

            self.external_media = "https://youtube.com/embed/" + video_id + start_time

        elif "twitch.tv/" in self.external_media:
            get_data = self.external_media[25:]

    def set_media_type(self):
        self.media_type = "XX"
        self.save()
        if bool(self.internal_media):
            # https://developer.mozilla.org/en-US/docs/Web/Media/Formats/Containers
            if self.internal_media.url[-4:] == ".mp4" or self.internal_media.url[-4:] == ".ogg":
                self.media_type = "LV"
            elif self.internal_media.url[-5:] == ".webm":
                self.media_type = "LV"
            else:
                # Local Image
                self.media_type = "LI"

        elif self.external_media is not None:
            if "twitter" in self.external_media:
                self.media_type = "TW"
            elif "tiktok" in self.external_media:
                self.media_type = "TT"
            elif "instagram" in self.external_media:
                self.media_type = "IG"
            elif "facebook" in self.external_media:
                self.media_type = "FB"
            elif "archive.org" in self.external_media and "web.archive.org" not in self.external_media:
                self.media_type = "IF"
            elif re.search("youtu\.?be", self.external_media) is not None:
                self.media_type = "IF"
            # https://developer.mozilla.org/en-US/docs/Web/Media/Formats/Image_types
            elif self.external_media[-4:].lower() in [".gif", ".jpg", ".pjp", ".gif", ".png", ".svg"]:
                self.media_type = "EI"
            elif self.external_media[-5:].lower() in [".jpeg", ".jfif", ".webp"]:
                self.media_type = "EI"
            elif self.external_media[-6:].lower() == ".pjpeg":
                self.media_type = "EI"
            else:
                self.media_type = "UN"
        self.save()

    def has_video(self):
        return self.media_type in ["LV", "IF", "IG", "TW", "TT", "FB"]

    def get_tt_id(self):
        # https: // www.tiktok.com / @ battlebots / video / 7060864801462963502 - Example video
        output = ""
        for i in range(len(self.external_media) - 1, 0, -1):
            if self.external_media[i] not in ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]:
                break
            output = self.external_media[i] + output
        return output

    def teams(self):
        teams = []
        for fv in self.fight_version_set.all().order_by("tag_team"):
            if fv.tag_team != 0:
                try:
                    teams[fv.tag_team - 1].append(fv.version)
                except IndexError:
                    teams.append([fv.version])
        return teams

    def winners(self):
        winners = []
        for fv in self.fight_version_set.all():
            if fv.won == 1:
                winners.append(fv.version)
        return winners

    def result(self, r):
        fv = Fight_Version.objects.get(version__robot=r, fight=self)
        if fv.won:
            if len(self.competitors.filter(fight_version__won=1)) == 1 or fv.tag_team != 0:
                return "Won"
            else:
                return "Qualified"
        else:
            if self.method in ["KO", "JD", "TO", "OA", "PT"]:
                return "Lost"
            if self.method == "NM":
                if len(self.competitors.filter(fight_version__won=1)) == 0:
                    return "Unknown"
                else:
                    return "Lost"
            elif self.method == "DR":
                return "Drew"
            else:
                return "Unknown"

    def opponents_fv(self, robot):
        fvs = Fight_Version.objects.filter(fight=self)
        tag = Fight_Version.objects.get(version__robot=robot, fight=self).tag_team
        out = []
        for fv in fvs:
            if fv.version.robot != robot and (fv.tag_team == 0 or fv.tag_team != tag):
                out.append(fv)
        return out

    def opponents_string(self, robot):
        opponents = self.opponents_fv(robot)
        out = ""
        last = None
        i = 1
        for fv in opponents:
            if i > 3:
                out += " + " + str(len(opponents) - 3) + " more..."
                break
            if out != "":
                if fv.tag_team == last.tag_team and fv.tag_team != 0:
                    out += " & "
                else:
                    out += ", "
            out += fv.version.__str__()

            last = fv
            i += 1

        return out

    def __str__(self):
        # This can cause a recursion error
        try:
            if self.name is not None and self.name != "":
                return self.name
            elif self.competitors.count() >= 2:
                ret = ""
                if self.fight_version_set.first().tag_team != 0:
                    tags = {}
                    for fv in self.fight_version_set.all():
                        try:
                            tags[fv.tag_team].append(fv.version)
                        except KeyError:
                            tags[fv.tag_team] = [fv.version]
                    for tt in tags.values():
                        teamname = ""
                        for version in tt:
                            if version.robot_name != "" and version.robot_name is not None:
                                teamname += " & " + version.robot_name  # __str__()
                            else:
                                teamname += " & " + version.robot.name
                        ret += teamname[3:] + " vs "
                    return ret[:-4]

                else:
                    for version in self.competitors.all():
                        if version.robot_name != "" and version.robot_name is not None:
                            ret += " vs " + version.robot_name  # __str__()
                        else:
                            ret += " vs " + version.robot.name
                    return ret[4:]
            else:
                return "A fight with less than two robots"
        except Exception as e:
            print(e)
            return "Trying to name this fight is causing errors (Oh no!)"

    def can_edit(self, user):
        return self.contest.can_edit(user)

    @staticmethod
    def recalculate_all():
        Robot.objects.all().update(ranking=Robot.RANKING_DEFAULT, wins=0, losses=0)
        for event in Event.objects.all().order_by("start_date"):
            for contest in event.contest_set.all():
                for fight in contest.fight_set.all().order_by("number"):
                    fight.calculate(True)
            print(event, "saved.")


class Award(models.Model):
    name = models.CharField(max_length=255)
    TYPE_CHOICES = [
        (0, "Other"),
        (1, "First Place"),
        (2, "Second Place"),
        (3, "Third Place"),
    ]
    award_type = models.PositiveSmallIntegerField(choices=TYPE_CHOICES,
                                                  default=0)  # 0 other, 1 first place, 2 second place,
    # 3 third place
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    contest = models.ForeignKey(Contest, on_delete=models.SET_NULL, blank=True, null=True)
    version = models.ForeignKey(Version, on_delete=models.CASCADE)

    def __str__(self):
        return self.name

    def get_icon(self):
        if self.award_type == 0:
            return settings.STATIC_URL + "awards/medal.png"
        elif self.award_type == 1:
            return settings.STATIC_URL + "awards/trophy_gold.png"
        elif self.award_type == 2:
            return settings.STATIC_URL + "awards/trophy_silver.png"
        else:
            return settings.STATIC_URL + "awards/trophy_bronze.png"

    def can_edit(self, user):
        return self.event.can_edit(user)


class Person_Team(models.Model):
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)

    def can_edit(self, user):
        return self.team.can_edit(user)

    def __str__(self):
        return self.person.__str__() + "'s membership of " + self.team.__str__()


class Person_Franchise(models.Model):
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    franchise = models.ForeignKey(Franchise, on_delete=models.CASCADE)

    def can_edit(self, user):
        return self.franchise.can_edit(user)

    def __str__(self):
        return self.person.__str__() + "'s membership of " + self.franchise.__str__()


class Fight_Version(models.Model):
    won = models.BooleanField()
    tag_team = models.PositiveSmallIntegerField(
        default=0)  # matching number, matching side on a tag team match, 0 for free for all fights
    ranking_change = models.FloatField(default=0)
    fight = models.ForeignKey(Fight, on_delete=models.CASCADE)
    version = models.ForeignKey(Version, on_delete=models.CASCADE)

    def can_edit(self, user):
        return self.fight.can_edit(user)

    def __str__(self):
        return self.version.__str__() + " in |" + self.fight.__str__() + "|"


class Leaderboard(models.Model):
    position = models.PositiveSmallIntegerField()
    ranking = models.FloatField()
    weight = models.CharField(max_length=1, choices=LEADERBOARD_WEIGHTS)
    year = models.IntegerField()
    robot = models.ForeignKey(Robot, on_delete=models.CASCADE)

    @staticmethod
    def update_class(wc, current_year=None):
        valid = [x[0] for x in LEADERBOARD_WEIGHTS]
        valid.remove("X")
        if wc not in valid:
            return
        if current_year is None:
            latest_event = Event.objects.all().order_by("-end_date")[0]
            date = latest_event.end_date
        else:
            date = datetime.date(current_year, 12, 31)

        five_years_ago = date - relativedelta(years=5)
        Robot.objects.filter(last_fought__lte=five_years_ago).exclude(lb_weight_class="X").update(lb_weight_class="X")

        top_100 = Robot.objects.filter(lb_weight_class=wc).order_by("-ranking")[:100]
        if current_year:
            lb = Leaderboard.objects.filter(weight=wc, year=current_year).order_by("position")
        else:
            lb = Leaderboard.get_current(wc)
            try:
                current_year = lb[0].year
            except IndexError:
                current_year = Event.objects.filter(start_date__lt=timezone.now()).order_by("-end_date")[0].start_date.year
        i = 0
        update_list = []
        for robot in top_100:
            if i < lb.count():
                to_update = lb[i]
                to_update.robot = robot
                to_update.ranking = robot.ranking
                to_update.position = i + 1
                update_list.append(to_update)
            else:
                new_entry = Leaderboard()
                new_entry.position = i + 1
                new_entry.ranking = robot.ranking
                new_entry.weight = wc
                new_entry.year = current_year
                new_entry.robot = robot
                new_entry.save()
            i += 1
        Leaderboard.objects.bulk_update(update_list, ["robot", "ranking","position"])
        #if leaderboard shrinks for some reason, delete garbage data at the end
        lb.filter(position__gt=top_100.count()).delete()

    @staticmethod
    def update_all(current_year=None):
        wcs = [x[0] for x in LEADERBOARD_WEIGHTS]
        wcs.remove("X")
        for wc in wcs:
            Leaderboard.update_class(wc,current_year)

    @staticmethod
    def update_robot_weight_class(robot, commit=True, year=None):

        currentYear = year is None
        if currentYear:
            latest_event = Event.objects.all().order_by("-end_date")[0]
            date = latest_event.end_date
        else:
            date = datetime.date(year, 12, 31)

        five_years_ago = date - relativedelta(years=5)

        if not robot.last_fought or robot.last_fought < five_years_ago:
            robot.lb_weight_class = "X"
            if commit: robot.save()
            return robot
        else:
            #Checks to see if there are less computationally heavy ways to test weight class
            if robot.version_set.count() == 1:
                robot.lb_weight_class = robot.version_set.last().weight_class.find_lb_class()
                if commit: robot.save()
                return robot
            if currentYear and robot.version_set.last().weight_class.find_lb_class() == robot.lb_weight_class:
                return robot

            # Count number of fights each weight class has to determine which it should be a part of. not perfect if the same version goes to events more than 5 years ago
            fights = {"X": 0}
            for version in robot.version_set.filter(first_fought__lte = date , last_fought__gte = five_years_ago):
                if not version.last_fought or version.last_fought < five_years_ago:
                    continue
                wc = version.weight_class.find_lb_class()
                if wc not in fights.keys():
                    fights[wc] = 0
                fights[wc] += version.fight_set.count()
            actual_weight_class = "X"
            for key in fights:
                if fights[key] >= fights[actual_weight_class]:
                    actual_weight_class = key

            robot.lb_weight_class = actual_weight_class

            if commit: robot.save()
            return robot

    @staticmethod
    def get_current(wc):
        last_event = Event.objects.filter(start_date__lt=timezone.now()).order_by("-end_date")[0].start_date
        return Leaderboard.objects.filter(weight=wc, year=last_event.year).order_by("position")

    def __str__(self):
        return "#" + str(self.position) + " " + self.weight + " in " + str(self.year) + ": " + self.robot.__str__()


class Web_Link(models.Model):
    LINK_CHOICES = [
        ("WW", "Website"),
        ("WA", "Archived Website"),
        ("FB", "Facebook"),
        ("TW", "Twitter"),
        ("IG", "Instagram"),
        ("TT", "TikTok"),
        ("DC", "Discord"),
        ("YT", "YouTube"),
        ("WC", "WeChat"),
        ("SW", "Sina Weibo"),
        ("TV", "Twitch")
    ]
    type = models.CharField(max_length=2, choices=LINK_CHOICES, default="WW")
    link = models.URLField()
    franchise = models.ForeignKey(Franchise, on_delete=models.CASCADE, blank=True, null=True)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, blank=True, null=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                              Q(franchise__isnull=True) &
                              Q(team__isnull=False)
                      ) | (
                              Q(team__isnull=True) &
                              Q(franchise__isnull=False)
                      ),
                name='team_xor_franchise',
            )
        ]

    def clean(self):
        if self.franchise and self.team:
            raise ValidationError("A Web link may be tied to a franchise or team, not both")
        if not self.franchise and not self.team:
            raise ValidationError("A Web link must be attached to a franchise or team")

    def get_logo(self):
        if self.type == "TV":
            return settings.STATIC_URL + "web_logos/" + "TwitchGlitchPurple.svg"
        else:
            return settings.STATIC_URL + "web_logos/" + self.type + ".png"

    def can_edit(self, user):  # TODO: Improve this?
        p = Person.objects.get(user=user)
        return user.is_staff

    @staticmethod
    def classify(link):
        link = link.lower()
        if "web.archive.org/" in link:
            return "WA"
        if "facebook.com/" in link:
            return "FB"
        if "twitter.com/" in link:
            return "TW"
        if "instagram.com/" in link:
            return "IG"
        if "tiktok.com/" in link:
            return "TT"
        if "discord.com/" in link or "discord.gg/" in link:
            return "DC"
        if "youtube.com/" in link or "youtu.be/" in link:
            return "YT"
        if "weibo.com/" in link or "weibo.cn/" in link:
            return "SW"
        if "wechat.com/" in link or "wechat.cn/" in link:
            return "WC"
        if "twitch.tv/" in link:
            return "TV"
        return "WW"

    def __str__(self):
        if self.franchise:
            return self.franchise.name + " " + self.get_type_display() + ": " + self.link
        else:
            return self.team.name + " " + self.get_type_display() + ": " + self.link


class Source(models.Model):
    name = models.CharField(max_length=255)
    link = models.URLField()
    archived = models.BooleanField()
    last_accessed = models.DateField(default=timezone.now)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    
    def get_domain(self): # TODO: This wastes the server's time, do this in JavaScript
        if "ultimate-robot-archive.fandom.com" in self.link:
            #this does not display properly with iconhorse
            return "fandom.com"
        if self.link[:8] == "https://":
            ret = self.link[8:]
            i = 8
        elif self.link[:7] == "http://":
            ret = self.link[7:]
            i = 7
        if ret[:4] == "www.":
            ret = ret[4:]
        for i in range(i, len(ret)):
            if ret[i] == '/' or ret[i] == ':':
                break
        return ret[:i]

    def __str__(self):
        return self.name


# TODO: This should maybe be another module, requires database but idk how to like, do it otherwise.
class Ascii_Lookup(models.Model):
    old_char = models.CharField(max_length=1)
    new_char = models.CharField(max_length=10, blank=True)
    requires_translation = models.BooleanField(default=False)


class Ascii_Attention(models.Model):
    word = models.TextField()
    bad_char = models.CharField(max_length=1)
    model = models.CharField(max_length=50)
    model_id = models.IntegerField()


def asciify(text, model="none", model_id=0):
    valid = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 "
    lookups = Ascii_Lookup.objects.all()
    lookup = {}
    for look in lookups:
        lookup[look.old_char] = look.new_char
    new = ""
    for i in range(len(text)):
        if text[i] not in valid:
            try:
                # Checks for Special Cases
                if text[i] == "-":
                    # Convert " - " to one space
                    try:
                        if text[i - 1] == " " and text[i + 1] == " ":
                            new = new[0:-1]
                            continue
                    except IndexError:
                        pass

                new += lookup[text[i]]

            except KeyError:
                # Checks for Special Cases
                if text[i] == ".":
                    try:
                        if text[i - 1] in "0123456789" and text[i + 1] in "0123456789":
                            new += "."
                    except IndexError:
                        pass  # Do Nothing
                    continue
                if text[i] == "%":
                    try:
                        if text[i - 1] in "0123456789":
                            new += "%"
                    except IndexError:
                        pass  # Do Nothing
                    continue

                # General Case
                if model_id is None:
                    model_id = 0
                asc = Ascii_Attention(word=text, bad_char=text[i], model=model, model_id=model_id)
                asc.save()
                new += text[i]
        else:
            new += text[i]
    if new != text:
        return new
    else:
        return ""


try:
    w = Weight_Class.objects.get(pk=1)
    if w.name != "unknown":
        w.id = None
        w.save("force_insert")
    w.name = "unknown"
    w.weight_grams = 0
    w.recommended = False
    w.id = 1
    w.save()
except:
    try:
        w = Weight_Class()
        w.name = "unknown"
        w.weight_grams = 0
        w.recommended = False
        w.id = 1
        w.save()
    except:
        pass

#TODO: DO THIS ON CREATION
for e in Event.objects.filter(slug=""):
    e.slugify()
for f in Franchise.objects.filter(slug=""):
    f.slugify()
for t in Team.objects.filter(slug=""):
    t.slugify()