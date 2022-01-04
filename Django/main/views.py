from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from .models import *
from .forms import *
from django.contrib.auth.models import User
from django.urls import reverse
from django.views import generic
from django.template import RequestContext
from django.utils import timezone
import datetime

class IndexView(generic.ListView):
    template_name = "main/index.html"
    context_object_name = "upcoming_event_list"
    print("cringe")
    def get_queryset(self):
        return Event.objects.filter(start_date__gte=datetime.date.today()).order_by("start_date")[:5]

class EventDetailView(generic.DetailView):
    model = Event
    template_name = "main/eventdetail.html"

def contestSignup(response,contest_id):
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
    return render(response,"main/contestsignup.html",{"anon_form":anon_form,"contest":contest})

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
    return render(response,"main/register.html",{"form":form})

class RobotIndex(generic.ListView):
    template_name = "main/robotindex.html"
    print("poop")
    context_object_name = "robot_list"
    def get_queryset(self):
        return Robot.objects.order_by("name")[:5]

class RobotDetailView(generic.DetailView):
    model = Robot
    template_name = "main/robotdetail.html"
