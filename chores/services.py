"""Shared business operations for template views and the future API.

Add workflow rules here as their backlog tasks are implemented. Internal Django
admin is a development tool and can bypass application workflow rules.
"""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import AuditEvent, Chore, Notification, RecurringSeries
from .accounts import require_admin

DETAIL_FIELDS = ("title", "description", "category", "priority", "requires_photo", "requires_approval")


def record(actor, chore, action, note="", attempt=None):
    return AuditEvent.objects.create(household=chore.household, actor=actor, subject=chore.assignee, chore=chore, action=action, note=note, attempt=attempt)


@transaction.atomic
def create_chore(*, actor, assignee, due_date, frequency="", **details):
    require_admin(actor, assignee)
    chore = Chore(household=actor.household, assignee=assignee, due_date=due_date, **{k: v for k, v in details.items() if k in DETAIL_FIELDS})
    if frequency:
        series = RecurringSeries(household=actor.household, assignee=assignee, start_date=due_date, frequency=frequency, **{k: getattr(chore, k) for k in DETAIL_FIELDS})
        series.full_clean()
        series.save()
        chore.series = series
        chore.scheduled_date = due_date
    chore.full_clean()
    chore.save()
    record(actor, chore, "chore_created")
    Notification.objects.create(recipient=assignee, chore=chore, kind="assignment", message=f"Assigned: {chore.title}")
    return chore


@transaction.atomic
def edit_chore(*, actor, chore, note="", **changes):
    require_admin(actor, chore)
    chore = Chore.objects.select_for_update().get(pk=chore.pk, deleted_at__isnull=True)
    old_assignee = chore.assignee
    if "assignee" in changes:
        require_admin(actor, changes["assignee"])
    major = any(key in changes and changes[key] != getattr(chore, key) for key in ("assignee", "due_date", "priority"))
    if major and not note.strip():
        raise ValidationError("An edit note is required for due date, priority, or assignment changes.")
    for key in (*DETAIL_FIELDS, "assignee", "due_date"):
        if key in changes:
            setattr(chore, key, changes[key])
    chore.full_clean()
    chore.save()
    record(actor, chore, "chore_edited", note)
    if major:
        for recipient in {old_assignee, chore.assignee}:
            Notification.objects.create(recipient=recipient, chore=chore, kind="major_edit", message=f"Updated {chore.title}: {note}")
    return chore


def duplicate_chore(*, actor, chore, assignee, due_date):
    require_admin(actor, chore)
    return create_chore(actor=actor, assignee=assignee, due_date=due_date, frequency=chore.series.frequency if chore.series else "", **{k: getattr(chore, k) for k in DETAIL_FIELDS})


def visible_chores(*, actor):
    if not actor.is_authenticated:
        return Chore.objects.none()
    chores = Chore.objects.filter(household=actor.household, deleted_at__isnull=True)
    return chores if actor.is_household_admin else chores.filter(assignee=actor)


@transaction.atomic
def delete_chore(*, actor, chore):
    if not actor.is_authenticated or not actor.is_household_admin or actor.household_id != chore.household_id:
        raise PermissionDenied
    chore = Chore.objects.select_for_update().get(pk=chore.pk)
    if chore.deleted_at is None:
        chore.deleted_at = timezone.now()
        chore.save(update_fields=["deleted_at", "updated_at"])
        AuditEvent.objects.create(household=chore.household, actor=actor, subject=chore.assignee, chore=chore, action="chore_deleted")
    return chore

