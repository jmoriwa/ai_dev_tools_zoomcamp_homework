from io import StringIO
from tempfile import TemporaryDirectory
from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings
from .models import User, Chore, CompletionAttempt, AuditEvent


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class SeedTests(TestCase):
    def test_repeatable_seed_preserves_accounts_history_and_photos(self):
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            call_command("seed_demo", stdout=StringIO())
            self.assertEqual(User.objects.count(), 5)
            self.assertEqual(Chore.objects.count(), 8)
            self.assertTrue(Chore.objects.filter(status="pending", requires_photo=True).exists())
            self.assertTrue(Chore.objects.filter(status="completed").exists())
            self.assertTrue(Chore.objects.filter(series__frequency="daily").exists())
            self.assertTrue(Chore.objects.filter(series__frequency="weekly").exists())
            proof = CompletionAttempt.objects.exclude(photo="").get()
            self.assertTrue(proof.photo.storage.exists(proof.photo.name))
            count = AuditEvent.objects.count()
            member = User.objects.get(username="demo_alex")
            member.set_password("678912")
            member.save()
            call_command("seed_demo", stdout=StringIO())
            self.assertEqual(Chore.objects.count(), 8)
            self.assertEqual(AuditEvent.objects.count(), count)
            member.refresh_from_db()
            self.assertTrue(member.check_password("678912"))

    def test_existing_primary_admin_is_preserved(self):
        User.objects.create_user(username="Existing", role="primary_admin")
        with self.assertRaises(CommandError):
            call_command("seed_demo", stdout=StringIO())
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(Chore.objects.count(), 0)
