import datetime
from EventManager import stuff

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import timezone
from django.views import generic

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
    event = Event.objects.get(pk=event_id)
    return render(request, "main/event_detail.html", {"event": event, "map": stuff.map})


def contest_signup_view(response, contest_id):
    contest = Contest.objects.get(pk=contest_id)
    if timezone.now() > contest.event.registration_close:
        return redirect("main:index")

    if response.user.is_authenticated:
        user = response.user
        me = Person.objects.get(user=user)
        if response.method == "POST":
            form = SignupForm(response.POST)
            if form.is_valid():
                form.save(contest, me)
                return redirect("main:index")
        else:
            form = SignupForm()
            t = Person_Team.objects.filter(me)
            teams = []
            for result in t:
                teams.append(result.team)
            form.fields['version'].queryset = Version.objects.filter(team__in=teams)
        return render(response, "main/contest_signup.html", {"form": form, "contest": contest})

    else:
        if response.method == "POST":
            anon_form = AnonSignupForm(response.POST)
            if anon_form.is_valid():
                anon_form.save(contest)
                return redirect("main:index")
        else:
            anon_form = AnonSignupForm()
        return render(response, "main/contest_signup.html", {"anon_form": anon_form, "contest": contest})


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


class RobotIndexView(generic.ListView):
    template_name = "main/robot_index.html"
    context_object_name = "robot_list"

    def get_queryset(self):
        return Robot.objects.order_by("name")[:5]


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
        form = TeamForm(request.POST)
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
        form = FranchiseForm(request.POST)
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
            form = FranchiseForm(instance=Franchise)
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
    member = len(Person_Franchise.objects.filter(person=me, franchise=fran)) > 0  # TODO: Potentially a bad check
    # for if you can edit and such, should probably use a better system in future
    return render(request, "main/franchise_detail.html", {"fran": fran, "member": member})
