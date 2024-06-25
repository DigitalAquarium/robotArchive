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

FIGHT_TYPE_CHOICES = [
    ('FC', "Full Combat"),
    ('NS', "Non-Spinner"),
    ('SP', "Sportsman"),
    ('PL', "Plastic"),
    ('NC', "Other - Not Combat"),
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

robot_slug_blacklist_file = open(settings.STATIC_URL[1:] + "slug_blacklist.txt", "r")
robot_slug_blacklist = []
for line in robot_slug_blacklist_file:
    robot_slug_blacklist.append(line.replace("\n", ""))
robot_slug_blacklist_file.close()


def get_flag(code):
    return settings.STATIC_URL + "flags/4x3/" + code.lower() + ".svg"


def make_slug(slug_text, queryset):
    SLUG_LENGTH = 50
    slug_text = slugify(slug_text[:SLUG_LENGTH])
    if queryset.filter(slug=slug_text).count() > 0:
        uu = "-" + str(uuid.uuid4())
        slug_text = slug_text[:SLUG_LENGTH - len(uu)] + uu
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
    slug = models.SlugField(max_length=50, unique=True)

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

    def all_robots(self):
        return Robot.objects.filter(version__team=self).distinct()

    def owned_robots(self):
        return Robot.objects.filter(version__team=self, version__loaned=False).distinct()

    def loaners(self):
        return Robot.objects.filter(version__team=self, version__loaned=True).distinct()

    def can_edit(self, user):
        p = Person.objects.get(user=user)
        return p in self.members.all() or user.is_staff

    def make_slug(self, save=False):
        if self.slug is not None and self.slug != "": return self.slug
        slug_text = self.name
        if slug_text[:5].lower() == "team ":
            slug_text = slug_text[5:]
        self.slug = make_slug(slug_text, Team.objects.all())
        if save: self.save()
        return self.slug

    def timespan(self,text=False):
        # Only select robots that fought after 1980 (all robots) as a proxy for checking that first_fought is not none
        first_first_fought = self.owned_robots().filter(first_fought__gt="1980-01-01").order_by(
            "first_fought").first()
        if first_first_fought is not None:
            first_first_fought = first_first_fought.first_fought
            last_last_fought = self.owned_robots().order_by("-last_fought").first().last_fought
            return timespan(first_first_fought, last_last_fought, text)
        else:
            return "that never competed"



class Weight_Class(models.Model):
    BOUNDARY_AMOUNT = 0.21
    LEADERBOARD_VALID = [(150, "UK Antweight / US Fairyweight"),
                         (454, "US Antweight"),
                         (1361, "Beetleweight"),
                         (6000, "Hobbyweight"),  # Should this be 5553 to remove 15lbs
                         (13608, "Featherweight"),
                         (28000, "Lightweight"),  # 28000 over 27212 to include korean 33kg lws.
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
        if self.weight_grams < 1000:
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
        # [2,3,4,5,6,7,8,9]
        nearest_weight_class = min(Weight_Class.LEADERBOARD_VALID_GRAMS, key=lambda x: abs(x - grams))
        if abs(nearest_weight_class - grams) <= nearest_weight_class * self.BOUNDARY_AMOUNT:
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
    latin_name = models.CharField(max_length=255, blank=True)
    slug = models.SlugField(max_length=100, allow_unicode=True, unique=True)
    display_latin_name = models.BooleanField(default=False)

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
        SLUG_LEN = 50

        desired_slug = self.name[:SLUG_LEN]
        desired_slug = desired_slug.replace("&", "and")
        desired_slug = slugify(desired_slug)
        any_letter = re.compile(".*[a-zA-Z].*")
        if not any_letter.match(self.name) or len(desired_slug) < len(self.name) / 3:
            desired_slug = slugify(self.name[:SLUG_LEN], allow_unicode=True)

        similar_slugs = Robot.objects.filter(slug__contains=desired_slug).exclude(id=self.id)
        if similar_slugs.filter(slug=desired_slug).count() > 0:
            slug_holder = similar_slugs.get(slug=desired_slug)

            same_wc = (
                              self.lb_weight_class == slug_holder.lb_weight_class and self.lb_weight_class != 'X' and slug_holder.lb_weight_class != 'X') or \
                      (
                              self.last_version().weight_class.find_lb_class() == slug_holder.version_set.last().weight_class.find_lb_class())
            if not same_wc:
                if self.lb_weight_class == "S":
                    weight_slug = "-shw"
                elif self.lb_weight_class == "U":
                    weight_slug = "-awus"
                elif self.lb_weight_class == "Y":
                    weight_slug = "-hbw"
                elif self.lb_weight_class != "X":
                    weight_slug = "-" + self.lb_weight_class.lower() + "w"
                elif self.last_version().weight_class.find_lb_class() != "X":
                    weight_slug = "-" + self.last_version().weight_class.find_lb_class().lower() + "w"
                else:
                    weight_slug = "-" + self.last_version().weight_class.weight_string()
                    weight_slug = re.sub("\.[0-9]", '', weight_slug)  # truncates decimals
                desired_slug = desired_slug + weight_slug

            if similar_slugs.filter(slug=desired_slug).count() > 0:
                slug_holder = similar_slugs.get(slug=desired_slug)

                same_country = self.country == slug_holder.country
                if not same_country:
                    country_dict = {"GB": "-uk", "US": "-usa", "AE": "-uae", "KP": "-north-korea", "KR": "-south-korea",
                                    "CD": "-dr-congo", "RU": "-russia", "SY": "-syria", "BO": "-bolivia",
                                    "BN": "-benin",
                                    "FM": "-micronesia", "IR": "-iran", "LA": "-laos", "MF": "-saint-martin",
                                    "SX": "-sint-maartin", "MD": "-moldova", "PS": "-palestine", "VN": "-vietnam",
                                    "TW": "-taiwan", "XE": "-england", "XS": "-scotland", "XW": "-wales",
                                    "XI": "-northern-ireland", "XX": "-unknown"}
                    if self.country in country_dict:
                        country_slug = country_dict[self.country]
                    else:
                        country_slug = "-" + slugify(pycountry.countries.get(alpha_2=self.country).name)
                    desired_slug = desired_slug + country_slug

        if similar_slugs.filter(slug=desired_slug).count() > 0 or desired_slug in robot_slug_blacklist:
            matching_regex = "(" + re.escape(desired_slug) + ")(-[0-9]*)?"
            number_of_matches = similar_slugs.filter(slug__regex=matching_regex).count()
            found_unique_number = False
            for i in range(2, number_of_matches + 1000):
                number_slug = "-" + str(i)
                if similar_slugs.filter(slug=desired_slug + number_slug).count() == 0:
                    found_unique_number = True
                    break
            if found_unique_number:
                desired_slug = desired_slug + number_slug
            else:
                desired_slug = desired_slug + uuid.uuid4()

        if len(desired_slug) > 100:
            # Something has probably gone wrong, force a UUID in order to fit in the field.
            desired_slug = uuid.uuid4()

        return desired_slug

    def first_version(self):
        return self.version_set.all().order_by("number")[0]
    def last_version(self):
        return self.version_set.all().order_by("-number")[0]


    @staticmethod
    def get_by_rough_weight(wc):
        BOUNDARY_AMOUNT = 0.21
        upper_bound = wc + (wc * BOUNDARY_AMOUNT)
        lower_bound = wc - (wc * BOUNDARY_AMOUNT)
        classes = Weight_Class.objects.filter(weight_grams__lte=upper_bound, weight_grams__gte=lower_bound)
        robs = Robot.objects.filter(version__weight_class__in=classes).distinct()
        return robs

    def set_latin_name(self, commit=True):
        self.latin_name = asciify(self.name, "Robot", self.id)
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

    def get_representitive(self, team=None):
        if team:
            valid_version_set = self.version_set.filter(team=team).order_by("-number")
        else:
            valid_version_set = self.version_set.order_by("-number")

        identically_named_versions = valid_version_set.filter(
            robot_name__regex="(^|" + self.name + " ([MDCLXVI]+|[mdclxvi]+|[0-9]+))$")

        # This regex also classes numbered versions as identical, will show "Tiberius 6" over Tiberius or "Firestorm V" over "Firestorm"
        # TODO: Should probably contain an exact name match

        if identically_named_versions.count() > 0:
            representative = identically_named_versions[0]
        else:
            representative = valid_version_set.last()
            # TODO: Could try to guess the best version based on string similarity?
        return representative

    def get_image(self, team=None):
        rep = self.get_representitive(team)
        if rep.image:
            return rep.image.url
        else:
            return settings.STATIC_URL + "unknown.png"

    def timespan(self, text=False):
        return timespan(self.first_fought, self.last_fought, text)


class Version(models.Model):
    robot_name = models.CharField(max_length=255, blank=True)
    latin_robot_name = models.CharField(max_length=255, blank=True)
    name = models.CharField(max_length=255, blank=True)
    display_latin_name = models.BooleanField(default=False)

    number = models.PositiveSmallIntegerField(default=0)
    country = models.CharField(max_length=2, choices=COUNTRY_CHOICES, blank=False, default="XX")
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='robot_images/%Y/', blank=True)
    weapon_type = models.CharField(max_length=20)
    first_fought = models.DateField(blank=True, null=True)
    last_fought = models.DateField(blank=True, null=True)

    robot = models.ForeignKey(Robot, on_delete=models.CASCADE)
    loaned = models.BooleanField(default=False)
    owner = models.ForeignKey(Person, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, blank=True, null=True)
    weight_class = models.ForeignKey(Weight_Class, on_delete=models.SET(1))

    def set_latin_name(self, commit=True):
        self.latin_robot_name = asciify(self.robot_name, "Version", self.id)
        if commit:
            self.save()

    def update_fought_range(self, contest, commit=True):
        v_update_flag = False
        r_update_flag = False

        if not self.first_fought or self.first_fought > contest.start_date:
            self.first_fought = contest.start_date
            v_update_flag = True
        if not self.robot.first_fought or self.robot.first_fought > contest.start_date:
            self.robot.first_fought = contest.start_date
            v_update_flag = True

        if not self.last_fought or self.last_fought < contest.end_date:
            self.last_fought = contest.end_date
            v_update_flag = True
        if not self.robot.last_fought or self.robot.last_fought < contest.end_date:
            self.robot.last_fought = contest.end_date
            r_update_flag = True

        if commit:
            if v_update_flag:
                self.save()
            if r_update_flag:
                self.robot.save()
        return v_update_flag or r_update_flag

    def get_latin_name(self):
        if self.robot_name != "":
            return self.latin_robot_name
        else:
            return self.robot.latin_name

    def english_readable_name(self):
        if self.robot_name == "":
            if self.robot.display_latin_name:
                return self.robot.latin_name
            else:
                return self.robot.name
        else:
            if self.display_latin_name:
                return self.latin_robot_name
            else:
                return self.robot_name

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
        return self.owner.can_edit(user) or self.robot.last_version().owner.can_edit(user)

    def timespan(self, text=False):
        return timespan(self.first_fought, self.last_fought, text)


class Franchise(models.Model):
    name = models.CharField(max_length=50)
    logo = models.ImageField(upload_to='franchise_logos/%Y/', blank=True)
    description = models.TextField(blank=True)
    members = models.ManyToManyField(Person, through="Person_Franchise")
    slug = models.SlugField(max_length=50, unique=True)

    def make_slug(self, save=False):
        if self.slug is not None and self.slug != "": return self.slug
        self.slug = make_slug(self.name, Franchise.objects.all())
        if save: self.save()
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
        if Event.objects.filter(franchise=self).count() > 0 and Event.objects.filter(franchise=self)[0].country != "XX":
            return Event.objects.filter(franchise=self)[0].get_flag()
        return settings.STATIC_URL + "unknown.png"

    def timespan(self, text=False):
        return timespan(self.event_set.all().order_by("start_date").first().start_date,
                        self.event_set.all().order_by("start_date").last().end_date, text)


class Location(models.Model):
    name = models.CharField(max_length=255)
    latitude = models.FloatField()
    longitude = models.FloatField()

    def __str__(self):
        return self.name


class Event(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='event_logos/%Y/', blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    country = models.CharField(max_length=2, choices=COUNTRY_CHOICES, blank=False, default="XX")
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True)
    franchise = models.ForeignKey(Franchise, on_delete=models.CASCADE)
    slug = models.SlugField(max_length=50, unique=True)
    missing_brackets = models.BooleanField(default=False)


    def make_slug(self, save=False):
        if self.slug is not None and self.slug != "": return self.slug
        self.slug = make_slug(self.name, Event.objects.all())
        if save: self.save()
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

    def is_one_day(self):
        return self.start_date == self.end_date

    def can_edit(self, user):
        return self.franchise.can_edit(user)

    def get_logo_url(self):
        if self.logo:
            return self.logo.url
        if self.franchise.logo:
            return self.franchise.logo.url
        if self.country != "XX":
            return self.get_flag()
        return settings.STATIC_URL + "unknown.png"

    def get_location(self):
        if self.location:
            return self.location
        else:
            return Location(name="Undefined", latitude=0, longitude=0)

    def timespan(self, text=False):
        return timespan(self.start_date, self.end_date, text)


class Contest(models.Model):
    name = models.CharField(max_length=255, blank=True)
    fight_type = models.CharField(max_length=2, choices=FIGHT_TYPE_CHOICES + [("MU", "Multiple Types")])
    start_date = models.DateField()
    end_date = models.DateField()
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    weight_class = models.ForeignKey(Weight_Class, on_delete=models.SET(1))

    def __str__(self):
        if self.name is not None and self.name != "":
            return self.name
        else:
            return self.weight_class.name

    def can_edit(self, user):
        return self.event.franchise.can_edit(user)

    def timespan(self, text=False):
        return timespan(self.start_date, self.end_date, text)


class Registration(models.Model):  # Idea for future: Add a team limit to reservations.
    signup_time = models.DateTimeField(auto_now_add=True)
    approved = models.BooleanField(default=False)  # TODO: Remove these
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
        ("DK", "Double KO"),
        ("JD", "Judge's Decision"),
        ("CV", "Crowd Vote"),
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

    def calculate(self, commit=True, v_dict=None):
        #if self.id == 981:
        #    breakpoint()
        if self.fight_type == "NC":
            return [[], v_dict]
        K = 25
        if self.fight_type == "NS":
            # Penalty for Non Spinner fights, Iron Awe & co can't be the best ranked if they can't take a shot from a spinner
            # and those robots typically do more fights anyway due to being less destroyed.
            K /= 2
        fvs = self.fight_version_set.all()
        numBots = len(fvs)  # Must be len and not count because lazy loading causes the robot to not save otherwise
        numWinners = fvs.filter(won=True).count()

        if not v_dict:
            v_dict = {}
        for fv in fvs:
            if fv.version.id not in v_dict:
                v_dict[fv.version.id] = fv.version
        # print(v_dict)

        startverif = []
        for fv in fvs:
            startverif.append(v_dict[fv.version.id].robot.ranking)

        if (self.fight_type == "FC" or self.fight_type == "NS") and (numWinners > 0 or self.method == "DR"):
            tag = fvs.filter(tag_team__gt=0).count() > 1

            if numBots == 2:
                q1 = 10 ** (v_dict[fvs[0].version.id].robot.ranking / 400)
                q2 = 10 ** (v_dict[fvs[1].version.id].robot.ranking / 400)
                expected1 = q1 / (q1 + q2)
                if fvs[0].won:
                    score1 = 1
                elif numWinners == 0:
                    score1 = 0.5
                else:
                    score1 = 0
                change = K * (score1 - expected1)
                v_dict[fvs[0].version.id].robot.ranking += change
                fvs[0].ranking_change = change
                v_dict[fvs[1].version.id].robot.ranking -= change
                fvs[1].ranking_change = -change

            elif not tag:
                # Take an amount of points for a loss/draw against the average of the group, divided by the number of
                # robots off each robot and then add fair share of that back to the winners/everyone. Makes it a low
                # stakes loss, but still a win equal to a normal fight if you're the only winner of the rumble
                averageRank = 0
                for fv in fvs:
                    averageRank += v_dict[fv.version.id].robot.ranking / numBots
                averageQ = 10 ** (averageRank / 400)
                pool = 0
                for i in range(numBots):
                    q = 10 ** (v_dict[fvs[i].version.id].robot.ranking / 400)
                    averageExpected = averageQ / (averageQ + q)
                    if self.method == "DR":  # Some elo here may get lost on the floor or gained due to floating points
                        change = (K * (0.5 - averageExpected)) / numBots
                    else:
                        change = (K * (1 - averageExpected)) / numBots
                        pool += change
                    fvs[i].version.robot.ranking -= change
                    fvs[i].ranking_change = -change

                for i in range(numBots):  # Distribute this based on amount of elo maybe
                    if fvs[i].won == 1:
                        v_dict[fvs[i].version.id].robot.ranking += pool / numWinners
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
                        tavg += v_dict[fv.version.id].robot.ranking
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
                        v_dict[fv.version.id].robot.ranking += change / len(tteams[0])
                    for fv in tteams[1]:
                        fv.ranking_change = -change / len(tteams[1])
                        v_dict[fv.version.id].robot.ranking -= change / len(tteams[1])

                else:
                    averageRank = 0
                    for i in range(len(tteams)):
                        averageRank += tteamsAvg[i] / numBots
                    averageQ = 10 ** (averageRank / 400)
                    pool = 0
                    for i in range(len(tteams)):
                        q = 10 ** (tteamsAvg[i] / 400)
                        averageExpected = averageQ / (averageQ + q)
                        if self.method == "DR":
                            change = (K * (0.5 - averageExpected)) / len(tteams)
                        else:
                            change = (K * (1 - averageExpected)) / len(tteams)
                            pool += change
                        for fv in tteams[i]:
                            v_dict[fv.version.id].robot.ranking -= change
                            fv.ranking_change = -change

                    for i in range(len(tteams)):
                        if fvs[i].won == 1:
                            v_dict[fvs[i].version.id].robot.ranking += pool / numWinners
                            fvs[i].ranking_change += pool / numWinners
        else:
            for fv in fvs:
                fv.ranking_change = 0

        if numBots == 2 and numWinners == 1 and self.fight_type in ["FC", "NS", "SP", "PL"]:
            for fv in fvs:
                if fv.won:
                    v_dict[fv.version.id].robot.wins += 1
                else:
                    v_dict[fv.version.id].robot.losses += 1

        rank_changed = False
        for fv in fvs:
            if not v_dict[fv.version.id].first_fought or v_dict[fv.version.id].first_fought > fv.fight.contest.event.start_date:
                v_dict[fv.version.id].first_fought = fv.fight.contest.event.start_date
                vupdateFlag = True
            if not v_dict[fv.version.id].robot.first_fought or v_dict[fv.version.id].robot.first_fought > fv.fight.contest.event.start_date:
                v_dict[fv.version.id].robot.first_fought = fv.fight.contest.event.start_date

            if not v_dict[fv.version.id].last_fought or v_dict[fv.version.id].last_fought < fv.fight.contest.event.end_date:
                v_dict[fv.version.id].last_fought = fv.fight.contest.event.end_date
                vupdateFlag = True
            if not v_dict[fv.version.id].robot.last_fought or v_dict[fv.version.id].robot.last_fought < fv.fight.contest.event.end_date:
                v_dict[fv.version.id].robot.last_fought = fv.fight.contest.event.end_date

        #Verification
        iterator = 0
        for fv in fvs:
            change = fv.ranking_change
            start = startverif[iterator]
            end = v_dict[fv.version.id].robot.ranking
            startpluschange = start + change
            if abs(abs(startpluschange)-abs(end)) > 0.05:
                breakpoint()
            iterator += 1

        if commit:
            for fv in fvs:
                if vupdateFlag:
                    v_dict[fv.version.id].save()
                v_dict[fv.version.id].robot.save()
                fv.save()
        return [fvs, v_dict]

    def new_calculate(self, competitors=[], commit=True):
        # Preprocessing
        fvs = self.fight_version_set.all()
        if self.fight_type == "NC":
            return [fvs, competitors]
        K = 25
        if self.fight_type == "NS":
            # Penalty for Non Spinner fights, Iron Awe & co can't be the best ranked if they can't take a shot from a
            # spinner and those robots typically do more fights anyway due to being less destroyed.
            K /= 2

        if len(competitors) == 0:
            competitors = [fv.version for fv in fvs]
        else:
            commit=False

        # Skip Rank Calculation (and tag team pre- / post-processing) if it isn't relevant
        if (self.fight_type == "FC" or self.fight_type == "NS") and (sum([fv.won for fv in fvs]) > 0 or self.method == "DR"):
            tt_fight_flag = fvs.filter(tag_team__gt=0).count() > 1
            if tt_fight_flag:
                # If the match is a tag team match, create dummy competitors and fvs for the fight calculation representing the average robot per team.
                tteams = []
                newfvs = []
                tteams_key = {}
                # sort the competitors & fvs so they line up properly when tag teams are made.
                fvs = sorted(fvs,key=lambda x: x.tag_team)
                new_competitors = []
                for fv in fvs:
                    for competitor in competitors:
                        if fv.version.id == competitor.id:
                            new_competitors.append(competitor)
                competitors = new_competitors
                oldfvs = fvs
                for i in range(len(competitors)):  # Sort fvs into teams in a 2D array
                    try:
                        tteams[tteams_key[fvs[i].tag_team]].append(competitors[i])
                    except KeyError:
                        tteams_key[fvs[i].tag_team] = len(tteams) # tteams_key tells the index of each team in the list. the length of the list finds this for the next team in line
                        tteams.append([competitors[i]])
                competitors = []
                i = -1
                for tt in tteams:  # Convert 2D array into 1D array of dummies and reorder fight versions to be along with teams so they line up again when unwrapped later.
                    averageTTRank = 0
                    for member in tt:
                        i += 1
                        averageTTRank += member.robot.ranking
                    averageTTRank /= len(tt)
                    competitors.append(Version())
                    competitors[-1].robot = Robot()
                    competitors[-1].robot.ranking = averageTTRank
                    newfvs.append(Fight_Version())
                    newfvs[-1].won = fvs[i].won
                fvs = newfvs

            numWinners = sum([fv.won for fv in fvs])


            # Rank Calculation
            if len(competitors) == 2:
                q1 = 10 ** (competitors[0].robot.ranking / 400)
                q2 = 10 ** (competitors[1].robot.ranking / 400)
                expected1 = q1 / (q1 + q2)
                if numWinners == 0:
                    score1 = 0.5
                elif fvs[0].won == 1:
                    score1 = 1
                else:
                    score1 = 0
                change = K * (score1 - expected1)
                fvs[0].ranking_change = change
                fvs[1].ranking_change = -change
            else:
                # Take an amount of points for a loss/draw against the average of the group, divided by the number of
                # robots off each robot and then add fair share of that back to the winners/everyone. Makes it a low
                # stakes loss, but still a win equal to a normal fight if you're the only winner of the rumble
                averageRank = 0
                for competitor in competitors:
                    averageRank += competitor.robot.ranking / len(competitors)
                averageQ = 10 ** (averageRank / 400)
                pool = 0
                for i in range(len(competitors)):
                    q = 10 ** (competitors[i].robot.ranking / 400)
                    averageExpected = averageQ / (averageQ + q)
                    if self.method == "DR":  # Some elo here may get lost on the floor or gained due to floating points
                        change = (K * (0.5 - averageExpected)) / len(competitors)
                    else:
                        change = (K * (1 - averageExpected)) / len(competitors)
                        pool += change
                    fvs[i].ranking_change = -change

                for i in range(len(competitors)):  # Distribute this based on amount of elo maybe
                    if fvs[i].won == 1:
                        fvs[i].ranking_change += pool / numWinners

            #Post Processing
            if tt_fight_flag:
                #Convert data from dummy fvs back onto the real fvs and unwrap the tteams 2D array back to a competitors 1D array
                unwraped_competitors = []
                k = 0
                for i in range(len(tteams)):
                    for j in range(len(tteams[i])):
                        unwraped_competitors.append(tteams[i][j])
                        oldfvs[k].ranking_change = fvs[i].ranking_change / len(tteams[i])
                        k += 1
                fvs = oldfvs
                competitors = unwraped_competitors

            for i in range(len(competitors)): # Apply ranking change to robots.
                competitors[i].robot.ranking += fvs[i].ranking_change

        #Sportsman and plastic can gain wins but not rank
        if len(competitors) == 2 and sum([fv.won for fv in fvs]) == 1 and self.fight_type in ["FC", "NS", "SP", "PL"]:
            for i in [0,1]:
                if fvs[i].won:
                    competitors[i].robot.wins += 1
                else:
                    competitors[i].robot.losses += 1

        if commit:
            robs = [competitor.robot for competitor in competitors]
            Robot.objects.bulk_update(robs, ["ranking", "wins", "losses"])
            Fight_Version.objects.bulk_update(fvs, ["ranking_change"])

        return [fvs, competitors]

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
            if "twitter" in self.external_media or "www.x.com" in self.external_media:
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

    def img_gif_vid(self):
        if self.media_type in ["LV", "IF", "IG", "TW", "TT", "FB"]:
            return "video"
        elif self.media_type in ["LI", "EI"]:
            if self.media_type == "LI":
                media = self.internal_media.url
            else:
                media = self.external_media
            if media[-4:] == ".gif":
                return "gif"
            else:
                return "image"
        else:
            return None

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

    def teams_fv(self):
        teams = []
        for fv in self.fight_version_set.all().order_by("tag_team"):
            if fv.tag_team != 0:
                try:
                    teams[fv.tag_team - 1].append(fv)
                except IndexError:
                    teams.append([fv])
        return teams

    def winners(self):
        winners = []
        for fv in self.fight_version_set.all():
            if fv.won == 1:
                winners.append(fv.version)
        return winners

    def result(self, r):
        this_robot = Fight_Version.objects.filter(version__robot=r, fight=self)
        if this_robot.count() > 1:
            print("Multiple copies of " + str(r) + " in " + str(self))  # TODO: log this properly
        fv = this_robot[0]
        if fv.won:
            if len(self.competitors.filter(fight_version__won=1)) == 1 or fv.tag_team != 0:
                return "Won"
            else:
                return "Qualified"
        else:
            if self.method in ["KO", "JD", "TO", "OA", "PT", "OT", "CV", "DK"]:
                return "Lost"
            if self.method == "NM":
                if len(self.competitors.filter(fight_version__won=1)) == 0:
                    return "Unknown"
                else:
                    return "Lost"
            elif self.method == "DR":
                return "Drew"
            elif self.method == "NW":
                return "No Winner Declared"
            else:
                return "Unknown"

    def opponents_fv(self, robot):
        fvs = Fight_Version.objects.filter(fight=self)
        this_robot = Fight_Version.objects.filter(version__robot=robot, fight=self)
        if this_robot.count() > 1:
            print("Multiple copies of " + str(robot) + " in " + str(self))  # TODO: log this properly
        tag = this_robot[0].tag_team
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
            if i > 4:
                out += " + " + str(len(opponents) - 3) + " more..."
                break
            if out != "":
                if fv.tag_team == last.tag_team and fv.tag_team != 0:
                    out += " & "
                else:
                    out += ", "
            out += fv.version.english_readable_name()

            last = fv
            i += 1

        return out

    def string_name(self, english_readable=False):
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
                            if english_readable:
                                teamname += " & " + version.english_readable_name()
                            else:
                                teamname += " & " + version.__str__()
                        ret += teamname[3:] + " vs "
                    return ret[:-4]

                else:
                    for version in self.competitors.all():
                        if english_readable:
                            ret += " vs " + version.english_readable_name()
                        else:
                            ret += " vs " + version.__str__()
                    return ret[4:]
            else:
                return "A fight with less than two robots"
        except Exception as e:
            print(e)
            return "Trying to name this fight is causing errors (Oh no!)"

    def non_latin_name(self):
        return self.string_name(False)

    def __str__(self):
        return self.string_name(True)

    def can_edit(self, user):
        return self.contest.can_edit(user)


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
    difference = models.SmallIntegerField()
    robot = models.ForeignKey(Robot, on_delete=models.CASCADE)
    version = models.ForeignKey(Version, on_delete=models.CASCADE)

    # lb.robot.version_set.filter(first_fought__year__lte=year).order_by("-last_fought")

    @staticmethod
    def update_class(wc, current_year=None):
        # WARNING: Only to be used with a current_year value if recalculating all fights. This function assumes that
        # each robot's elo is the elo it currently has on the system which is NOT TRUE for old leaderboards. On a
        # full database this function ONLY WORKS on the LATEST YEAR on record.
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
                current_year = Event.objects.filter(start_date__lt=timezone.now()).order_by("-end_date")[
                    0].start_date.year
        previous_year = Leaderboard.objects.filter(weight=wc, year=current_year - 1, position__lt=101)
        i = 0
        update_list = []
        still_here = []
        for robot in top_100:
            if i < lb.count():
                to_update = lb[i]
                to_update.robot = robot
                to_update.version = \
                    robot.version_set.filter(first_fought__year__lte=current_year).order_by("-last_fought")[0]
                to_update.ranking = robot.ranking
                to_update.position = i + 1
                to_update.difference = -1000
                entry = to_update
                update_list.append(to_update)
            else:
                new_entry = Leaderboard()
                new_entry.position = i + 1
                new_entry.ranking = robot.ranking
                new_entry.weight = wc
                new_entry.year = current_year
                new_entry.robot = robot
                new_entry.version = \
                    robot.version_set.filter(first_fought__year__lte=current_year).order_by("-last_fought")[0]
                new_entry.difference = -1000
                entry = new_entry
                new_entry.save()

            prev_entry = previous_year.filter(robot=robot)
            if prev_entry.exists():
                prev_entry = prev_entry[0]
                still_here.append(prev_entry.id)
                if entry.difference == -1000:
                    entry.difference = prev_entry.position - entry.position
                    update_list.append(entry)
            elif Leaderboard.objects.filter(robot=robot, year=current_year - 1).exclude(weight=wc).exists():
                if entry.difference == -1000:
                    entry.difference = 102
                    update_list.append(entry)
            else:
                if entry.difference == -1000:
                    entry.difference = 101
                    update_list.append(entry)
            i += 1

        for entry in previous_year:
            if entry.id not in still_here:
                if Leaderboard.objects.filter(year=current_year, robot=entry.robot).count() > 0:
                    # reason = "Switched Weight Class"
                    diff = -103
                elif entry.robot.version_set.filter(last_fought__gte=five_years_ago).count() == 0:
                    # reason = "Too Old: Timed Out"
                    diff = -102
                else:
                    # reason = "Rank Too Low: Eliminated"
                    diff = -101
                if not lb.filter(robot=entry.robot, position=101).exists():
                    new_entry = Leaderboard()
                    new_entry.year = current_year
                    new_entry.weight = wc
                    new_entry.robot = entry.robot
                    new_entry.ranking = 0
                    new_entry.position = 101
                    new_entry.version = \
                        entry.robot.version_set.filter(first_fought__year__lte=current_year).order_by("-last_fought")[
                            0]
                    new_entry.difference = diff
                    new_entry.save()

        for entry in lb.filter(position=101):
            if entry.robot in lb.filter(position__lte=100):
                entry.delete()

        Leaderboard.objects.bulk_update(update_list, ["robot", "ranking", "position", "version", "difference"])
        # if leaderboard shrinks for some reason, delete garbage data at the end
        lb.filter(position__gt=top_100.count(), position__lt=101).delete()

    @staticmethod
    def update_all(current_year=None):
        # TODO: if for whatever reason small weight classes come back change this
        wcs = ["H", "M", "L", "S"]  # x[0] for x in LEADERBOARD_WEIGHTS]
        # wcs.remove("X")
        if current_year in [1995, 1996, 1997]:
            wcs.append("F")
        for wc in wcs:
            Leaderboard.update_class(wc, current_year)

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
            has_competitively_fought = False
            for version in robot.version_set.all():
                if version.fight_set.filter(fight_type__in=["FC", "NS"]).count() > 0:
                    has_competitively_fought = True
                    break
            if not has_competitively_fought:
                robot.lb_weight_class = "X"
                if commit: robot.save()
                return robot

            # Checks to see if there are less computationally heavy ways to test weight class
            if robot.version_set.count() == 1:
                robot.lb_weight_class = robot.last_version().weight_class.find_lb_class()
                if commit: robot.save()
                return robot
            if currentYear and robot.last_version().weight_class.find_lb_class() == robot.lb_weight_class:
                return robot

            # Count number of fights each weight class has to determine which it should be a part of. not perfect if the same version goes to events more than 5 years ago
            fights = {"X": 0}
            for version in robot.version_set.filter(first_fought__lte=date, last_fought__gte=five_years_ago):
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

    def wc_to_string(self):
        for i in LEADERBOARD_WEIGHTS:
            if i[0] == self.weight:
                return i[1]
        return "Not a weight class"

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
        ("TV", "Twitch"),
        ("LI", "LinkedIn"),
        ("GH", "GitHub"),
        ("LT", "Linktree"),

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
        if self.type in ["TV", "GH"]:
            return settings.STATIC_URL + "web_logos/" + self.type + ".svg"
        else:
            return settings.STATIC_URL + "web_logos/" + self.type + ".png"

    def can_edit(self, user):  # TODO: Improve this?
        p = Person.objects.get(user=user)
        return user.is_staff

    def alt(self):
        if self.type == "WW":
            return "Grid Sphere Icon"
        elif self.type == "WA":
            return "Filing Cabinet Icon"
        else:
            return self.get_type_display() + " Logo"

    @staticmethod
    def classify(link):
        link = link.lower()
        if "web.archive.org/" in link:
            return "WA"
        if "facebook.com/" in link:
            return "FB"
        if "twitter.com/" in link or "/x.com/" in link:
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
        if "linkedin.com/" in link or "linked.in/" in link:
            return "LI"
        if "github.com/" in link:
            return "GH"
        if "linktr.ee/" in link:
            return "LT"

        return "WW"

    def get_display(self):
        def preprocess(link):
            if "https://" == link[:8]:
                link = link[8:]
            elif "http://" == link[:7]:
                link = link[7:]
            if "www." == link[:4]:
                link = link[4:]
            if "mobile." == link[:7]:
                link = link[7:]
            if link[-1] == "/":
                link = link[:-1]
            return link

        if self.type == "WW":
            ret = re.search("(\/|^)[0-9a-zA-Z-.]+(\/|$)", self.link).group(0)
            ret = ret.replace("/", "")
            if ret[:4] == "www.":
                ret = ret[4:]
            return ret

        elif self.type == "WA":
            beginning = re.search(
                "(https?:\/\/)?web\.archive\.org\/web\/(([0-9]{14}([a-z]{2}_)?)|(\*))\/(https?:\/\/)?(www\.)?",
                self.link)
            beginning = beginning.span()[1]
            ret = self.link[beginning:]
            if "/" in ret:
                end = re.search("\/.*", ret)
                ret = ret[:end.span()[0]]
            if ret[-3:] == ":80":
                ret = ret[:-3]
            return ret

        elif self.type == "TW":
            ret = preprocess(self.link)
            if "twitter.com/" == ret[:12]:
                ret = ret[12:]
            else:
                # x.com/
                ret = ret[6:]
            return ret

        elif self.type == "TV":
            ret = preprocess(self.link)
            ret = ret[10:]
            slashlocation = ret.find("/")
            if slashlocation != -1:
                ret = ret[:slashlocation]
            return ret

        elif self.type == "FB":
            if "profile.php?id=" in self.link:
                return "Facebook Profile"
            ret = preprocess(self.link)
            if "facebook.com/" == ret[:13]:
                ret = ret[13:]
            if "people/" == ret[:7] or "groups/" == ret[:7]:
                ret = ret[7:]
            slashlocation = ret.find("/")
            if slashlocation != -1:
                ret = ret[:slashlocation]

            return ret

        elif self.type == "IG":
            ret = preprocess(self.link)
            ret = ret[14:]
            return ret

        elif self.type == "YT":
            if "/channel/" in self.link:
                return "Youtube Channel"
            ret = self.link
            if ret[-7:] == "/videos":
                ret = ret[:-7]
            if "https://www.youtube.com/" == ret[:24]:
                ret = ret[24:]
            if "http://www.youtube.com/" == ret[:23]:
                ret = ret[23:]
            if "www.youtube.com/" == ret[:16]:
                ret = ret[16:]
            if "c/" == ret[:2]:
                ret = ret[2:]
            if "user/" == ret[:5]:
                ret = ret[5:]
            if "@" == ret[0]:
                ret = ret[1:]
            return ret

        elif self.type == "TT":
            ret = preprocess(self.link)
            ret = ret[12:]
            return ret

        elif self.type == "LI":
            ret = preprocess(self.link)
            if "linkedin.com/" == ret[:13]:
                ret = ret[13:]
            elif "linked.in/" == ret[:10]:
                ret = ret[10:]
            if "company/" == ret[:8]:
                ret = ret[8:]
            return ret

        elif self.type == "GH":
            ret = preprocess(self.link)
            ret = ret[11:]
            return ret

        elif self.type == "LT":
            ret = preprocess(self.link)
            ret = ret[10:]
            return ret

        else:
            return self.link

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

    def get_domain(self):  # TODO: This wastes the server's time, do this in JavaScript
        if "ultimate-robot-archive.fandom.com" in self.link:
            # this does not display properly with iconhorse
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


    def can_edit(self, a):  # TODO : lol
        return True

class HalloFame(models.Model):
    full_member = models.BooleanField()
    robot = models.ForeignKey(Robot, on_delete=models.CASCADE)

    def __str__(self):
        str(self.robot) + " " + ("hall of fame entry" if self.full_member else "hall of fame honorable mention")

def asciify(obj, commit=False):
    isVersion = isinstance(obj, Version)
    if isVersion:
        output = slugify(obj.robot_name).replace("-", " ")
    else:
        output = slugify(obj.name).replace("-", " ")

    if output != "":  # TODO: Add length threshold.
        if isVersion:
            low_name = obj.robot_name.lower()
        else:
            low_name = obj.name.lower()

        if low_name != output:
            low_name = low_name.replace(" & ", " and ")
            low_name = low_name.replace("&", " and ")
            low_name = re.sub(r"([0-9]+)% ", r"\1 percent ", low_name)
            output = slugify(low_name).replace("-", " ")  # TODO: proper unicode collation

            if commit and (isVersion and (obj.latin_robot_name is None or obj.latin_robot_name == "")) or \
                    ((not isVersion) and (obj.latin_name is None or obj.latin_name == "")):
                if isVersion:
                    obj.latin_robot_name = output
                else:
                    obj.latin_name = output
                obj.save()
        return output
    else:
        return ""


def timespan(dateA, dateB, text=False):
    def format_day(date):
        day_string = date.strftime("%d")
        if day_string[0] == "0":
            day_string = day_string[1]

        if day_string[-1] == "1":
            day_string += "st"
        elif day_string[-1] == "2":
            day_string += "nd"
        elif day_string[-1] == "3":
            day_string += "rd"
        else:
            day_string += "th"
        return day_string

    year = "%Y"

    if text:
        between = " to the "
        start = "from the "
        day_seperator = " of "
        month = "%B"
    else:
        between = " - "
        start = ""
        day_seperator = " "
        month = "%b"

    if dateA == None:
        if dateB == None:
            return "never"
        else:
            return ("on the " if text else "") + format_day(dateA) + day_seperator + dateA.strftime(month + " " + year)

    if dateA == dateB:
        return ("on the " if text else "") + format_day(dateA) + day_seperator + dateA.strftime(month + " " + year)
    elif dateA.month == dateB.month:
        return start + format_day(dateA) + between + format_day(dateB) + day_seperator + dateB.strftime(
            month + " " + year)
    elif dateA.year == dateB.year:
        return start + format_day(dateA) + day_seperator + dateA.strftime(month) + between + format_day(
            dateB) + day_seperator + dateB.strftime(month + " " + year)
    else:
        return start + format_day(dateA) + day_seperator + dateA.strftime(month + " " + year) + between + format_day(
            dateB) + day_seperator + dateB.strftime(month + " " + year)


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
