from datetime import timedelta
from unittest.mock import patch
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from . import completion, reminders, services
from .models import User, Notification, AuditEvent


class ReminderTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="Admin", role="primary_admin")
        self.member = User.objects.create_user(username="Alex")
        self.other = User.objects.create_user(username="Sam")
        self.chore = services.create_chore(actor=self.admin, assignee=self.member, title="Dishes", due_date=timezone.localdate(), requires_approval=True)

    def test_due_repeat_safe_pause_resume_and_completed(self):
        reminders.pause(actor=self.admin, chore=self.chore)
        self.assertEqual(reminders.send_reminders(), 0)
        reminders.resume(actor=self.admin, chore=self.chore)
        self.assertEqual(reminders.send_reminders(), 1)
        self.assertEqual(reminders.send_reminders(), 0)
        completion.submit(actor=self.member, chore=self.chore)
        completion.review(actor=self.admin, chore=self.chore, approve=True)
        self.assertEqual(reminders.send_reminders(), 0)
        self.assertEqual(AuditEvent.objects.filter(action__in=["reminders_paused", "reminders_resumed"]).count(), 2)

    def test_rejected_immediate_and_daily_admin_delay_until_resubmission(self):
        self.chore.due_date -= timedelta(days=1)
        self.chore.save()
        completion.submit(actor=self.member, chore=self.chore)
        start = timezone.now()
        with patch("django.utils.timezone.now", return_value=start):
            completion.review(actor=self.admin, chore=self.chore, approve=False, reason="Secret reason")
        self.assertEqual(Notification.objects.filter(kind="rejected_overdue").count(), 1)
        self.assertEqual(Notification.objects.filter(kind="rejected_overdue_admin").count(), 0)
        self.assertFalse(Notification.objects.filter(message__contains="Secret reason").exists())
        self.assertEqual(reminders.send_reminders(now=start + timedelta(hours=23)), 1)
        self.assertEqual(Notification.objects.filter(kind="rejected_overdue_admin").count(), 0)
        reminders.send_reminders(now=start + timedelta(days=1))
        self.assertEqual(Notification.objects.filter(kind="rejected_overdue_admin").count(), 1)
        reminders.send_reminders(now=start + timedelta(days=2))
        self.assertEqual(Notification.objects.filter(kind="rejected_overdue_admin").count(), 2)
        completion.submit(actor=self.member, chore=self.chore)
        self.assertEqual(reminders.send_reminders(now=start + timedelta(days=3)), 0)

    def test_pause_reason_and_no_automatic_resume(self):
        self.chore.due_date -= timedelta(days=1)
        self.chore.save()
        with self.assertRaises(ValidationError):
            reminders.pause(actor=self.admin, chore=self.chore)
        with self.assertRaises(PermissionDenied):
            reminders.pause(actor=self.member, chore=self.chore, reason="Away")
        reminders.pause(actor=self.admin, chore=self.chore, reason="Away")
        self.assertEqual(reminders.send_reminders(now=timezone.now() + timedelta(days=100)), 0)
        self.chore.refresh_from_db()
        self.assertEqual(self.chore.reminders_paused_by, self.admin)

    def test_notification_read_and_ownership(self):
        notification = self.member.notifications.get()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("chores:notification_open", args=[notification.pk])).status_code, 404)
        self.client.force_login(self.member)
        self.assertContains(self.client.get(reverse("chores:notifications")), "Notifications (1)")
        response = self.client.get(reverse("chores:notification_open", args=[notification.pk]))
        self.assertContains(response, "Open chore")
        notification.refresh_from_db()
        self.assertIsNotNone(notification.read_at)
        self.assertContains(self.client.get(reverse("chores:notifications")), "Notifications (0)")
