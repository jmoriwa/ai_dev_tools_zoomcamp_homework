"""Shared business operations for template views and the future API.

Add workflow rules here as their backlog tasks are implemented. Internal Django
admin is a development tool and can bypass application workflow rules.
"""
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from .models import AuditEvent, Chore


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

