from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from . import accounts
from .forms import ChangePINForm, LoginForm, MemberForm
from .models import User
from django.utils import timezone


def home(request):
    if request.user.is_authenticated and not request.user.is_staff:
        return redirect("chores:dashboard")
    return render(request, "chores/home.html")


@login_required
def dashboard(request):
    from .dashboard import dashboard_data
    template = "chores/dashboard_content.html" if request.headers.get("HX-Request") else "chores/dashboard.html"
    return render(request, template, dashboard_data(request.user, request.GET))


@sensitive_post_parameters("pin")
@never_cache
def login_view(request):
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = authenticate(request, **form.cleaned_data)
        if user is not None:
            login(request, user)
            request.session["pin_session_version"] = user.session_version
            return redirect("chores:home")
        form.add_error(None, "Unable to log in. Check your username and PIN, or ask an admin to unlock your account.")
    return render(request, "chores/account_form.html", {"form": form, "title": "Log in", "button": "Log in"})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("chores:login")


@login_required
@sensitive_post_parameters("current_pin", "new_pin")
@never_cache
def change_pin_view(request):
    form = ChangePINForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            accounts.change_pin(actor=request.user, **form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error.messages)
        else:
            logout(request)
            messages.success(request, "PIN changed. Please log in again.")
            return redirect("chores:login")
    return render(request, "chores/account_form.html", {"form": form, "title": "Change your PIN", "button": "Change PIN"})


@login_required
@sensitive_post_parameters("pin")
@never_cache
def members(request):
    accounts.require_admin(request.user)
    form = MemberForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            accounts.create_member(actor=request.user, **form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error.messages)
        else:
            messages.success(request, "Member created. They can now log in with their username and PIN.")
            return redirect("chores:members")
    return render(request, "chores/members.html", {"form": form, "members": User.objects.filter(household=request.user.household).order_by("username")})


@login_required
@require_POST
@never_cache
def member_action(request, pk, action):
    accounts.require_admin(request.user)
    subject = get_object_or_404(User, pk=pk, household=request.user.household)
    if action == "role":
        try:
            accounts.set_role(actor=request.user, subject=subject, role=request.POST.get("role"))
        except ValidationError as error:
            return render(request, "chores/account_result.html", {"title": "Invalid role", "detail": " ".join(error.messages)}, status=400)
    elif action == "reset":
        pin = accounts.reset_pin(actor=request.user, subject=subject)
        return render(request, "chores/account_result.html", {"title": "PIN reset", "detail": f"New PIN for {subject.username}: {pin}. Share it with the member; it is only displayed here. Resetting does not unlock the account."})
    elif action == "unlock":
        accounts.unlock_member(actor=request.user, subject=subject)
    return redirect("chores:members")


@login_required
def notifications(request):
    return render(request, "chores/notifications.html", {"notifications": request.user.notifications.select_related("chore")})


@login_required
def notification_open(request, pk):
    notification = get_object_or_404(request.user.notifications.select_related("chore"), pk=pk)
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at"])
    return render(request, "chores/notification.html", {"notification": notification})
