"""Regression coverage for workflow boundaries and failed-operation integrity."""
from datetime import date, timedelta
from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from . import completion, recurrence, services
from .models import AuditEvent, Chore, CompletionAttempt, Notification, RecurringSeries, User


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class WorkflowEdgeCaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(username="Admin", role="primary_admin")
        cls.member = User.objects.create_user(username="Alex")
        cls.other = User.objects.create_user(username="Sam")

    def make_chore(self, **details):
        values = {"title": "Dishes", "due_date": timezone.localdate()}
        values.update(details)
        return services.create_chore(actor=self.admin, assignee=self.member, **values)

    def snapshot(self):
        """Include persisted values, so rejected operations cannot silently mutate rows."""
        return {
            model.__name__: list(model.objects.order_by("pk").values())
            for model in (Chore, RecurringSeries, CompletionAttempt, AuditEvent, Notification)
        }

    def test_invalid_recurring_creation_leaves_no_partial_records(self):
        before = self.snapshot()
        for details in ({"title": ""}, {"priority": "urgent"}, {"frequency": "monthly"}):
            with self.subTest(details=details):
                with self.assertRaises(ValidationError):
                    self.make_chore(**{"frequency": "daily", **details})
                self.assertEqual(self.snapshot(), before)

    def test_invalid_edit_preserves_assignment_and_notifications(self):
        chore = self.make_chore()
        before = self.snapshot()
        with self.assertRaises(ValidationError):
            services.edit_chore(actor=self.admin, chore=chore, assignee=self.other,
                                priority="urgent", note="Reassign")
        self.assertEqual(self.snapshot(), before)

    def test_same_assignee_major_edit_notifies_once(self):
        chore = self.make_chore()
        services.edit_chore(actor=self.admin, chore=chore, priority="high", note="Guests")
        notices = Notification.objects.filter(chore=chore, kind="major_edit")
        self.assertEqual(list(notices.values_list("recipient_id", flat=True)), [self.member.pk])

    def test_bulk_duplicate_assignees_create_one_series_each(self):
        chores = recurrence.bulk_create(actor=self.admin,
            assignees=[self.member, self.other, self.member], frequency="weekly",
            due_date=timezone.localdate(), title="Laundry")
        self.assertEqual(len(chores), 2)
        self.assertEqual({chore.assignee_id for chore in chores}, {self.member.pk, self.other.pk})
        self.assertEqual(RecurringSeries.objects.count(), 2)
        self.assertEqual(Notification.objects.filter(kind="assignment").count(), 2)

    def test_bulk_failure_rolls_back_earlier_assignments(self):
        before = self.snapshot()
        real_create = services.create_chore
        calls = []

        def fail_second(**kwargs):
            calls.append(kwargs)
            if len(calls) == 2:
                raise ValidationError("Second assignment failed")
            return real_create(**kwargs)

        with patch("chores.recurrence.create_chore", side_effect=fail_second):
            with self.assertRaises(ValidationError):
                recurrence.bulk_create(actor=self.admin, assignees=[self.member, self.other],
                    frequency="daily", due_date=timezone.localdate(), title="Laundry")
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.snapshot(), before)

    def test_pending_submission_retry_has_no_side_effects(self):
        chore = self.make_chore(requires_approval=True)
        completion.submit(actor=self.member, chore=chore)
        before = self.snapshot()
        with self.assertRaises(ValidationError):
            completion.submit(actor=self.member, chore=chore)
        self.assertEqual(self.snapshot(), before)

    def test_review_retry_cannot_reverse_decision_or_duplicate_recurrence(self):
        for approved in (True, False):
            with self.subTest(approved=approved):
                chore = self.make_chore(requires_approval=True, frequency="daily")
                completion.submit(actor=self.member, chore=chore)
                completion.review(actor=self.admin, chore=chore, approve=approved, reason="Redo")
                before = self.snapshot()
                with self.assertRaises(ValidationError):
                    completion.review(actor=self.admin, chore=chore, approve=not approved, reason="Redo")
                self.assertEqual(self.snapshot(), before)

    def test_completion_note_limit(self):
        chore = self.make_chore()
        before = self.snapshot()
        with self.assertRaises(ValidationError):
            completion.submit(actor=self.member, chore=chore, note="a" * 2001)
        self.assertEqual(self.snapshot(), before)
        attempt = completion.submit(actor=self.member, chore=chore, note="a" * 2000)
        self.assertEqual(attempt.note, "a" * 2000)

    def test_disallowed_and_oversized_photos_leave_no_records(self):
        chore = self.make_chore(requires_photo=True)
        gif = BytesIO()
        Image.new("RGB", (2, 2)).save(gif, "GIF")
        before = self.snapshot()
        for photo in (None, SimpleUploadedFile("proof.gif", gif.getvalue()),
                      SimpleUploadedFile("large.png", b"x" * (5 * 1024 * 1024 + 1))):
            with self.subTest(photo=photo.name if photo else "missing"):
                with self.assertRaises(ValidationError):
                    completion.submit(actor=self.member, chore=chore, photo=photo)
                self.assertEqual(self.snapshot(), before)

    def test_supported_photos_are_saved_with_safe_generated_names(self):
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            for image_format in ("JPEG", "PNG", "WEBP"):
                with self.subTest(image_format=image_format):
                    data = BytesIO()
                    Image.new("RGB", (2, 2)).save(data, image_format)
                    attempt = completion.submit(actor=self.member, chore=self.make_chore(),
                        photo=SimpleUploadedFile("untrusted.png", data.getvalue()))
                    self.assertTrue(attempt.photo.name.endswith("." + image_format.lower()))
                    self.assertNotIn("untrusted", attempt.photo.name)
                    with attempt.photo.open("rb") as saved:
                        self.assertEqual(saved.read(), data.getvalue())

    def test_member_cannot_undo_admin_submission(self):
        chore = self.make_chore()
        completion.submit(actor=self.admin, chore=chore)
        before = self.snapshot()
        with self.assertRaises(ValidationError):
            completion.undo(actor=self.member, chore=chore)
        self.assertEqual(self.snapshot(), before)

    def test_deleted_chore_preserves_history_and_blocks_submission(self):
        chore = self.make_chore()
        attempt = completion.submit(actor=self.member, chore=chore, note="Evidence")
        services.delete_chore(actor=self.admin, chore=chore)
        before = self.snapshot()
        services.delete_chore(actor=self.admin, chore=chore)
        self.assertEqual(self.snapshot(), before)
        self.assertTrue(CompletionAttempt.objects.filter(pk=attempt.pk, note="Evidence").exists())
        self.assertTrue(AuditEvent.objects.filter(attempt=attempt).exists())
        for actor in (self.member, self.admin):
            with self.subTest(actor=actor.username):
                self.assertFalse(services.visible_chores(actor=actor).filter(pk=chore.pk).exists())
                with self.assertRaises(PermissionDenied):
                    completion.submit(actor=actor, chore=chore)
        self.assertEqual(self.snapshot(), before)

    def test_next_occurrence_due_today_does_not_require_catchup(self):
        chore = self.make_chore(frequency="daily", due_date=timezone.localdate() - timedelta(days=1))
        completion.submit(actor=self.member, chore=chore)
        chore.refresh_from_db()
        self.assertFalse(chore.catchup_pending)
        self.assertTrue(chore.recurrence_processed)
        self.assertEqual(chore.series.occurrences.exclude(pk=chore.pk).get().due_date, timezone.localdate())

    def test_invalid_catchup_choice_preserves_pending_decision(self):
        chore = self.make_chore(frequency="daily", due_date=timezone.localdate() - timedelta(days=3))
        completion.submit(actor=self.member, chore=chore)
        before = self.snapshot()
        with self.assertRaises(ValidationError):
            recurrence.resolve_catchup(actor=self.admin, chore=chore, choice="invalid")
        self.assertEqual(self.snapshot(), before)

    def test_ended_series_does_not_advance_or_appear_in_preview(self):
        chore = self.make_chore(frequency="daily")
        chore.series.ended_at = timezone.now()
        chore.series.save()
        completion.submit(actor=self.member, chore=chore)
        self.assertEqual(chore.series.occurrences.count(), 1)
        self.assertEqual(recurrence.schedule_preview(actor=self.admin), [])

    def test_schedule_preview_clamps_month_end_and_handles_year_rollover(self):
        for today, end in ((date(2028, 1, 31), date(2028, 2, 29)),
                           (date(2027, 1, 31), date(2027, 2, 28)),
                           (date(2027, 12, 31), date(2028, 1, 31))):
            with self.subTest(today=today), patch("chores.recurrence.timezone.localdate", return_value=today):
                chore = self.make_chore(frequency="daily", due_date=today)
                dates = [row["date"] for row in recurrence.schedule_preview(actor=self.member)
                         if row["series_id"] == chore.series_id]
                self.assertEqual(dates, [today + timedelta(days=offset)
                                       for offset in range(1, (end - today).days + 1)])
