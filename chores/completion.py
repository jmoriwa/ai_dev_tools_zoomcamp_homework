"""Completion state transitions shared by HTML and REST callers."""
from datetime import timedelta
from uuid import uuid4

from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .accounts import require_admin
from .models import Chore, CompletionAttempt, Notification, User
from .services import record, visible_chores


def owned_chore(actor, chore):
    if not visible_chores(actor=actor).filter(pk=chore.pk).exists():
        raise PermissionDenied
    return Chore.objects.select_for_update().get(pk=chore.pk)


def latest_attempt(chore):
    return chore.attempts.filter(undone_at__isnull=True).order_by("-submitted_at", "-pk").first()


def status_label(chore):
    attempt = latest_attempt(chore)
    today = timezone.localdate()
    if chore.status == Chore.Status.PENDING and attempt:
        if attempt.status == CompletionAttempt.Status.REJECTED:
            return "Rejected — overdue" if chore.due_date < today else "Rejected — resubmit"
        return "Submitted on time" if timezone.localdate(attempt.submitted_at) <= attempt.due_date_at_submission else "Pending approval"
    if chore.status == Chore.Status.OPEN and chore.due_date < today:
        return "Overdue"
    return chore.get_status_display()


def notify_admins(chore, message):
    for admin in User.objects.filter(household=chore.household, role__in=[User.Role.ADMIN, User.Role.PRIMARY_ADMIN]):
        Notification.objects.create(recipient=admin, chore=chore, kind="completion", message=message)


@transaction.atomic
def submit(*, actor, chore, note="", photo=None):
    chore = owned_chore(actor, chore)
    previous = latest_attempt(chore)
    if chore.status == Chore.Status.COMPLETED or (chore.status == Chore.Status.PENDING and previous and previous.status != CompletionAttempt.Status.REJECTED):
        raise ValidationError("This chore has already been submitted.")
    if len(note) > 2000:
        raise ValidationError("Completion notes must be 2000 characters or fewer.")
    if chore.requires_photo and not photo:
        raise ValidationError("A new completion photo is required.")
    if photo:
        if photo.size > 5 * 1024 * 1024:
            raise ValidationError("Photos must be 5 MB or smaller.")
        photo = forms.ImageField().clean(photo)
        if photo.image.format not in {"JPEG", "PNG", "WEBP"}:
            raise ValidationError("Use a JPEG, PNG, or WebP photo.")
        photo.name = f"{uuid4().hex}.{photo.image.format.lower()}"
    attempt = CompletionAttempt.objects.create(chore=chore, assignee=chore.assignee, submitted_by=actor, due_date_at_submission=chore.due_date, note=note, photo=photo or "", status="pending" if chore.requires_approval else "completed")
    chore.status = Chore.Status.PENDING if chore.requires_approval else Chore.Status.COMPLETED
    chore.completed_at = None if chore.requires_approval else timezone.now()
    chore.save(update_fields=["status", "completed_at", "updated_at"])
    action = "resubmitted" if previous and previous.status == "rejected" else "admin_completion" if actor.pk != chore.assignee_id else "completion_submitted" if chore.requires_approval else "completed"
    record(actor, chore, action, note, attempt)
    notify_admins(chore, f"{actor.username} submitted {chore.title} for {chore.assignee.username}.")
    return attempt


@transaction.atomic
def review(*, actor, chore, approve, reason=""):
    require_admin(actor, chore)
    chore = owned_chore(actor, chore)
    attempt = latest_attempt(chore)
    if chore.status != Chore.Status.PENDING or not attempt or attempt.status != "pending":
        raise ValidationError("There is no submission awaiting review.")
    if not approve and not reason.strip():
        raise ValidationError("A rejection reason is required.")
    attempt.status = "approved" if approve else "rejected"
    attempt.reviewed_by = actor
    attempt.reviewed_at = timezone.now()
    attempt.rejection_reason = "" if approve else reason
    attempt.save()
    chore.status = Chore.Status.COMPLETED if approve else Chore.Status.PENDING
    chore.completed_at = timezone.now() if approve else None
    chore.save(update_fields=["status", "completed_at", "updated_at"])
    record(actor, chore, "approved" if approve else "rejected", reason if not approve else "", attempt)
    Notification.objects.create(recipient=chore.assignee, chore=chore, kind="review", message=f"{chore.title}: {'approved' if approve else 'please open the chore and resubmit'}.")
    return attempt


@transaction.atomic
def undo(*, actor, chore):
    chore = owned_chore(actor, chore)
    attempt = latest_attempt(chore)
    if actor.pk != chore.assignee_id:
        raise PermissionDenied
    if not attempt or attempt.submitted_by_id != actor.pk or attempt.status not in {"completed", "pending"} or timezone.now() >= attempt.submitted_at + timedelta(minutes=15):
        raise ValidationError("The 15-minute undo window has ended or the submission was reviewed.")
    attempt.undone_at = timezone.now()
    attempt.save(update_fields=["undone_at"])
    chore.status = Chore.Status.OPEN
    chore.completed_at = None
    chore.save(update_fields=["status", "completed_at", "updated_at"])
    record(actor, chore, "completion_undone", attempt=attempt)


@transaction.atomic
def reactivate(*, actor, chore, note):
    require_admin(actor, chore)
    chore = owned_chore(actor, chore)
    if not note.strip() or chore.status != Chore.Status.COMPLETED:
        raise ValidationError("A completed chore and reactivation note are required.")
    chore.status = Chore.Status.OPEN
    chore.completed_at = None
    chore.save(update_fields=["status", "completed_at", "updated_at"])
    record(actor, chore, "reactivated", note)
