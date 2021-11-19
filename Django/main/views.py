from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from .models import *
from django.contrib.auth.models import User
from django.urls import reverse
from django.views import generic
import datetime

class IndexView(generic.ListView):
    template_name = "main/index.html"
    context_object_name = "upcoming_event_list"

    def get_queryset(self):
        return Event.objects.filter(start_date__gte=datetime.date.today()).order_by('start_date')[:5]

class EventDetailView(generic.DetailView):
    model = Event
    template_name = "main/eventdetail.html"

class ContestSignupView(generic.DetailView):
    model = Contest
    template_name = "main/contestsignup.html"


#class LoginView()
