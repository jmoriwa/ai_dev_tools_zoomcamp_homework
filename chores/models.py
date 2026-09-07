from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q


class Household(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    name = models.CharField(max_length=120, default="Our household")

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(id=1), name="single_household")]

    def __str__(self):
        return self.name


class User(AbstractUser):
    class Role(models.TextChoices):
        PRIMARY_ADMIN = "primary_admin", "Primary admin"
        ADMIN = "admin", "Secondary admin"
        MEMBER = "member", "Member"

    household = models.ForeignKey(Household, default=1, on_delete=models.PROTECT)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
    previous_pin_hash = models.CharField(max_length=128, blank=True)
    failed_login_attempts = models.PositiveSmallIntegerField(default=0)
    locked_at = models.DateTimeField(null=True, blank=True)
    pin_changed_at = models.DateTimeField(null=True, blank=True)
    session_version = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["household"], condition=Q(role="primary_admin"), name="one_primary_admin")]

    @property
    def is_household_admin(self):
        return self.role in {self.Role.PRIMARY_ADMIN, self.Role.ADMIN}


class ChoreDetails(models.Model):
    class Category(models.TextChoices):
        KITCHEN = "kitchen", "Kitchen"
        BATHROOM = "bathroom", "Bathroom"
        LAUNDRY = "laundry", "Laundry"
        OTHER = "other", "Other"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    requires_photo = models.BooleanField(default=False)
    requires_approval = models.BooleanField(default=False)

    class Meta:
        abstract = True

    def __str__(self):
        return self.title


class RecurringSeries(ChoreDetails):
    class Frequency(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"

    household = models.ForeignKey(Household, default=1, on_delete=models.PROTECT)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="recurring_series")
    frequency = models.CharField(max_length=10, choices=Frequency.choices)
    start_date = models.DateField()
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Chore(ChoreDetails):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        PENDING = "pending", "Pending approval"
        COMPLETED = "completed", "Completed"

    household = models.ForeignKey(Household, default=1, on_delete=models.PROTECT)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="assigned_chores")
    series = models.ForeignKey(RecurringSeries, null=True, blank=True, on_delete=models.PROTECT, related_name="occurrences")
    scheduled_date = models.DateField(null=True, blank=True, help_text="Original recurrence date, unaffected by due-date edits.")
    due_date = models.DateField(db_index=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    completed_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    reminders_paused_at = models.DateTimeField(null=True, blank=True)
    reminders_paused_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="paused_chores")
    reminder_pause_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["series", "scheduled_date"], name="unique_series_occurrence"),
            models.CheckConstraint(condition=(Q(series__isnull=True, scheduled_date__isnull=True) | Q(series__isnull=False, scheduled_date__isnull=False)), name="series_requires_schedule"),
        ]
        indexes = [models.Index(fields=["assignee", "status", "deleted_at"])]


class CompletionAttempt(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        COMPLETED = "completed", "Completed without review"

    chore = models.ForeignKey(Chore, on_delete=models.PROTECT, related_name="attempts")
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="completion_attempts")
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="submitted_attempts")
    submitted_at = models.DateTimeField(auto_now_add=True)
    due_date_at_submission = models.DateField()
    note = models.TextField(blank=True)
    photo = models.FileField(upload_to="completion_photos/%Y/%m/", blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="reviewed_attempts")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    undone_at = models.DateTimeField(null=True, blank=True)


class AuditEvent(models.Model):
    household = models.ForeignKey(Household, default=1, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="audit_actions")
    subject = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="audit_history")
    chore = models.ForeignKey(Chore, null=True, blank=True, on_delete=models.PROTECT, related_name="audit_events")
    attempt = models.ForeignKey(CompletionAttempt, null=True, blank=True, on_delete=models.PROTECT, related_name="audit_events")
    action = models.CharField(max_length=50)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]


class Notification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="notifications")
    chore = models.ForeignKey(Chore, null=True, blank=True, on_delete=models.PROTECT, related_name="notifications")
    kind = models.CharField(max_length=50)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    delivery_key = models.CharField(max_length=200, unique=True, null=True, blank=True, help_text="Repeat-safe identifier for scheduled reminders.")

    class Meta:
        ordering = ["-created_at", "-pk"]
