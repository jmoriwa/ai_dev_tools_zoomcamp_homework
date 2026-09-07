from datetime import datetime, time, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .accounts import require_admin
from .completion import latest_attempt
from .models import Chore, Notification, User
from .services import record


def deliver(recipient, chore, kind, key, message):
    _, created = Notification.objects.get_or_create(delivery_key=key, defaults={"recipient": recipient, "chore": chore, "kind": kind, "message": message})
    return int(created)


@transaction.atomic
def send_reminders(now=None, chore_id=None):
    now = now or timezone.now()
    today = timezone.localdate(now)
    chores = Chore.objects.filter(deleted_at__isnull=True, reminders_paused_at__isnull=True).exclude(status="completed")
    if chore_id:
        chores = chores.filter(pk=chore_id)
    count = 0
    for chore in chores:
        attempt = latest_attempt(chore)
        if chore.due_date == today and (chore.status == "open" or (attempt and attempt.status == "rejected")):
            count += deliver(chore.assignee, chore, "due", f"due:{chore.pk}:{today}", f"Due today: {chore.title}")
        if chore.status != "pending" or not attempt or attempt.status != "rejected" or chore.due_date >= today:
            continue
        start = max(attempt.reviewed_at, timezone.make_aware(datetime.combine(chore.due_date + timedelta(days=1), time.min)))
        count += deliver(chore.assignee, chore, "rejected_overdue", f"rejected:{attempt.pk}:{chore.assignee_id}:{today}", f"Overdue: please open {chore.title} and resubmit.")
        if now >= start + timedelta(days=1):
            for admin in User.objects.filter(household=chore.household, role__in=["admin", "primary_admin"]):
                count += deliver(admin, chore, "rejected_overdue_admin", f"rejected-admin:{attempt.pk}:{admin.pk}:{today}", f"Still awaiting resubmission: {chore.title}.")
    return count


@transaction.atomic
def pause(*, actor, chore, reason=""):
    require_admin(actor, chore)
    chore = Chore.objects.select_for_update().get(pk=chore.pk, deleted_at__isnull=True)
    if chore.due_date < timezone.localdate() and not reason.strip():
        raise ValidationError("A reason is required to pause overdue reminders.")
    if not chore.reminders_paused_at:
        chore.reminders_paused_at = timezone.now()
        chore.reminders_paused_by = actor
        chore.reminder_pause_reason = reason
        chore.save(update_fields=["reminders_paused_at", "reminders_paused_by", "reminder_pause_reason"])
        record(actor, chore, "reminders_paused", reason)


@transaction.atomic
def resume(*, actor, chore):
    require_admin(actor, chore)
    chore = Chore.objects.select_for_update().get(pk=chore.pk, deleted_at__isnull=True)
    if chore.reminders_paused_at:
        chore.reminders_paused_at = None
        chore.reminders_paused_by = None
        chore.reminder_pause_reason = ""
        chore.save(update_fields=["reminders_paused_at", "reminders_paused_by", "reminder_pause_reason"])
        record(actor, chore, "reminders_resumed")
