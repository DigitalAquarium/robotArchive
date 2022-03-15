from django.contrib import admin
from .models import *


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    pass


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    pass


@admin.register(Robot)
class RobotAdmin(admin.ModelAdmin):
    pass


@admin.register(Version)
class VersionAdmin(admin.ModelAdmin):
    search_fields = ['robot_name', 'robot__name']


@admin.register(Franchise)
class FranchiseAdmin(admin.ModelAdmin):
    pass


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    pass


@admin.register(Weight_Class)
class WeightClassAdmin(admin.ModelAdmin):
    pass


@admin.register(Contest)
class ContestAdmin(admin.ModelAdmin):
    pass


@admin.register(Person_Team)
class PersonTeamAdmin(admin.ModelAdmin):
    pass


@admin.register(Fight)
class FightAdmin(admin.ModelAdmin):
    search_fields = ['contest__event__name']


@admin.register(Person_Franchise)
class PersonFranchiseAdmin(admin.ModelAdmin):
    pass


@admin.register(Fight_Version)
class FightVersionAdmin(admin.ModelAdmin):
    search_fields = ['version__robot_name', 'version__robot__name']


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    pass


@admin.register(Award)
class AwardAdmin(admin.ModelAdmin):
    search_fields = ['name', 'event__name']
