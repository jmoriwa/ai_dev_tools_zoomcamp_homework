from datetime import timedelta
from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import completion, services
from .models import AuditEvent, User, Notification


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class CompletionTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="Admin", role="primary_admin")
        self.member = User.objects.create_user(username="Alex")
        self.other = User.objects.create_user(username="Sam")
        self.chore = services.create_chore(actor=self.admin, assignee=self.member, title="Dishes", due_date=timezone.localdate())
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.directory.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

    def photo(self):
        data = BytesIO()
        Image.new("RGB", (4, 4)).save(data, "PNG")
        return SimpleUploadedFile("photo.png", data.getvalue(), content_type="image/png")

    def test_standard_completion_and_retries(self):
        attempt = completion.submit(actor=self.member, chore=self.chore, note="Done")
        self.chore.refresh_from_db()
        self.assertEqual(self.chore.status, "completed")
        self.assertEqual(attempt.note, "Done")
        with self.assertRaises(ValidationError):
            completion.submit(actor=self.member, chore=self.chore)
        self.assertEqual(self.chore.attempts.count(), 1)

    def test_approved_completion_undo_uses_final_completion_time(self):
        self.chore.requires_approval = True
        self.chore.save()
        completion.submit(actor=self.member, chore=self.chore)
        later = timezone.now() + timedelta(days=1)
        with patch("django.utils.timezone.now", return_value=later):
            completion.review(actor=self.admin, chore=self.chore, approve=True)
        with patch("django.utils.timezone.now", return_value=later + timedelta(minutes=14)):
            completion.undo(actor=self.member, chore=self.chore)
        self.chore.refresh_from_db()
        self.assertEqual(self.chore.status, "open")

    def test_review_rejection_resubmission_preserves_attempts(self):
        self.chore.requires_approval = True
        self.chore.requires_photo = True
        self.chore.save()
        attempt = completion.submit(actor=self.member, chore=self.chore, note="First", photo=self.photo())
        self.chore.refresh_from_db()
        self.assertEqual(completion.status_label(self.chore), "Submitted on time")
        with self.assertRaises(ValidationError):
            completion.review(actor=self.admin, chore=self.chore, approve=False)
        completion.review(actor=self.admin, chore=self.chore, approve=False, reason="Hidden reason")
        self.assertFalse(Notification.objects.filter(message__contains="Hidden reason").exists())
        with self.assertRaises(ValidationError):
            completion.submit(actor=self.member, chore=self.chore)
        fresh = completion.submit(actor=self.member, chore=self.chore, photo=self.photo())
        self.assertEqual(fresh.note, "")
        attempt.refresh_from_db()
        self.assertEqual(attempt.note, "First")
        self.assertEqual(attempt.status, "rejected")
        self.assertTrue(attempt.photo.storage.exists(attempt.photo.name))
        completion.review(actor=self.admin, chore=self.chore, approve=True)
        self.chore.refresh_from_db()
        self.assertEqual(self.chore.status, "completed")
        self.assertTrue(AuditEvent.objects.filter(action="resubmitted", attempt=fresh).exists())

    def test_invalid_photo_and_ownership(self):
        with self.assertRaises(ValidationError):
            completion.submit(actor=self.member, chore=self.chore, photo=SimpleUploadedFile("fake.png", b"not an image"))
        with self.assertRaises(PermissionDenied):
            completion.submit(actor=self.other, chore=self.chore)
        with self.assertRaises(PermissionDenied):
            completion.review(actor=self.member, chore=self.chore, approve=True)

    def test_undo_boundary_and_admin_reactivation(self):
        attempt = completion.submit(actor=self.member, chore=self.chore)
        self.chore.refresh_from_db()
        with patch("django.utils.timezone.now", return_value=self.chore.completed_at + timedelta(minutes=15)):
            with self.assertRaises(ValidationError):
                completion.undo(actor=self.member, chore=self.chore)
        with patch("django.utils.timezone.now", return_value=attempt.submitted_at + timedelta(minutes=14, seconds=59)):
            completion.undo(actor=self.member, chore=self.chore)
        self.chore.refresh_from_db()
        self.assertEqual(self.chore.status, "open")
        completion.submit(actor=self.admin, chore=self.chore)
        self.assertTrue(AuditEvent.objects.filter(action="admin_completion", actor=self.admin).exists())
        with self.assertRaises(ValidationError):
            completion.reactivate(actor=self.admin, chore=self.chore, note="")
        completion.reactivate(actor=self.admin, chore=self.chore, note="Needs another pass")
        self.assertTrue(AuditEvent.objects.filter(action="reactivated").exists())

    def test_on_time_pending_does_not_become_overdue_but_rejected_does(self):
        self.chore.requires_approval = True
        self.chore.save()
        completion.submit(actor=self.member, chore=self.chore)
        self.chore.refresh_from_db()
        with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(days=2)):
            self.assertEqual(completion.status_label(self.chore), "Submitted on time")
            completion.review(actor=self.admin, chore=self.chore, approve=False, reason="Redo")
            self.assertEqual(completion.status_label(self.chore), "Rejected — overdue")

    def test_pages_and_private_photo_history(self):
        self.chore.requires_approval = True
        self.chore.save()
        self.client.force_login(self.member)
        self.assertEqual(self.client.post(reverse("chores:chore_submit", args=[self.chore.pk]), {"note": "My proof", "photo": self.photo()}).status_code, 302)
        attempt = self.chore.attempts.get()
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("chores:chore_detail", args=[self.chore.pk])), "Review submission")
        self.assertEqual(self.client.post(reverse("chores:chore_reject", args=[self.chore.pk]), {"reason": "Again"}).status_code, 302)
        self.client.force_login(self.member)
        self.assertContains(self.client.get(reverse("chores:chore_detail", args=[self.chore.pk])), "Again")
        self.client.post(reverse("chores:chore_submit", args=[self.chore.pk]))
        self.client.force_login(self.admin)
        self.client.post(reverse("chores:chore_approve", args=[self.chore.pk]))
        services.delete_chore(actor=self.admin, chore=self.chore)
        self.client.force_login(self.member)
        self.assertContains(self.client.get(reverse("chores:history")), "My proof")
        response = self.client.get(reverse("chores:attempt_photo", args=[attempt.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b"".join(response.streaming_content))
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(reverse("chores:history")), "My proof")
        self.assertEqual(self.client.get(reverse("chores:attempt_photo", args=[attempt.pk])).status_code, 404)
