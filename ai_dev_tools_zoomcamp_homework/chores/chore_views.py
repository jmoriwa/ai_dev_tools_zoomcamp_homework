from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.http import FileResponse

from . import services
from .accounts import require_admin
from .forms import ChoreForm, DuplicateForm, BulkChoreForm
from . import recurrence
from . import reminders
from . import completion
from .models import AuditEvent, CompletionAttempt


def get_chore(request, pk):
    return get_object_or_404(services.visible_chores(actor=request.user), pk=pk)


@login_required
def chore_list(request):
    chores = services.visible_chores(actor=request.user)
    if request.user.is_household_admin and request.GET.get("q"):
        chores = chores.filter(title__icontains=request.GET["q"])
    return render(request, "chores/chore_list.html", {"chores": chores.order_by("due_date", "pk")})


@login_required
def chore_detail(request, pk):
    chore = get_chore(request, pk)
    return render(request, "chores/chore_detail.html", {"chore": chore, "status_label": completion.status_label(chore), "latest": completion.latest_attempt(chore)})


@login_required
def chore_form(request, pk=None, duplicate=False):
    require_admin(request.user)
    chore = get_chore(request, pk) if pk else None
    title = "Duplicate chore" if duplicate else "Edit chore" if chore else "Create chore"
    form_type = DuplicateForm if duplicate else ChoreForm
    kwargs = {} if duplicate else {"instance": chore}
    form = form_type(request.POST or None, actor=request.user, **kwargs)
    if request.method == "POST" and form.is_valid():
        try:
            if duplicate:
                result = services.duplicate_chore(actor=request.user, chore=chore, **form.cleaned_data)
            elif chore:
                # ModelForm validation mutates its instance; reload original values.
                result = services.edit_chore(actor=request.user, chore=get_chore(request, pk), **form.cleaned_data)
            else:
                result = services.create_chore(actor=request.user, **form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error.messages)
        else:
            return redirect("chores:chore_detail", pk=result.pk)
    return render(request, "chores/account_form.html", {"form": form, "title": title, "button": "Save chore"})


@login_required
@require_POST
def chore_delete(request, pk):
    services.delete_chore(actor=request.user, chore=get_chore(request, pk))
    return redirect("chores:chore_list")


@login_required
@require_POST
def completion_action(request, pk, action):
    chore = get_chore(request, pk)
    try:
        if action == "submit":
            completion.submit(actor=request.user, chore=chore, note=request.POST.get("note", ""), photo=request.FILES.get("photo"))
        elif action in {"approve", "reject"}:
            completion.review(actor=request.user, chore=chore, approve=action == "approve", reason=request.POST.get("reason", ""))
        elif action == "undo":
            completion.undo(actor=request.user, chore=chore)
        elif action == "reactivate":
            completion.reactivate(actor=request.user, chore=chore, note=request.POST.get("note", ""))
        elif action == "catchup":
            recurrence.resolve_catchup(actor=request.user, chore=chore, choice=request.POST.get("choice"))
        elif action == "pause":
            reminders.pause(actor=request.user, chore=chore, reason=request.POST.get("reason", ""))
        elif action == "resume":
            reminders.resume(actor=request.user, chore=chore)
    except ValidationError as error:
        return render(request, "chores/chore_detail.html", {"chore": chore, "status_label": completion.status_label(chore), "latest": completion.latest_attempt(chore), "errors": error.messages}, status=400)
    return redirect("chores:chore_detail", pk=pk)


@login_required
def history(request):
    events = AuditEvent.objects.filter(household=request.user.household).select_related("actor", "subject", "chore", "attempt")
    if not request.user.is_household_admin:
        events = events.filter(subject=request.user, attempt__isnull=False)
    return render(request, "chores/history.html", {"events": events})


@login_required
def attempt_photo(request, pk):
    attempts = CompletionAttempt.objects.filter(chore__household=request.user.household).exclude(photo="")
    if not request.user.is_household_admin:
        attempts = attempts.filter(assignee=request.user)
    attempt = get_object_or_404(attempts, pk=pk)
    response = FileResponse(attempt.photo.open("rb"))
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
def bulk_create(request):
    require_admin(request.user)
    form = BulkChoreForm(request.POST or None, actor=request.user)
    if request.method == "POST" and form.is_valid():
        recurrence.bulk_create(actor=request.user, **form.cleaned_data)
        return redirect("chores:chore_list")
    return render(request, "chores/account_form.html", {"form": form, "title": "Assign recurring chore to several members", "button": "Create independent series"})


@login_required
def schedule(request):
    return render(request, "chores/schedule.html", {"schedule": recurrence.schedule_preview(actor=request.user)})
