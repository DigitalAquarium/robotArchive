from django.db import models
import pycountry

FULL_COMBAT = 'FC'
SPORTSMAN = 'SP'
PLASTIC = 'PL'
NON_COMBAT = 'NC'
FIGHT_TYPE_CHOICES = [
    (FULL_COMBAT, "Full Combat"),
    (SPORTSMAN, "Sportsman"),
    (PLASTIC, "Restricted Material"),
    (NON_COMBAT, "Non-Combat")
    ]

COUNTRY_CHOICES = []
for country in pycountry.countries:
    COUNTRY_CHOICES.append((country.alpha_2,country.name))
COUNTRY_CHOICES.extend([
    ('XE',"England"),
    ('XS',"Scotland"),
    ('XW',"Wales"),
    ('XI',"Northern Ireland")
    ])

class Person(models.Model):
    name = models.CharField(max_length = 255)
    email = models.EmailField()

class Team(models.Model):
    name = models.CharField(max_length = 255)
    logo = models.ImageField(upload_to='team_logos/%Y/')
    website = models.URLField()
    country = models.CharField(max_length = 2,choices = COUNTRY_CHOICES)
    members = models.ManyToManyField(Person,through="Person_Team")
    
class Weight_Class(models.Model):
    name = models.CharField(max_length = 30)
    weight_grams = models.IntegerField()

class Robot(models.Model):
    name = models.CharField(max_length = 255)
    description = models.TextField()
    wins = models.IntegerField()
    losses = models.IntegerField()
    ranking = models.FloatField()
    opt_out = models.BooleanField() # for opting out of rankings

class Version(models.Model):
    robot_name = models.CharField(max_length = 255)
    version_name = models.CharField(max_length = 255)
    description = models.TextField()
    image = models.ImageField(upload_to='robot_images/%Y/')
    weapon_type = models.CharField(max_length = 20)
    robot = models.ForeignKey(Robot, on_delete = models.CASCADE)
    team = models.ForeignKey(Team, on_delete = models.CASCADE)
    weight_class = models.ForeignKey(Weight_Class, on_delete = models.CASCADE)

class Franchise(models.Model):
    name = models.CharField(max_length=50)
    logo = models.ImageField(upload_to='franchise_logos/%Y/')
    website = models.URLField()
    description = models.TextField()
    members = models.ManyToManyField(Person,through="Person_Franchise")

class Event(models.Model):
    name = models.CharField(max_length=50)
    logo = models.ImageField(upload_to='event_logos/%Y/')
    ruleset = models.FileField(upload_to='event_rulesets')
    start_date = models.DateField()
    end_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    registration_close = models.DateTimeField()
    franchise = models.ForeignKey(Franchise,on_delete = models.CASCADE)
    #Location!!!!!!!!!

class Contest(models.Model):
    fight_type = models.CharField(max_length = 2, choices = FIGHT_TYPE_CHOICES)
    auto_awards = models.BooleanField()
    event = models.ForeignKey(Event,on_delete = models.CASCADE)
    weight_class = models.ForeignKey(Weight_Class,on_delete = models.CASCADE)

class Registration(models.Model):
    approved = models.BooleanField()
    reserve = models.BooleanField()
    version = models.ForeignKey(Version,on_delete = models.CASCADE)
    signee = models.ForeignKey(Person,on_delete = models.CASCADE)
    event = models.ForeignKey(Event,on_delete = models.CASCADE)
    contest = models.ForeignKey(Contest,on_delete = models.CASCADE)

class Fight(models.Model):
    '''METHOD_CHOICES = [
        ("KO","Knockout"),
        ("JD","Judge's Decision"),
        ("TO","Tap Out"),
        ("OA","Out of the Arena"),
        ("PT","Pit")
        ]
    method = models.CharField(max_length = 2, choices = METHOD_CHOICES)'''
    name = models.CharField(max_length=100)
    fight_type = models.CharField(max_length = 2, choices = FIGHT_TYPE_CHOICES)
    media_internal = models.FileField(upload_to='fight_media/%Y/')
    media_external = models.URLField();
    event = models.ForeignKey(Event,on_delete = models.CASCADE)
    contest = models.ForeignKey(Contest,on_delete = models.CASCADE)
    competitors = models.ManyToManyField(Version,through="Fight_Version")

class Award(models.Model):
    name = models.CharField(max_length = 255)
    award_type = models.PositiveSmallIntegerField()#0 other, 1 first place, 2 second place, 3 thrid place
    contest = models.ForeignKey(Contest,on_delete = models.CASCADE)
    version = models.ForeignKey(Version,on_delete = models.CASCADE)

class Person_Team(models.Model):
    permissions = models.PositiveSmallIntegerField()
    person = models.ForeignKey(Person,on_delete = models.CASCADE)
    team = models.ForeignKey(Team,on_delete = models.CASCADE)

class Person_Franchise(models.Model):
    permissions = models.PositiveSmallIntegerField()
    person = models.ForeignKey(Person,on_delete = models.CASCADE)
    franchise = models.ForeignKey(Franchise,on_delete = models.CASCADE)

class Fight_Version(models.Model):
    won = models.BooleanField()
    tag_team = models.PositiveSmallIntegerField() # matching number, matching side on a tag team match, null for free for all fights
    fight = models.ForeignKey(Fight,on_delete = models.CASCADE)
    version = models.ForeignKey(Version,on_delete = models.CASCADE)
