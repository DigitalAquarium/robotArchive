from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import *


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = UserCreationForm.Meta.fields

    def save(self, commit=True):
        user = super(RegistrationForm, self).save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class AnonSignupForm(forms.Form):
    name = forms.CharField(max_length=255, required=True)
    email = forms.EmailField(required=True)
    team_name = forms.CharField(max_length=255, required=False)
    robot_name = forms.CharField(max_length=255, required=True)
    weapon_type = forms.CharField(max_length=20, required=True)

    def save(self, weight):
        p = Person()
        p.name = self.cleaned_data['name']
        p.email = self.cleaned_data['email']
        t = Team()
        team_name = self.cleaned_data['team_name']
        if team_name is not None and team_name != "":
            t.name = team_name
        else:
            t.name = "Team " + self.cleaned_data['robot_name']
        r = Robot()
        r.name = self.cleaned_data['robot_name']
        v = Version()
        v.version_name = "v1"
        v.weapon_type = self.cleaned_data['weapon_type']
        v.weight_class = weight
        v.team = t
        v.robot = r
        p.save()
        t.save()
        t.members.add(p.id)
        t.save()
        r.save()
        v.save()
