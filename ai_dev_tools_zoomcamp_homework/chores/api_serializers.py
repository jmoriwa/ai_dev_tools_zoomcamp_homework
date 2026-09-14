from rest_framework import serializers as s
from .models import User, Chore, CompletionAttempt, AuditEvent, Notification
from .completion import status_label


class UserOutput(s.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "role", "locked_at"]


class MemberInput(s.Serializer):
    username = s.CharField(max_length=150, trim_whitespace=False)
    pin = s.CharField(write_only=True, trim_whitespace=False)


class RoleInput(s.Serializer):
    role = s.ChoiceField(choices=["member", "admin"])


class PINInput(s.Serializer):
    current_pin = s.CharField(write_only=True, trim_whitespace=False)
    new_pin = s.CharField(write_only=True, trim_whitespace=False)


class PINOutput(s.Serializer):
    pin = s.CharField()


class ChoreOutput(s.ModelSerializer):
    display_status = s.SerializerMethodField()

    def get_display_status(self, obj) -> str:
        return status_label(obj)

    class Meta:
        model = Chore
        fields = ["id", "title", "description", "category", "priority", "assignee", "due_date", "series", "scheduled_date", "requires_photo", "requires_approval", "status", "display_status", "completed_at", "deleted_at", "catchup_pending", "reminders_paused_at", "reminders_paused_by"]


class ChoreInput(s.ModelSerializer):
    frequency = s.ChoiceField(choices=["", "daily", "weekly"], default="", required=False)
    class Meta:
        model = Chore
        fields = ["title", "description", "category", "priority", "assignee", "due_date", "requires_photo", "requires_approval", "frequency"]


class EditInput(s.ModelSerializer):
    note = s.CharField(required=False, allow_blank=True, default="")
    class Meta:
        model = Chore
        fields = ["title", "description", "category", "priority", "assignee", "due_date", "requires_photo", "requires_approval", "note"]
        extra_kwargs = {key: {"required": False} for key in fields if key != "note"}


class DuplicateInput(s.Serializer):
    assignee = s.PrimaryKeyRelatedField(queryset=User.objects.all())
    due_date = s.DateField()


class BulkInput(ChoreInput):
    assignees = s.PrimaryKeyRelatedField(queryset=User.objects.all(), many=True, allow_empty=False)
    frequency = s.ChoiceField(choices=["daily", "weekly"])
    class Meta(ChoreInput.Meta):
        fields = [field for field in ChoreInput.Meta.fields if field != "assignee"] + ["assignees"]


class SubmissionInput(s.Serializer):
    note = s.CharField(max_length=2000, required=False, allow_blank=True, default="")
    photo = s.ImageField(required=False)


class ReasonInput(s.Serializer):
    reason = s.CharField()


class NoteInput(s.Serializer):
    note = s.CharField()


class PauseInput(s.Serializer):
    reason = s.CharField(required=False, allow_blank=True, default="")


class CatchupInput(s.Serializer):
    choice = s.ChoiceField(choices=["all", "skip"])


class EmptyInput(s.Serializer):
    pass


class SuccessOutput(s.Serializer):
    success = s.BooleanField()


class ErrorOutput(s.Serializer):
    errors = s.JSONField()


class AttemptOutput(s.ModelSerializer):
    photo_url = s.SerializerMethodField()

    def get_photo_url(self, obj) -> str:
        return f"/api/photos/{obj.pk}/" if obj.photo else ""

    class Meta:
        model = CompletionAttempt
        fields = ["id", "chore", "assignee", "submitted_by", "submitted_at", "due_date_at_submission", "note", "photo_url", "status", "reviewed_by", "reviewed_at", "rejection_reason", "undone_at"]


class HistoryOutput(s.ModelSerializer):
    attempt = AttemptOutput(read_only=True)
    chore_title = s.CharField(source="chore.title", allow_null=True)
    chore_deleted = s.DateTimeField(source="chore.deleted_at", allow_null=True)
    class Meta:
        model = AuditEvent
        fields = ["id", "actor", "subject", "chore", "chore_title", "chore_deleted", "action", "note", "created_at", "attempt"]


class NotificationOutput(s.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "chore", "kind", "message", "created_at", "read_at"]


class ScheduleOutput(s.Serializer):
    title = s.CharField()
    date = s.DateField()
    assignee = s.CharField()
    series_id = s.IntegerField()


class WorkloadOutput(s.Serializer):
    id = s.IntegerField()
    username = s.CharField()
    low = s.IntegerField()
    medium = s.IntegerField()
    high = s.IntegerField()
    total = s.IntegerField()


class DashboardOutput(s.Serializer):
    counts = s.DictField(child=s.IntegerField())
    sections = s.DictField(child=ChoreOutput(many=True))
    workload = WorkloadOutput(many=True)
    locked_count = s.IntegerField()
    catchups = ChoreOutput(many=True)
