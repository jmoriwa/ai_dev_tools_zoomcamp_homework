"""Repeatable demo fixtures; existing accounts and chores are never reset."""
from datetime import timedelta
from io import BytesIO

from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from chores import completion, services
from chores.models import Chore, Household, User

DEMO_USERS = [
    ("demo_admin", "123456", "primary_admin"),
    ("demo_helper", "234567", "admin"),
    ("demo_alex", "345678", "member"),
    ("demo_sam", "456789", "member"),
    ("demo_jamie", "567891", "member"),
]


class Command(BaseCommand):
    help = "Add repeatable local demo accounts and chores without overwriting existing data."

    @transaction.atomic
    def handle(self, *args, **options):
        Household.objects.get_or_create(pk=1)
        if User.objects.filter(role="primary_admin").exclude(username="demo_admin").exists():
            raise CommandError("A different primary admin exists. Use a fresh demo database; existing accounts were not changed.")
        users = {}
        for username, pin, role in DEMO_USERS:
            user, created = User.objects.get_or_create(username=username, defaults={"role": role})
            if user.role != role:
                raise CommandError(f"Existing {username} has a different role. No demo data was changed.")
            if created:
                user.set_password(pin)
                user.save()
            users[username] = user
        admin = users["demo_admin"]
        today = timezone.localdate()
        scenarios = [
            ("Wash dishes", "demo_alex", 0, "kitchen", "high", "", False, False, "open"),
            ("Clean bathroom", "demo_sam", -2, "bathroom", "high", "", False, False, "open"),
            ("Fold laundry", "demo_jamie", 2, "laundry", "low", "", False, False, "open"),
            ("Wipe counters", "demo_alex", 0, "kitchen", "medium", "daily", False, False, "open"),
            ("Wash towels", "demo_sam", 3, "laundry", "medium", "weekly", False, False, "open"),
            ("Mop floor", "demo_alex", 0, "kitchen", "high", "", True, True, "pending"),
            ("Take out recycling", "demo_jamie", -1, "other", "low", "", False, False, "completed"),
            ("Scrub sink", "demo_sam", -1, "bathroom", "medium", "", True, False, "rejected"),
        ]
        created_count = 0
        for title, username, offset, category, priority, frequency, approval, photo, state in scenarios:
            title = f"[Demo] {title}"
            member = users[username]
            if Chore.objects.filter(title=title, assignee=member).exists():
                continue
            chore = services.create_chore(actor=admin, assignee=member, title=title, description="Example household chore for the local demo.", due_date=today + timedelta(days=offset), category=category, priority=priority, frequency=frequency, requires_approval=approval, requires_photo=photo)
            created_count += 1
            if state != "open":
                upload = None
                if photo:
                    stream = BytesIO()
                    Image.new("RGB", (160, 100), "#52765c").save(stream, "PNG")
                    upload = SimpleUploadedFile("demo-proof.png", stream.getvalue(), content_type="image/png")
                completion.submit(actor=member, chore=chore, note="Demo completion note", photo=upload)
                if state == "rejected":
                    completion.review(actor=admin, chore=chore, approve=False, reason="Please clean around the drain and resubmit.")
        self.stdout.write(self.style.SUCCESS(f"Demo ready: {created_count} new chores. Existing PINs and chores were retained. See README for initial demo credentials."))
