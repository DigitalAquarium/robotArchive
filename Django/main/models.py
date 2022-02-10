from django.db import models
from django.conf import settings
import pycountry

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
    ('XX', "Unspecified")
])


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


class Version(models.Model):
    robot_name = models.CharField(max_length=255, blank=True)
    version_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='robot_images/%Y/', blank=True)
    weapon_type = models.CharField(max_length=20)
    robot = models.ForeignKey(Robot, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    weight_class = models.ForeignKey(Weight_Class, on_delete=models.CASCADE)

    def __str__(self):
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
    name = models.CharField(max_length=50)
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


class Contest(models.Model):
    name = models.CharField(max_length=50, blank=True)
    fight_type = models.CharField(max_length=2, choices=FIGHT_TYPE_CHOICES + [("MU", "Multiple Types")])
    auto_awards = models.BooleanField()
    entries = models.PositiveSmallIntegerField()
    reserves = models.PositiveSmallIntegerField(blank=True)
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


class Media(models.Model):
    TYPE_CHOICES = [
        ("LI", "Local Image"),
        ("EI", "External Image"),
        ("LV", "Local Video"),
        ("FB", "Facebook"),
        ("IF", "IFrame Embed"),  # Such as YouTube or Vimeo
        ("IG", "Instagram"),
        ("TW", "Twitter"),
        ("TT", "TikTok"),
    ]
    media_type = models.CharField(max_length=2, choices=TYPE_CHOICES)
    internal = models.FileField(upload_to='fight_media/%Y/', blank=True)
    external = models.URLField(blank=True)


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
    method = models.CharField(max_length=2, choices=METHOD_CHOICES, default="NM")
    name = models.CharField(max_length=100)
    fight_type = models.CharField(max_length=2, choices=FIGHT_TYPE_CHOICES)
    number = models.IntegerField()
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE, blank=True)
    competitors = models.ManyToManyField(Version, through="Fight_Version")
    media = models.ForeignKey(Media, blank=True, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


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
    tag_team = models.PositiveSmallIntegerField()  # matching number, matching side on a tag team match, 0 for free for all fights
    fight = models.ForeignKey(Fight, on_delete=models.CASCADE)
    version = models.ForeignKey(Version, on_delete=models.CASCADE)
