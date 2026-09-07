"""Shared account operations for household pages and future API callers."""
import re
import secrets

from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import AuditEvent, User


def validate_pin(pin):
    if not isinstance(pin, str) or not re.fullmatch(r"[1-9][0-9]{5}", pin):
        raise ValidationError("Enter exactly six digits with no leading zero.")


def require_admin(actor, subject=None):
    if not actor.is_authenticated or not actor.is_active or actor.locked_at or not actor.is_household_admin:
        raise PermissionDenied
    if subject is not None and actor.household_id != subject.household_id:
        raise PermissionDenied


def audit(actor, subject, action):
    AuditEvent.objects.create(household_id=subject.household_id, actor=actor, subject=subject, action=action)


@transaction.atomic
def create_member(*, actor, username, pin):
    require_admin(actor)
    validate_pin(pin)
    member = User(username=username, household_id=actor.household_id)
    member.set_password(pin)
    member.full_clean()
    member.save()
    return member


@transaction.atomic
def set_role(*, actor, subject, role):
    require_admin(actor, subject)
    subject = User.objects.select_for_update().get(pk=subject.pk)
    if actor.role != User.Role.PRIMARY_ADMIN or subject.role == User.Role.PRIMARY_ADMIN:
        raise PermissionDenied
    if role not in (User.Role.ADMIN, User.Role.MEMBER):
        raise ValidationError("Choose member or secondary admin.")
    subject.role = role
    subject.save(update_fields=["role"])


def replace_pin(actor, subject, pin, action):
    validate_pin(pin)
    if subject.check_password(pin) or (subject.previous_pin_hash and check_password(pin, subject.previous_pin_hash)):
        raise ValidationError("Choose a PIN different from your current and previous PIN.")
    subject.previous_pin_hash = subject.password
    subject.set_password(pin)
    subject.pin_changed_at = timezone.now()
    subject.session_version += 1
    subject.save(update_fields=["password", "previous_pin_hash", "pin_changed_at", "session_version"])
    audit(actor, subject, action)


@transaction.atomic
def change_pin(*, actor, current_pin, new_pin):
    if not actor.is_authenticated or not actor.is_active or actor.locked_at:
        raise PermissionDenied
    subject = User.objects.select_for_update().get(pk=actor.pk)
    if not subject.check_password(current_pin):
        raise ValidationError("Your current PIN is incorrect.")
    replace_pin(actor, subject, new_pin, "pin_changed")


@transaction.atomic
def reset_pin(*, actor, subject):
    require_admin(actor, subject)
    subject = User.objects.select_for_update().get(pk=subject.pk)
    if subject.role != User.Role.MEMBER:
        raise PermissionDenied
    while True:
        pin = str(secrets.randbelow(900000) + 100000)
        if not subject.check_password(pin) and not (subject.previous_pin_hash and check_password(pin, subject.previous_pin_hash)):
            break
    replace_pin(actor, subject, pin, "pin_reset")
    return pin


@transaction.atomic
def unlock_member(*, actor, subject):
    require_admin(actor, subject)
    subject = User.objects.select_for_update().get(pk=subject.pk)
    if subject.pk == actor.pk:
        raise PermissionDenied
    if subject.locked_at is not None:
        subject.locked_at = None
        subject.failed_login_attempts = 0
        subject.save(update_fields=["locked_at", "failed_login_attempts"])
        audit(actor, subject, "account_unlocked")


class PINBackend:
    @transaction.atomic
    def authenticate(self, request, username=None, pin=None, **kwargs):
        if username is None or pin is None:
            return None
        user = User.objects.select_for_update().filter(username=username).first()
        if user is None or user.username != username:
            make_password(pin)
            return None
        if not user.is_active or user.locked_at:
            return None
        valid_format = re.fullmatch(r"[1-9][0-9]{5}", pin) is not None
        if user.check_password(pin) and valid_format:
            user.failed_login_attempts = 0
            user.save(update_fields=["failed_login_attempts"])
            return user
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= 10:
            user.locked_at = timezone.now()
            user.session_version += 1
            audit(None, user, "account_locked")
        user.save(update_fields=["failed_login_attempts", "locked_at", "session_version"])
        return None

    def get_user(self, user_id):
        return User.objects.filter(pk=user_id, is_active=True, locked_at__isnull=True).first()
