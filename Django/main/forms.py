from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist, ValidationError

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
        t.country = "XX"
        team_name = self.cleaned_data['team_name']
        if team_name is not None and team_name != "":
            t.name = team_name
        else:
            t.name = "Team " + self.cleaned_data['robot_name']
        r = Robot()
        r.name = self.cleaned_data['robot_name']
        v = Version()
        v.name = "v1"
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


class NewVersionForm(forms.Form):
    robot_name = forms.CharField(max_length=255, required=False)
    version_name = forms.CharField(max_length=255, required=True)
    description = forms.CharField(widget=forms.Textarea, required=False)
    img = forms.ImageField(required=False)
    weapon_type = forms.CharField(max_length=20, required=True)
    weight_class = forms.ModelChoiceField(queryset=Weight_Class.objects.all().order_by("-recommended", "weight_grams"),
                                          required=True)
    team = forms.ModelChoiceField(queryset=None, required=True)

    def save(self, robot):
        v = Version()
        v.robot = robot
        v.robot_name = self.cleaned_data['robot_name']
        v.name = self.cleaned_data['name']
        v.image = self.cleaned_data['img']
        v.weapon_type = self.cleaned_data['weapon_type']
        v.weight_class = self.cleaned_data['weight_class']
        v.team = self.cleaned_data['team']
        v.save()
        return v


class RobotForm(forms.ModelForm):
    class Meta:
        model = Robot
        fields = ['name', 'description', "opt_out"]


class VersionForm(forms.ModelForm):
    class Meta:
        model = Version
        fields = ["robot_name", "name", "description", "image", "weapon_type", "weight_class"]


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
        fields = ["name", "fight_type", "entries", "reserves", "weight_class"]


class FightForm(forms.ModelForm):
    class Meta:
        model = Fight
        fields = ["name", "fight_type", "method", "internal_media", "external_media"]



class RobotFightForm(forms.ModelForm):
    class Meta:
        model = Fight_Version
        fields = ["version", "won", "tag_team"]


class AwardForm(forms.ModelForm):
    class Meta:
        model = Award
        fields = ['name', 'award_type', 'contest', 'version']


class PersonForm(forms.ModelForm):
    class Meta:
        model = Person
        fields = ['name', 'email', 'public']


class WeightClassForm(forms.Form):
    name = forms.CharField(max_length=30, required=True)
    weight_grams = forms.IntegerField(initial=0, min_value=0, required=True)

    # Requires Javascript
    # weight_kg = forms.IntegerField(initial=0, min_value=0)
    # weight_lbs = forms.IntegerField(initial=0, min_value=0)

    def save(self):
        wc = Weight_Class()
        wc.name = self.cleaned_data['name']
        wc.weight_grams = self.cleaned_data['weight_grams']
        wc.save()


class TransferRobotForm(forms.Form):
    team_name = forms.CharField(max_length=255, required=True)
    team_id = forms.IntegerField(required=True)

    def clean(self):
        cleaned_data = super().clean()
        team_name = cleaned_data.get('team_name')
        team_id = cleaned_data.get('team_id')
        if team_name and team_id:
            try:
                Team.objects.get(name=team_name, pk=team_id)
            except ObjectDoesNotExist:
                raise ValidationError(
                    "A team with these details could not be found."
                )

    def save(self):
        team_name = self.cleaned_data.get('team_name')
        team_id = self.cleaned_data.get('team_id')
        new_team = Team.objects.get(name=team_name, pk=team_id)
        return new_team
