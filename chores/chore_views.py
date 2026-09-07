from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import services
from .accounts import require_admin
from .forms import ChoreForm, DuplicateForm


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
    return render(request, "chores/chore_detail.html", {"chore": get_chore(request, pk)})


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
