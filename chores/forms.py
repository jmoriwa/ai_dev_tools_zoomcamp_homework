from django import forms

from .accounts import validate_pin
from .models import User


def pin_field(label):
    return forms.CharField(label=label, strip=False, validators=[validate_pin], widget=forms.PasswordInput(attrs={"inputmode": "numeric", "autocomplete": "new-password"}))


class LoginForm(forms.Form):
    username = forms.CharField(max_length=150, strip=False)
    pin = forms.CharField(label="PIN", strip=False, widget=forms.PasswordInput(attrs={"inputmode": "numeric", "autocomplete": "current-password"}))


class MemberForm(forms.Form):
    username = forms.CharField(max_length=150, strip=False, validators=User._meta.get_field("username").validators)
    pin = pin_field("Initial PIN")


class ChangePINForm(forms.Form):
    current_pin = forms.CharField(label="Current PIN", strip=False, widget=forms.PasswordInput(attrs={"inputmode": "numeric", "autocomplete": "current-password"}))
    new_pin = pin_field("New PIN")
