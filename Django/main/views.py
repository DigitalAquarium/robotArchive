import datetime

from django.urls import reverse

from EventManager import stuff

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone
from django.views import generic
from django.db.models import Q

from .forms import *


class IndexView(generic.ListView):
    template_name = "main/index.html"
    context_object_name = "upcoming_event_list"

    def get_queryset(self):
        return Event.objects.filter(start_date__gte=datetime.date.today()).order_by("start_date")[:5]


class EventIndexView(generic.ListView):
    template_name = "main/event_index.html"
    context_object_name = "event_list"

    def get_queryset(self):
        return Event.objects.all


def event_detail_view(request, event_id):
    me = Person.objects.get(user=request.user)
    event = Event.objects.get(pk=event_id)
    fran = event.franchise
    can_change = fran.is_member(me)
    return render(request, "main/event_detail.html",
                  {"event": event,
                   "map": stuff.map,
                   "can_change": can_change,
                   "reg_open": event.registration_open < timezone.now() < event.registration_close})


def new_event_view(request, franchise_id):
    fran = Franchise.objects.get(pk=franchise_id)  # TODO: Add verification
    if request.method == "POST":
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.franchise = fran
            event.save()
            return redirect("main:eventDetail", event.id)
    else:
        form = EventForm()
    return render(request, "main/new_event.html", {"form": form, "fran": fran})


def modify_event_view(request, event_id):
    event = Event.objects.get(pk=event_id)
    if request.method == "POST":
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            new = form.save()
            return redirect("main:eventDetail", new.id)
    else:
        form = EventForm(instance=event)
    return render(request, "main/edit_event.html", {"form": form, "event_id": event_id})


def contest_signup_view(response, contest_id):
    contest = Contest.objects.get(pk=contest_id)

    if timezone.now() > contest.event.registration_close:
        return redirect("%s?m=%s" % (reverse("main:message"), "Registration for this contest has closed."))
    elif timezone.now() < contest.event.registration_open:
        return redirect("%s?m=%s" % (reverse("main:message"), "Registration for this contest has not yet opened."))

    if contest.entries != 0 and (contest.registration_set.count() >= contest.entries + contest.reserves):
        return redirect("%s?m=%s" % (reverse("main:message"), "Entries for this contest are full."))

    if response.user.is_authenticated:
        user = response.user
        me = Person.objects.get(user=user)
        if response.method == "POST":
            form = SignupForm(response.POST)
            t = Person_Team.objects.filter(person=me)
            teams = []
            for result in t:
                teams.append(result.team)
            form.fields['version'].queryset = Version.objects.filter(team__in=teams)
            if form.is_valid():
                if contest.entries != 0 and (contest.registration_set.count() >= contest.entries + contest.reserves):
                    # A Second Check in case slots filled up between the time the page was loaded and the time the
                    # form was completed
                    return redirect("%s?m=%s" % (reverse("main:message"), "Entries for this contest are full."))
                form.save(contest, me)
                return redirect("main:index")
        else:
            form = SignupForm()
            t = Person_Team.objects.filter(person=me)
            teams = []
            for result in t:
                teams.append(result.team)
            form.fields['version'].queryset = Version.objects.filter(team__in=teams,
                                                                     weight_class=contest.weight_class)
        return render(response, "main/contest_signup.html", {"form": form, "contest": contest})

    else:
        if response.method == "POST":
            anon_form = AnonSignupForm(response.POST)
            if anon_form.is_valid():
                if contest.entries != 0 and (contest.registration_set.count() >= contest.entries + contest.reserves):
                    # A Second Check in case slots filled up between the time the page was loaded and the time the
                    # form was completed
                    return redirect("%s?m=%s" % (reverse("main:message"), "Entries for this contest are full."))
                anon_form.save(contest)
                return redirect("main:index")
        else:
            anon_form = AnonSignupForm()
        return render(response, "main/contest_signup.html", {"anon_form": anon_form, "contest": contest})


def contest_detail_view(request, contest_id):
    contest = Contest.objects.get(pk=contest_id)
    fights = Fight.objects.filter(contest=contest)
    registrations = Registration.objects.filter(contest=contest)
    return render(request, "main/contest_detail.html",
                  {"contest": contest, "fights": fights, "applications": registrations,
                   "future": contest.event.registration_open > timezone.now()})


def new_contest_view(request, event_id):
    event = Event.objects.get(pk=event_id)  # TODO: Add verification
    if request.method == "POST":
        form = ContestForm(request.POST)
        if form.is_valid():
            contest = form.save(commit=False)
            contest.event = event
            contest.save()
            return redirect("main:eventDetail", event.id)
    else:
        form = ContestForm()
    return render(request, "main/new_contest.html", {"form": form, "event": event})


def edit_contest_view(request, contest_id):
    contest = Contest.objects.get(pk=contest_id)
    if request.method == "POST":
        form = ContestForm(request.POST, instance=contest)
        if form.is_valid():
            form.save()
            return redirect("main:eventDetail", contest.event.id)
    else:
        form = ContestForm(instance=contest)
    return render(request, "main/edit_contest.html", {"form": form, "contest_id": contest_id})


def register(response):
    if response.method == "POST":
        form = RegistrationForm(response.POST)
        name = response.POST["name"]
        email = response.POST["email"]
        if form.is_valid():
            user = form.save()
            p = Person()
            p.name = name
            p.email = email
            p.user_id = user.id
            p.save()
            return redirect("main:index")
    else:
        form = RegistrationForm()
    return render(response, "main/register.html", {"form": form})


def robot_index_view(request):
    name = request.GET.get("name") or ""
    page = request.GET.get("page") or 1
    page = int(page)
    num = 50
    robot_list = Robot.objects.filter(name__icontains=name)
    version_thing = Robot.objects.filter(version__robot_name__icontains=name)
    robot_list = robot_list.union(version_thing).order_by("name")
    results = len(robot_list)
    robot_list = robot_list[num * (page - 1):num * page]

    return render(request, "main/robot_index.html",
                  {"robot_list": robot_list, "page":page, "pages": results // num if results % num == 0 else results // num + 1})


class RobotDetailView(generic.DetailView):
    model = Robot
    template_name = "main/robot_detail.html"


@login_required(login_url='/accounts/login/')
def my_teams_view(request):
    me = Person.objects.get(user=request.user)
    p_t = Person_Team.objects.filter(person=me)
    teams = []
    for value in p_t:
        teams.append(value.team)
    return render(request, "main/my_teams.html", {"teams": teams})


def team_detail_view(request, team_id):
    me = Person.objects.get(user=request.user)
    team = Team.objects.get(pk=team_id)
    member = len(Person_Team.objects.filter(person=me, team=team)) > 0  # TODO: Potentially a bad check
    # for if you can edit and such, should probably use a better system in future
    return render(request, "main/team_detail.html", {"team": team, "member": member})


@login_required(login_url='/accounts/login/')
def new_robot_view(request, team_id):
    team = Team.objects.get(pk=team_id)  ##TODO: Add verification
    if request.method == "POST":
        form = NewRobotForm(request.POST, request.FILES)
        if form.is_valid():
            form.save(team)
            return redirect("main:index")
    else:
        form = NewRobotForm()
    return render(request, "main/new_robot.html", {"form": form, "team": team})


def team_edit_view(request, team_id=None):
    if request.method == "POST":
        if team_id is None:
            form = TeamForm(request.POST)
        else:
            team = Team.objects.get(pk=team_id)
            form = TeamForm(request.POST, instance=team)
        if form.is_valid():
            new = form.save()
            if team_id is None:
                person = Person.objects.get(user=request.user)
                Person_Team.objects.create(team=new, person=person)
            return redirect("main:index")
    else:
        if team_id is None:
            form = TeamForm()
        else:
            team = Team.objects.get(pk=team_id)
            form = TeamForm(instance=team)
    if team_id is None:
        return render(request, "main/edit_team.html", {"form": form, "team_id": team_id})
    else:
        return render(request, "main/edit_team.html", {"form": form, "team_id": team_id})


def franchise_modify_view(request, franchise_id=None):
    if request.method == "POST":
        if franchise_id is None:
            form = FranchiseForm(request.POST)
        else:
            franchise = Franchise.objects.get(franchise_id)
            form = FranchiseForm(request.POST, instance=franchise)
        if form.is_valid():
            new = form.save()
            if franchise_id is None:
                person = Person.objects.get(user=request.user)
                Person_Franchise.objects.create(franchise=new, person=person)
            return redirect("main:index")
    else:
        if franchise_id is None:
            form = TeamForm()
        else:
            franchise = Franchise.objects.get(pk=franchise_id)
            form = FranchiseForm(instance=franchise)
    if franchise_id is None:
        return render(request, "main/modify_franchise.html", {"form": form, "franchise_id": franchise_id})
    else:
        return render(request, "main/modify_franchise.html", {"form": form, "franchise_id": franchise_id})


@login_required(login_url='/accounts/login/')
def my_franchises_view(request):
    me = Person.objects.get(user=request.user)
    p_f = Person_Franchise.objects.filter(person=me)
    frans = []
    for value in p_f:
        frans.append(value.franchise)
    return render(request, "main/my_franchises.html", {"frans": frans})


def franchise_detail_view(request, fran_id):
    me = Person.objects.get(user=request.user)
    fran = Franchise.objects.get(pk=fran_id)
    member = fran.is_member(me)  # TODO: Potentially a bad check
    # for if you can edit and such, should probably use a better system in future
    return render(request, "main/franchise_detail.html", {"fran": fran, "member": member})


def new_fight_view(request, contest_id):  # TODO: Make sure you can't add the same Version to the same fight.
    contest = Contest.objects.get(pk=contest_id)
    f = Fight()
    f.contest = contest
    f.number = 1
    for prevFight in contest.fight_set.all():  # Should Probably find a more efficient way of doing this but it'll work for now
        if prevFight.number >= f.number:
            f.number = prevFight.number + 1
    if contest.fight_type == "MU":
        f.save()
        return redirect("main:editJustFight", f.id)
    else:
        f.fight_type = contest.fight_type
        f.save()
        return redirect("main:editWholeFight", f.id)


def fight_editj_view(request, fight_id):  # Just the Fight
    fight = Fight.objects.get(pk=fight_id)
    if request.method == "POST":
        form = FightForm(request.POST, request.FILES, instance=fight)
        if form.is_valid():
            form.save()
            return redirect("main:editWholeFight", fight_id)
    else:
        form = FightForm(instance=fight)
        return render(request, "main/modify_fight.html", {"form": form, "fight_id": fight_id})


def fight_edith_view(request, fight_id):  # The fight and the robots and media etc
    fight = Fight.objects.get(pk=fight_id)
    return render(request, "main/edit_whole_fight.html", {"fight": fight})


def modify_robot_version_view(request, fight_id, vf_id=None):
    fight = Fight.objects.get(pk=fight_id)
    registered = Version.objects.filter(registration__contest=fight.contest.id)
    if vf_id is not None:
        vf = Fight_Version.objects.get(pk=vf_id)
    else:
        vf = Fight_Version()
        vf.fight = fight
    form = RobotFightForm(request.POST or None, instance=vf)
    if form.is_valid():
        form.save()
        return redirect("main:editWholeFight", fight_id)
    form.fields['version'].queryset = registered

    return render(request, "main/modify_robot_version.html",
                  {"form": form, "fight_id": fight_id, "fight_version_id": vf_id})
    # TODO: This is basically identical to modify_fight and probably many more


def message_view(request):
    if request.method == "GET":
        message = request.GET.get("m")
        return render(request, "main/message.html", {"text": message})
    else:
        return redirect("main:index")
