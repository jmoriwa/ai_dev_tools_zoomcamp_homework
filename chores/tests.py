from datetime import date
from tempfile import TemporaryDirectory

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Household, User, Chore, RecurringSeries, CompletionAttempt, AuditEvent, Notification
from .services import delete_chore, visible_chores


class FoundationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.household = Household.objects.get(pk=1)
        cls.admin = User.objects.create_user(username="Admin", password="123456", role=User.Role.PRIMARY_ADMIN)
        cls.member = User.objects.create_user(username="Alex", password="234567")
        cls.other = User.objects.create_user(username="alex", password="345678")
        cls.chore = Chore.objects.create(title="Wash dishes", assignee=cls.member, due_date=date(2026, 9, 7))

    def test_single_household(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Household.objects.create(id=2, name="Second")

    def test_only_one_primary_admin(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(username="Second", role=User.Role.PRIMARY_ADMIN)

    def test_user_identity_and_hashing(self):
        self.assertNotEqual(self.member.pk, self.other.pk)
        self.assertTrue(self.member.check_password("234567"))
        self.assertNotEqual(self.member.password, "234567")
        self.assertEqual(User.objects.get(username="Alex"), self.member)
        self.assertEqual(User.objects.get(username="alex"), self.other)

    def test_visibility(self):
        self.assertEqual(list(visible_chores(actor=self.member)), [self.chore])
        self.assertEqual(list(visible_chores(actor=self.admin)), [self.chore])
        self.assertFalse(visible_chores(actor=self.other).exists())
        self.assertFalse(visible_chores(actor=AnonymousUser()).exists())

    def test_member_cannot_delete(self):
        with self.assertRaises(PermissionDenied):
            delete_chore(actor=self.member, chore=self.chore)

    def test_deletion_preserves_history_and_photo(self):
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            attempt = CompletionAttempt.objects.create(chore=self.chore, assignee=self.member, submitted_by=self.member, due_date_at_submission=self.chore.due_date, note="Done", photo=SimpleUploadedFile("proof.jpg", b"photo fixture"))
            Notification.objects.create(recipient=self.member, chore=self.chore, kind="completion", message="Submitted")
            delete_chore(actor=self.admin, chore=self.chore)
            delete_chore(actor=self.admin, chore=self.chore)
            self.chore.refresh_from_db()
            self.assertIsNotNone(self.chore.deleted_at)
            self.assertFalse(visible_chores(actor=self.admin).exists())
            attempt.refresh_from_db()
            self.assertEqual(attempt.note, "Done")
            with attempt.photo.open("rb") as photo:
                self.assertEqual(photo.read(), b"photo fixture")
            self.assertEqual(AuditEvent.objects.filter(action="chore_deleted").count(), 1)
            self.assertEqual(Notification.objects.count(), 1)
            with self.assertRaises(ProtectedError):
                self.chore.delete()

    def test_recurring_occurrences_are_unique(self):
        series = RecurringSeries.objects.create(title="Laundry", assignee=self.member, frequency="weekly", start_date=self.chore.due_date)
        Chore.objects.create(title="Laundry", assignee=self.member, due_date=self.chore.due_date, series=series, scheduled_date=self.chore.due_date)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Chore.objects.create(title="Laundry again", assignee=self.member, due_date=date(2026, 9, 9), series=series, scheduled_date=self.chore.due_date)

    def test_reminder_delivery_keys_are_unique(self):
        Notification.objects.create(recipient=self.member, kind="due", message="Due", delivery_key="due:1:2026-09-07")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Notification.objects.create(recipient=self.member, kind="due", message="Due", delivery_key="due:1:2026-09-07")

    def test_home_and_internal_admin(self):
        response = self.client.get(reverse("chores:home"))
        self.assertContains(response, "A home we care for together.")
        self.assertContains(response, 'name="viewport"')
        self.assertContains(response, "chores/vendor/htmx.min.js")
        self.assertNotContains(response, "Internal management")
        self.admin.is_staff = True
        self.admin.is_superuser = True
        self.admin.save()
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("chores:home")), "Internal management")
        for model in ("user", "household", "chore", "recurringseries", "completionattempt", "auditevent", "notification"):
            self.assertEqual(self.client.get(reverse(f"admin:chores_{model}_changelist")).status_code, 200)
