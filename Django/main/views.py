import datetime

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


class EventDetailView(generic.DetailView):
    model = Event
    template_name = "main/eventdetail.html"


def contestSignup(response, contest_id):
    contest = Contest.objects.get(pk=contest_id)
    if timezone.now() > contest.event.registration_close:
        return redirect("main:index")
    if response.method == "POST":
        anon_form = AnonSignupForm(response.POST)
        if anon_form.is_valid():
            anon_form.save(contest.weight_class)
            return redirect("main:index")
    else:
        anon_form = AnonSignupForm()
    return render(response, "main/contestsignup.html", {"anon_form": anon_form, "contest": contest})


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


class RobotIndex(generic.ListView):
    template_name = "main/robotindex.html"
    context_object_name = "robot_list"

    def get_queryset(self):
        return Robot.objects.order_by("name")[:5]


class RobotDetailView(generic.DetailView):
    model = Robot
    template_name = "main/robotdetail.html"


@login_required(login_url='/accounts/login/')
def myteamsview(request):
    me = Person.objects.get(user=request.user)
    p_t = Person_Team.objects.filter(person=me)
    teams = []
    for value in p_t:
        teams.append(value.team)
    return render(request, "main/myteams.html", {"teams": teams})


def TeamDetailView(request, team_id):
    me = Person.objects.get(user=request.user)
    team = Team.objects.get(pk=team_id)
    member = len(Person_Team.objects.filter(person=me, team=team)) > 0 #TODO: Potentially a bad check for if you can edit and such, should probably use a better system in future
    return render(request, "main/teamdetail.html", {"team": team, "member": member})

def newrobot(response, team_id):
    team = Team.objects.get(pk=team_id)
    if response.method == "POST":
        form = NewRobotForm(response.POST)
        if form.is_valid():
            form.save(team)
            return redirect("main:index")
    else:
        form = NewRobotForm()
    return render(response, "main/newrobot.html", {"form": form, "team": team})
