from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import completion, recurrence, services
from .models import User


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class RecurrenceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="Admin", role="primary_admin")
        self.member = User.objects.create_user(username="Alex")
        self.other = User.objects.create_user(username="Sam")

    def make(self, frequency="daily", days=0, **details):
        return services.create_chore(actor=self.admin, assignee=self.member, due_date=timezone.localdate() - timedelta(days=days), title="Laundry", frequency=frequency, **details)

    def test_daily_weekly_and_undo_recompletion(self):
        for frequency, days in (("daily", 1), ("weekly", 7)):
            chore = self.make(frequency)
            completion.submit(actor=self.member, chore=chore)
            self.assertEqual(chore.series.occurrences.count(), 2)
            self.assertTrue(chore.series.occurrences.filter(scheduled_date=chore.scheduled_date + timedelta(days=days)).exists())
            completion.undo(actor=self.member, chore=chore)
            completion.submit(actor=self.member, chore=chore)
            self.assertEqual(chore.series.occurrences.count(), 2)

    def test_schedule_ignores_edited_due_date(self):
        chore = self.make("weekly", days=2)
        services.edit_chore(actor=self.admin, chore=chore, due_date=timezone.localdate(), note="Extend")
        completion.submit(actor=self.member, chore=chore)
        self.assertTrue(chore.series.occurrences.filter(scheduled_date=chore.scheduled_date + timedelta(days=7)).exists())

    def test_catchup_choices_and_permissions(self):
        for choice, count in (("all", 4), ("skip", 2)):
            chore = self.make(days=3)
            completion.submit(actor=self.member, chore=chore)
            chore.refresh_from_db()
            self.assertTrue(chore.catchup_pending)
            self.assertEqual(chore.status, "completed")
            with self.assertRaises(PermissionDenied):
                recurrence.resolve_catchup(actor=self.member, chore=chore, choice=choice)
            recurrence.resolve_catchup(actor=self.admin, chore=chore, choice=choice)
            self.assertEqual(chore.series.occurrences.count(), count)
            with self.assertRaises(ValidationError):
                recurrence.resolve_catchup(actor=self.admin, chore=chore, choice=choice)

    def test_approval_is_recurrence_trigger(self):
        chore = self.make(requires_approval=True)
        completion.submit(actor=self.member, chore=chore)
        self.assertEqual(chore.series.occurrences.count(), 1)
        completion.review(actor=self.admin, chore=chore, approve=True)
        self.assertEqual(chore.series.occurrences.count(), 2)

    def test_bulk_independent_series_and_preview(self):
        chores = recurrence.bulk_create(actor=self.admin, assignees=[self.member, self.other], frequency="weekly", due_date=timezone.localdate(), title="Laundry")
        self.assertNotEqual(chores[0].series_id, chores[1].series_id)
        preview = recurrence.schedule_preview(actor=self.member)
        self.assertTrue(preview)
        self.assertEqual({row["assignee"] for row in preview}, {"Alex"})
        self.assertLessEqual(len(preview), 5)
        with self.assertRaises(ValidationError):
            recurrence.bulk_create(actor=self.admin, assignees=[self.member], frequency="", due_date=timezone.localdate(), title="Bad")
        self.client.force_login(self.admin)
        result = self.client.post(reverse("chores:bulk_create"), {"title": "Dishes", "category": "kitchen", "priority": "low", "assignees": [self.member.pk, self.other.pk], "frequency": "daily", "due_date": timezone.localdate().isoformat()})
        self.assertEqual(result.status_code, 302)
