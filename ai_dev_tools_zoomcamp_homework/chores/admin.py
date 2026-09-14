from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Household, User, Chore, RecurringSeries, CompletionAttempt, AuditEvent, Notification


@admin.register(User)
class HouseholdUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Household", {"fields": ("household", "role", "failed_login_attempts", "locked_at", "pin_changed_at", "session_version")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Household", {"fields": ("household", "role")}),)
    list_display = ("username", "role", "household", "locked_at", "is_staff")
    list_filter = ("role", "is_staff")
    readonly_fields = ("pin_changed_at", "session_version")


@admin.register(Chore)
class ChoreAdmin(admin.ModelAdmin):
    list_display = ("title", "assignee", "due_date", "priority", "status", "deleted_at")
    list_filter = ("status", "priority", "category", "requires_approval")
    search_fields = ("title", "assignee__username")
    readonly_fields = ("created_at", "updated_at")


@admin.register(RecurringSeries)
class SeriesAdmin(admin.ModelAdmin):
    list_display = ("title", "assignee", "frequency", "start_date", "ended_at")
    list_filter = ("frequency",)


class HistoryAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CompletionAttempt)
class AttemptAdmin(HistoryAdmin):
    list_display = ("chore", "submitted_by", "submitted_at", "status")
    list_filter = ("status",)


@admin.register(AuditEvent)
class AuditAdmin(HistoryAdmin):
    list_display = ("action", "actor", "subject", "chore", "created_at")
    list_filter = ("action",)


@admin.register(Notification)
class NotificationAdmin(HistoryAdmin):
    list_display = ("recipient", "kind", "created_at", "read_at")
    list_filter = ("kind",)


admin.site.register(Household)
admin.site.site_header = "Household internal management"
