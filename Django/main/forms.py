from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.forms.utils import ErrorList

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


class SignupForm(forms.Form):
    version = forms.ModelChoiceField(queryset=Version.objects.none(), required=True)

    def save(self, contest, person):
        reg = Registration()
        reg.version = self.cleaned_data['version']
        reg.signee = person
        reg.contest = contest
        reg.save()


class AnonSignupForm(forms.Form):
    name = forms.CharField(max_length=255, required=True)
    email = forms.EmailField(required=True)
    team_name = forms.CharField(max_length=255, required=False)
    robot_name = forms.CharField(max_length=255, required=True)
    weapon_type = forms.CharField(max_length=20, required=True)

    def save(self, contest):
        weight = contest.weight_class
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
        pt = Person_Team.objects.create(person=p, team=t)
        reg = Registration()
        reg.version = v
        reg.signee = p
        reg.contest = contest

        pt.save()
        t.save()
        r.save()
        v.save()
        reg.save()


class NewRobotForm(forms.Form):
    name = forms.CharField(max_length=255, required=True)
    description = forms.CharField(widget=forms.Textarea, required=False)
    img = forms.ImageField(required=False)
    weapon_type = forms.CharField(max_length=20, required=True)
    weight_class = forms.ModelChoiceField(queryset=Weight_Class.objects.all().order_by("-recommended", "weight_grams"),
                                          required=True)
    opt_out = forms.BooleanField(required=False)

    def save(self, team):
        r = Robot()
        v = Version()
        r.name = self.cleaned_data['name']
        r.description = self.cleaned_data['description']
        r.opt_out = self.cleaned_data['opt_out']
        v.robot = r
        v.image = self.cleaned_data['img']
        v.weapon_type = self.cleaned_data['weapon_type']
        v.weight_class = self.cleaned_data['weight_class']
        v.team = team
        r.save()
        v.save()


class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ['name', 'logo', 'country', 'website']


class FranchiseForm(forms.ModelForm):
    class Meta:
        model = Franchise
        fields = ['name', 'description', 'logo', 'website']


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['name', 'description', 'logo', 'country', 'start_date', 'end_date', 'start_time', 'end_time',
                  'registration_open', 'registration_close', 'latitude', 'longitude']
        widgets = {
            'start_date': forms.SelectDateWidget(),
            'end_date': forms.SelectDateWidget(),
            'start_time': forms.TimeInput(attrs={'supports_microseconds': False}),
            'end_time': forms.TimeInput(attrs={'supports_microseconds': False}),
        }


class ContestForm(forms.ModelForm):
    class Meta:
        model = Contest
        fields = ["name", "fight_type", "auto_awards", "entries", "reserves", "weight_class"]


class FightForm(forms.ModelForm):
    class Meta:
        model = Fight
        fields = ["name", "fight_type", "method"]


class RobotFightForm(forms.ModelForm):
    class Meta:
        model = Fight_Version
        fields = ["version", "won", "tag_team"]


class MediaForm(forms.ModelForm):
    class Meta:
        model = Media
        fields = ['media_type', "internal", "external"]
