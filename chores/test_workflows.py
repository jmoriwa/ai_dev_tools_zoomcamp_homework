from datetime import date, timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import AuditEvent, Chore, Notification, User
from . import services


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AssignmentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(username="Admin", password="123456", role="primary_admin")
        cls.member = User.objects.create_user(username="Alex", password="234567")
        cls.other = User.objects.create_user(username="Sam", password="345678")
        cls.chore = services.create_chore(actor=cls.admin, assignee=cls.member, due_date=date.today(), title="Wash dishes")

    def test_major_edits_require_note_and_notify_both_assignees(self):
        for changes in ({"assignee": self.other}, {"priority": "high"}, {"due_date": date.today() + timedelta(days=1)}):
            with self.assertRaises(ValidationError):
                services.edit_chore(actor=self.admin, chore=self.chore, **changes)
        services.edit_chore(actor=self.admin, chore=self.chore, assignee=self.other, note="Swap this week")
        self.assertEqual(set(Notification.objects.filter(kind="major_edit").values_list("recipient_id", flat=True)), {self.member.pk, self.other.pk})
        self.assertEqual(AuditEvent.objects.get(action="chore_edited").note, "Swap this week")

    def test_duplicate_recurring_is_independent(self):
        original = services.create_chore(actor=self.admin, assignee=self.member, due_date=date.today(), title="Laundry", frequency="weekly", requires_photo=True)
        copy = services.duplicate_chore(actor=self.admin, chore=original, assignee=self.other, due_date=date.today() + timedelta(days=2))
        self.assertNotEqual(copy.series_id, original.series_id)
        self.assertEqual(copy.series.frequency, "weekly")
        self.assertEqual(copy.assignee, self.other)
        self.assertTrue(copy.requires_photo)

    def test_member_ownership_and_forbidden_mutations(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("chores:chore_detail", args=[self.chore.pk])).status_code, 404)
        self.client.force_login(self.member)
        self.assertContains(self.client.get(reverse("chores:chore_detail", args=[self.chore.pk])), "Wash dishes")
        for name in ("chore_edit", "chore_duplicate", "chore_delete"):
            self.assertEqual(self.client.post(reverse(f"chores:{name}", args=[self.chore.pk])).status_code, 403)
        with self.assertRaises(PermissionDenied):
            services.create_chore(actor=self.member, assignee=self.member, due_date=date.today(), title="Forbidden")

    def test_create_edit_search_delete_pages(self):
        self.client.force_login(self.admin)
        payload = {"title": "Vacuum", "description": "Hall", "category": "other", "priority": "low", "assignee": self.member.pk, "due_date": date.today().isoformat()}
        self.assertEqual(self.client.post(reverse("chores:chore_create"), payload).status_code, 302)
        chore = Chore.objects.get(title="Vacuum")
        payload["priority"] = "high"
        self.assertContains(self.client.post(reverse("chores:chore_edit", args=[chore.pk]), payload), "edit note is required")
        chore.refresh_from_db()
        self.assertEqual(chore.priority, "low")
        payload["note"] = "Guests arriving"
        self.assertEqual(self.client.post(reverse("chores:chore_edit", args=[chore.pk]), payload).status_code, 302)
        result = self.client.get(reverse("chores:chore_list"), {"q": "Vacuum"})
        self.assertContains(result, "Vacuum")
        self.assertNotContains(result, "Wash dishes")
        self.client.post(reverse("chores:chore_delete", args=[chore.pk]))
        self.assertEqual(self.client.get(reverse("chores:chore_detail", args=[chore.pk])).status_code, 404)
        self.assertTrue(AuditEvent.objects.filter(chore=chore, action="chore_deleted").exists())
