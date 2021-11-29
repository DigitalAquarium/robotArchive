from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    class Meta:
        model = User
        fields = UserCreationForm.Meta.fields
    def save(self,commit=True):
        user = super(RegistrationForm,self).save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user

class AnonSignupForm(forms.Form):
    name = forms.CharField(max_length = 255,required=True)
    email = forms.EmailField(required=True)
    team_name = forms.CharField(max_length = 255,required=False)
    robot_name = forms.CharField(max_length = 255,required=True)
    weapon_type = forms.CharField(max_length = 20,required=True)
