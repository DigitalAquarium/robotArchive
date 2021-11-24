from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from .models import *
from .forms import *
from django.contrib.auth.models import User
from django.urls import reverse
from django.views import generic
from django.template import RequestContext

import datetime

class IndexView(generic.ListView):
    template_name = "main/index.html"
    context_object_name = "upcoming_event_list"

    def get_queryset(self):
        return Event.objects.filter(start_date__gte=datetime.date.today()).order_by("start_date")[:5]

class EventDetailView(generic.DetailView):
    model = Event
    template_name = "main/eventdetail.html"

class ContestSignupView(generic.DetailView):
    model = Contest
    template_name = "main/contestsignupform.html"

def contestSignup(request,contest_id):
    return HttpResponseRedirect(reverse('main:contestsignupform',args=(Contest.id,)))

def register(response):
    if response.method == "POST":
        form = RegistrationForm(response.POST)
        if form.is_valid():
            form.save
        return redirect("main:index")
    else:
        form = RegistrationForm()
    return render(response,"main/register.html",{"form":form})

#class LoginView()
