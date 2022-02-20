from django.db import models
from django.conf import settings
import pycountry
import re

FULL_COMBAT = 'FC'
SPORTSMAN = 'SP'
PLASTIC = 'PL'
NON_COMBAT = 'NC'
FIGHT_TYPE_CHOICES = [
    (FULL_COMBAT, "Full Combat"),
    (SPORTSMAN, "Sportsman"),
    (PLASTIC, "Restricted Material"),
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


def get_flag(code):
    return settings.STATIC_URL + "flags/4x3/" + code.lower() + ".svg"


class Person(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    email = models.EmailField()

    def __str__(self):
        return self.name


class Team(models.Model):
    name = models.CharField(max_length=255)
    logo = models.ImageField(upload_to='team_logos/%Y/', blank=True)
    website = models.URLField(blank=True)
    country = models.CharField(max_length=2, choices=COUNTRY_CHOICES)
    members = models.ManyToManyField(Person, through="Person_Team")

    def __str__(self):
        return self.name

    def get_flag(self):
        return get_flag(self.country)

class Weight_Class(models.Model):
    name = models.CharField(max_length=30)
    weight_grams = models.IntegerField()
    recommended = models.BooleanField(default=False)

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


class Robot(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    wins = models.IntegerField(default=0)
    losses = models.IntegerField(default=0)
    ranking = models.FloatField(default=1000)
    opt_out = models.BooleanField(default=False)  # for opting out of rankings

    def __str__(self):
        return self.name

    def get_flag(self):
        try:
            return self.version_set.last().get_flag()
        except:
            return get_flag("xx")


class Version(models.Model):
    robot_name = models.CharField(max_length=255, blank=True)
    version_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='robot_images/%Y/', blank=True)
    weapon_type = models.CharField(max_length=20)
    robot = models.ForeignKey(Robot, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    weight_class = models.ForeignKey(Weight_Class, on_delete=models.CASCADE)

    def get_flag(self):
        return get_flag(self.team.country)

    def __str__(self):
        if self.robot_name != "":
            return self.robot_name
        else:
            return self.robot.name

    def get_full_name(self):
        # TODO: check where __str__ is used and should use this instead
        if self.robot_name != "":
            return self.robot_name + " " + self.version_name
        else:
            return self.robot.name + " " + self.version_name


class Franchise(models.Model):
    name = models.CharField(max_length=50)
    logo = models.ImageField(upload_to='franchise_logos/%Y/', blank=True)
    website = models.URLField(blank=True)
    description = models.TextField(blank=True)
    members = models.ManyToManyField(Person, through="Person_Franchise")

    def is_member(self, person):
        return len(Person_Franchise.objects.filter(person=person, franchise=self)) > 0

    def __str__(self):
        return self.name


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
    country = models.CharField(max_length=2, choices=COUNTRY_CHOICES)
    latitude = models.FloatField()
    longitude = models.FloatField()
    franchise = models.ForeignKey(Franchise, on_delete=models.CASCADE)

    def __str__(self):
        return self.name

    def get_flag(self):
        return get_flag(self.country)


class Contest(models.Model):
    name = models.CharField(max_length=255, blank=True)
    fight_type = models.CharField(max_length=2, choices=FIGHT_TYPE_CHOICES + [("MU", "Multiple Types")])
    auto_awards = models.BooleanField()
    entries = models.PositiveSmallIntegerField(default=0)
    reserves = models.PositiveSmallIntegerField(default=0, blank=True)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    weight_class = models.ForeignKey(Weight_Class, on_delete=models.CASCADE)

    def __str__(self):
        if self.name is not None and self.name != "":
            return self.name
        else:
            return self.weight_class.name


class Registration(models.Model):
    signup_time = models.DateTimeField(auto_now_add=True)
    approved = models.BooleanField(default=False)
    reserve = models.BooleanField(default=False)
    version = models.ForeignKey(Version, on_delete=models.CASCADE)
    signee = models.ForeignKey(Person, on_delete=models.CASCADE)
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE)

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
        ("NM", "No Method Declared"),
    ]
    # Media Types:
    # LI: Local Image
    # EI: External Image
    # LV: Local Video
    # IF: Iframe embed Such as YouTube or Vimeo
    # IG: Instagram
    # TW: Twitter
    # TT: Tiktok
    # FB: Facebook
    # UN: unknown
    method = models.CharField(max_length=2, choices=METHOD_CHOICES, default="NM")
    name = models.CharField(max_length=255)
    fight_type = models.CharField(max_length=2, choices=FIGHT_TYPE_CHOICES)
    number = models.IntegerField()
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE)
    competitors = models.ManyToManyField(Version, through="Fight_Version")
    internal_media = models.FileField(upload_to='fight_media/%Y/', blank=True)
    external_media = models.URLField(blank=True)

    def format_external_media(self):
        if re.match("(https?://)?(www\.)?youtu\.?be",
                    self.external_media) is not None and "embed" not in self.external_media:  # This could break in the rare case the url contains embed for no reason
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

    def get_media_type(self):
        if bool(self.internal_media):
            # https://developer.mozilla.org/en-US/docs/Web/Media/Formats/Containers
            if self.internal_media.url[-4:] == ".mp4" or self.internal_media.url[-4:] == ".ogg":
                return "LV"
            elif self.internal_media.url[-5:] == ".webm":
                return "LV"
            else:
                # Local Image
                return "LI"

        elif self.external_media is not None:
            if "twitter" in self.external_media:
                return "TW"
            elif "tiktok" in self.external_media:
                return "TT"
            elif "instagram" in self.external_media:
                return "IG"
            elif "facebook" in self.external_media:
                return "FB"
            elif re.search("youtu\.?be", self.external_media) is not None:
                return "IF"
            # https://developer.mozilla.org/en-US/docs/Web/Media/Formats/Image_types
            elif self.external_media[-4:] in [".gif", ".jpg", ".pjp", ".gif", ".png", ".svg"]:
                return "EI"
            elif self.external_media[-5:] in [".jpeg", ".jfif", ".webp"]:
                return "EI"
            elif self.external_media[-6:] == ".pjpeg":
                return "EI"
            else:
                "UN"
        else:
            "Error"

    def get_tt_id(self):
        # https: // www.tiktok.com / @ battlebots / video / 7060864801462963502 - Example video
        output = ""
        for i in range(len(self.external_media) - 1, 0, -1):
            if self.external_media[i] not in ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]:
                break
            output = self.external_media[i] + output
        return output

    def __str__(self):
        # This can cause a recursian error
        try:
            if self.name is not None and self.name != "":
                return self.name
            elif self.competitors.count() >= 2:  # TODO: Fix this for team stuff
                ret = ""
                for version in self.competitors.all():
                    if version.robot_name != "" and version.robot_name is not None:
                        ret += " vs " + version.robot_name  # __str__()
                    else:
                        ret += " vs " + version.robot.name
                return ret[4:]
            else:
                return "A fight with less than two robots"
        except:
            return "Trying to name this fight is causing errors (Oh no!)"


class Award(models.Model):
    name = models.CharField(max_length=255)
    award_type = models.PositiveSmallIntegerField()  # 0 other, 1 first place, 2 second place, 3 third place
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE)
    version = models.ForeignKey(Version, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class Person_Team(models.Model):
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)


class Person_Franchise(models.Model):
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    franchise = models.ForeignKey(Franchise, on_delete=models.CASCADE)


class Fight_Version(models.Model):
    won = models.BooleanField()
    tag_team = models.PositiveSmallIntegerField(
        default=0)  # matching number, matching side on a tag team match, 0 for free for all fights
    ranking_change = models.FloatField(default=0)
    fight = models.ForeignKey(Fight, on_delete=models.CASCADE)
    version = models.ForeignKey(Version, on_delete=models.CASCADE)

    def __str__(self):
        return self.version.__str__() + " in |" + self.fight.__str__() + "|"
