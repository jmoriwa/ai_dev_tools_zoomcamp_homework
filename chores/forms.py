from django import forms

from .accounts import validate_pin
from .models import User, Chore, RecurringSeries


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


class ChoreForm(forms.ModelForm):
    frequency = forms.ChoiceField(required=False, choices=[("", "One time"), *RecurringSeries.Frequency.choices])
    note = forms.CharField(label="Edit note", required=False, widget=forms.Textarea(attrs={"rows": 2}))

    class Meta:
        model = Chore
        fields = ["title", "description", "category", "priority", "assignee", "due_date", "requires_photo", "requires_approval"]
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"}), "description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, actor, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assignee"].queryset = User.objects.filter(household=actor.household, is_active=True)
        if self.instance.pk:
            self.fields.pop("frequency")


class DuplicateForm(forms.Form):
    assignee = forms.ModelChoiceField(queryset=User.objects.none())
    due_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, actor, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assignee"].queryset = User.objects.filter(household=actor.household, is_active=True)
