from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import authenticate
from django.contrib.sessions.models import Session
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command, CommandError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import accounts
from .models import AuditEvent, User


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AccountTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(username="Admin", password="123456", role="primary_admin")
        cls.secondary = User.objects.create_user(username="Secondary", password="234567", role="admin")
        cls.member = User.objects.create_user(username="Alex", password="345678")
        cls.other = User.objects.create_user(username="alex", password="456789")

    def login(self, client=None, username="Alex", pin="345678"):
        return (client or self.client).post(reverse("chores:login"), {"username": username, "pin": pin})

    def test_pin_validation(self):
        for pin in ("012345", "12345", "1234567", "abcdef", "１２３４５６", "12345\n", " 123456", 123456):
            with self.subTest(pin=pin), self.assertRaises(ValidationError):
                accounts.create_member(actor=self.admin, username="New", pin=pin)
        member = accounts.create_member(actor=self.admin, username="New", pin="123456")
        self.assertTrue(member.check_password("123456"))
        self.assertNotEqual(member.password, "123456")

    def test_create_and_login_through_pages(self):
        for admin in (self.admin, self.secondary):
            self.login(username=admin.username, pin="123456" if admin == self.admin else "234567")
            self.assertContains(self.client.get(reverse("chores:members")), "Create a member")
            name = f"New{admin.pk}"
            self.assertRedirects(self.client.post(reverse("chores:members"), {"username": name, "pin": "567891", "role": "primary_admin"}), reverse("chores:members"))
            self.assertEqual(User.objects.get(username=name).role, "member")
            self.client.post(reverse("chores:logout"))
            self.assertEqual(self.login(username=name, pin="567891").status_code, 302)
            self.client.post(reverse("chores:logout"))

    def test_duplicate_username_is_form_error(self):
        self.login(username="Admin", pin="123456")
        response = self.client.post(reverse("chores:members"), {"username": "Alex", "pin": "567891"})
        self.assertContains(response, "already exists")

    def test_case_sensitive_login(self):
        self.assertEqual(authenticate(username="Alex", pin="345678"), self.member)
        self.assertEqual(authenticate(username="alex", pin="456789"), self.other)
        self.assertIsNone(authenticate(username="ALEX", pin="345678"))
        self.assertIsNone(authenticate(username="alex", pin="345678"))

    def test_pin_history_and_current_pin(self):
        with self.assertRaises(ValidationError):
            accounts.change_pin(actor=self.member, current_pin="999999", new_pin="567891")
        accounts.change_pin(actor=self.member, current_pin="345678", new_pin="567891")
        for pin in ("345678", "567891"):
            with self.assertRaises(ValidationError):
                accounts.change_pin(actor=self.member, current_pin="567891", new_pin=pin)
        accounts.change_pin(actor=self.member, current_pin="567891", new_pin="678912")
        accounts.change_pin(actor=self.member, current_pin="678912", new_pin="345678")
        self.assertEqual(AuditEvent.objects.filter(action="pin_changed").count(), 3)
        self.assertFalse(AuditEvent.objects.exclude(note="").exists())

    def test_role_restrictions(self):
        for actor in (self.member, self.secondary):
            with self.assertRaises(PermissionDenied):
                accounts.set_role(actor=actor, subject=self.other, role="admin")
        accounts.set_role(actor=self.admin, subject=self.member, role="admin")
        self.member.refresh_from_db()
        self.assertEqual(self.member.role, "admin")
        accounts.set_role(actor=self.admin, subject=self.member, role="member")
        self.member.refresh_from_db()
        self.assertEqual(self.member.role, "member")
        with self.assertRaises(PermissionDenied):
            accounts.set_role(actor=self.admin, subject=self.admin, role="member")
        with self.assertRaises(ValidationError):
            accounts.set_role(actor=self.admin, subject=self.member, role="primary_admin")

    def test_direct_requests_and_post_only_actions(self):
        self.assertEqual(self.client.get(reverse("chores:members")).status_code, 302)
        self.login()
        self.assertEqual(self.client.get(reverse("chores:members")).status_code, 403)
        self.assertEqual(self.client.post(reverse("chores:members"), {"username": "Bad", "pin": "123456"}).status_code, 403)
        for action in ("role", "reset", "unlock"):
            url = reverse(f"chores:member_{action}", args=[self.other.pk])
            self.assertEqual(self.client.post(url, {"role": "admin"}).status_code, 403)
            self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.get(reverse("chores:logout")).status_code, 405)
        self.client.post(reverse("chores:change_pin"), {"current_pin": "345678", "new_pin": "567891", "user_id": self.other.pk})
        self.other.refresh_from_db()
        self.assertTrue(self.other.check_password("456789"))

    def test_secondary_cannot_promote_by_direct_request(self):
        self.login(username="Secondary", pin="234567")
        self.assertEqual(self.client.post(reverse("chores:member_role", args=[self.member.pk]), {"role": "admin"}).status_code, 403)

    def test_lockout_unlock_and_audit(self):
        for _ in range(9):
            self.assertIsNone(authenticate(username="Alex", pin="999999"))
        self.member.refresh_from_db()
        self.assertIsNone(self.member.locked_at)
        self.assertEqual(AuditEvent.objects.count(), 0)
        self.assertIsNone(authenticate(username="Alex", pin="999999"))
        self.assertIsNone(authenticate(username="Alex", pin="345678"))
        self.assertIsNone(authenticate(username="Alex", pin="999999"))
        self.assertEqual(AuditEvent.objects.filter(action="account_locked").count(), 1)
        with self.assertRaises(PermissionDenied):
            accounts.unlock_member(actor=self.other, subject=self.member)
        accounts.unlock_member(actor=self.secondary, subject=self.member)
        accounts.unlock_member(actor=self.secondary, subject=self.member)
        self.assertEqual(AuditEvent.objects.filter(action="account_unlocked").count(), 1)
        self.assertEqual(authenticate(username="Alex", pin="345678"), self.member)
        self.member.refresh_from_db()
        self.assertEqual(self.member.failed_login_attempts, 0)

    def test_success_clears_failures_without_audit(self):
        authenticate(username="Alex", pin="999999")
        self.login()
        self.client.post(reverse("chores:logout"))
        self.member.refresh_from_db()
        self.assertEqual(self.member.failed_login_attempts, 0)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_change_invalidates_all_sessions(self):
        second = Client()
        self.login()
        self.login(second)
        response = self.client.post(reverse("chores:change_pin"), {"current_pin": "345678", "new_pin": "567891"})
        self.assertRedirects(response, reverse("chores:login"))
        for client in (self.client, second):
            self.assertEqual(client.get(reverse("chores:change_pin")).status_code, 302)
            self.assertNotIn("_auth_user_id", client.session)
        self.assertEqual(self.login(pin="567891").status_code, 302)

    def test_reset_history_sessions_and_no_expiry(self):
        self.login()
        second = Client()
        self.login(second)
        with patch("chores.accounts.secrets.randbelow", side_effect=[245678, 467891]):
            pin = accounts.reset_pin(actor=self.secondary, subject=self.member)
        self.assertEqual(pin, "567891")
        for client in (self.client, second):
            self.assertEqual(client.get(reverse("chores:change_pin")).status_code, 302)
        with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(days=365)):
            self.assertEqual(authenticate(username="Alex", pin=pin), self.member)
        with self.assertRaises(ValidationError):
            accounts.change_pin(actor=self.member, current_pin=pin, new_pin="345678")
        self.assertEqual(AuditEvent.objects.get().action, "pin_reset")
        self.assertEqual(AuditEvent.objects.get().note, "")

    def test_reset_page_does_not_cache_pin(self):
        self.login(username="Admin", pin="123456")
        response = self.client.post(reverse("chores:member_reset", args=[self.member.pk]))
        self.assertContains(response, "New PIN for Alex:")
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertNotContains(self.client.get(reverse("chores:members")), "New PIN for Alex:")

    def test_reset_does_not_unlock(self):
        self.member.locked_at = timezone.now()
        self.member.save()
        pin = accounts.reset_pin(actor=self.admin, subject=self.member)
        self.assertIsNone(authenticate(username="Alex", pin=pin))

    def test_lock_invalidates_existing_session_even_after_unlock(self):
        self.login()
        for _ in range(10):
            authenticate(username="Alex", pin="999999")
        accounts.unlock_member(actor=self.admin, subject=self.member)
        self.assertEqual(self.client.get(reverse("chores:change_pin")).status_code, 302)

    def test_sliding_expiry(self):
        start = timezone.now()
        with patch("django.utils.timezone.now", return_value=start):
            self.login()
        key = self.client.session.session_key
        self.assertEqual(Session.objects.get(session_key=key).expire_date, start + timedelta(hours=24))
        with patch("django.utils.timezone.now", return_value=start + timedelta(hours=23)):
            self.assertEqual(self.client.get(reverse("chores:change_pin")).status_code, 200)
        self.assertEqual(Session.objects.get(session_key=key).expire_date, start + timedelta(hours=47))
        with patch("django.utils.timezone.now", return_value=start + timedelta(hours=47, seconds=1)):
            self.assertEqual(self.client.get(reverse("chores:change_pin")).status_code, 302)

    def test_csrf(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(self.login(client).status_code, 403)
        client.force_login(self.admin, backend="django.contrib.auth.backends.ModelBackend")
        self.assertEqual(client.post(reverse("chores:member_reset", args=[self.member.pk])).status_code, 403)

    def test_bootstrap_primary_admin(self):
        User.objects.filter(pk=self.admin.pk).update(role="admin")
        output = StringIO()
        with patch("chores.management.commands.createhouseholdadmin.getpass", return_value="678912"):
            call_command("createhouseholdadmin", "First", stdout=output)
        user = User.objects.get(username="First")
        self.assertEqual(user.role, "primary_admin")
        self.assertFalse(user.is_staff)
        self.assertTrue(user.check_password("678912"))
        self.assertNotIn("678912", output.getvalue())
        with self.assertRaises(CommandError):
            call_command("createhouseholdadmin", "Another", stdout=output)

    def test_bootstrap_rejects_invalid_pin_and_mismatch(self):
        User.objects.filter(pk=self.admin.pk).update(role="admin")
        for prompts in (["012345"], ["678912", "789123"]):
            with patch("chores.management.commands.createhouseholdadmin.getpass", side_effect=prompts), self.assertRaises(CommandError):
                call_command("createhouseholdadmin", "First", stdout=StringIO())
        self.assertFalse(User.objects.filter(username="First").exists())

    def test_admin_reset_cannot_target_admins(self):
        for subject in (self.admin, self.secondary):
            with self.assertRaises(PermissionDenied):
                accounts.reset_pin(actor=self.admin, subject=subject)

    def test_member_cannot_call_account_services_directly(self):
        with self.assertRaises(PermissionDenied):
            accounts.create_member(actor=self.member, username="Unauthorized", pin="678912")
        with self.assertRaises(PermissionDenied):
            accounts.reset_pin(actor=self.member, subject=self.other)
