"""Unauthenticated local demo API. X-Demo-Actor is an assertion, not authentication."""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiParameter, OpenApiResponse
from drf_spectacular.types import OpenApiTypes
from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.views import APIView

from . import accounts, completion, recurrence, reminders, services
from . import api_serializers as S
from .dashboard import dashboard_data, workload
from .models import User, AuditEvent, CompletionAttempt

USER_EXAMPLE = {"id": 2, "username": "Alex", "role": "member", "locked_at": None}
CHORE_EXAMPLE = {"id": 1, "title": "Dishes", "description": "", "category": "kitchen", "priority": "medium", "assignee": 2, "due_date": "2026-09-07", "series": None, "scheduled_date": None, "requires_photo": False, "requires_approval": False, "status": "open", "display_status": "Open", "completed_at": None, "deleted_at": None, "catchup_pending": False, "reminders_paused_at": None, "reminders_paused_by": None}
CREATE_EXAMPLE = {"title": "Dishes", "category": "kitchen", "assignee": 2, "due_date": "2026-09-07"}
NOTIFICATION_EXAMPLE = {"id": 1, "chore": 1, "kind": "assignment", "message": "Assigned: Dishes", "created_at": "2026-09-07T12:00:00Z", "read_at": None}


def schema(summary, output, example, input=None, payload=None, parameters=None, status=200):
    return extend_schema(
        summary=summary,
        description="Local demo only. X-Demo-Actor asserts a user ID and is NOT authentication. Anyone can impersonate any actor. Browser login is not used. " + ("Request body example is shown below." if input else "No request body. Example request: send X-Demo-Actor: 1, with the path ID/query parameters shown."),
        request={"application/json": {"type": "object", "properties": {}}} if input is S.EmptyInput else input,
        responses={**({(status, "image/png"): output, (status, "image/jpeg"): output, (status, "image/webp"): output} if output == OpenApiTypes.BINARY else {status: output}), 400: S.ErrorOutput, 403: S.ErrorOutput, 404: S.ErrorOutput},
        parameters=[OpenApiParameter("X-Demo-Actor", int, OpenApiParameter.HEADER, required=True, examples=[OpenApiExample("Primary admin", value=1)])] + (parameters or []),
        examples=[OpenApiExample("Success", value=example, response_only=True, status_codes=[str(status)], media_type="image/png" if output == OpenApiTypes.BINARY else "application/json"), OpenApiExample("Validation error", value={"errors": ["An edit note is required."]}, response_only=True, status_codes=["400"]), OpenApiExample("Forbidden", value={"errors": {"detail": "You do not have permission to perform this action."}}, response_only=True, status_codes=["403"]), OpenApiExample("Not found", value={"errors": {"detail": "Not found."}}, response_only=True, status_codes=["404"])] + ([OpenApiExample("Request", value=payload or {}, request_only=True)] if input else []),
    )


class DemoAPI(APIView):
    authentication_classes = []
    permission_classes = []

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        value = request.headers.get("X-Demo-Actor", "")
        if not value.isascii() or not value.isdigit():
            raise exceptions.ValidationError("Supply X-Demo-Actor as an integer user ID; this is not authentication.")
        self.actor = get_object_or_404(User, pk=int(value), is_active=True, locked_at__isnull=True)

    def handle_exception(self, exc):
        if isinstance(exc, DjangoValidationError):
            return Response({"errors": exc.messages}, status=400)
        response = super().handle_exception(exc)
        response.data = {"errors": response.data}
        return response

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response

    def data(self, serializer):
        value = serializer(data=self.request.data)
        value.is_valid(raise_exception=True)
        return value.validated_data

    def chore(self, pk):
        return get_object_or_404(services.visible_chores(actor=self.actor), pk=pk)

    def member(self, pk):
        accounts.require_admin(self.actor)
        return get_object_or_404(User, pk=pk, household=self.actor.household)


class MembersAPI(DemoAPI):
    @schema("List household members (admin)", S.UserOutput(many=True), USER_EXAMPLE)
    def get(self, request):
        accounts.require_admin(self.actor)
        return Response(S.UserOutput(User.objects.filter(household=self.actor.household), many=True).data)

    @schema("Create member (admin)", S.UserOutput, USER_EXAMPLE, S.MemberInput, {"username": "Alex", "pin": "234567"}, status=201)
    def post(self, request):
        return Response(S.UserOutput(accounts.create_member(actor=self.actor, **self.data(S.MemberInput))).data, status=201)


class MemberAPI(DemoAPI):
    @schema("Inspect member (admin)", S.UserOutput, USER_EXAMPLE)
    def get(self, request, pk):
        return Response(S.UserOutput(self.member(pk)).data)


class RoleAPI(DemoAPI):
    @schema("Promote/demote member (primary admin)", S.UserOutput, {**USER_EXAMPLE, "role": "admin"}, S.RoleInput, {"role": "admin"})
    def post(self, request, pk):
        member = self.member(pk)
        accounts.set_role(actor=self.actor, subject=member, **self.data(S.RoleInput))
        member.refresh_from_db()
        return Response(S.UserOutput(member).data)


class ResetAPI(DemoAPI):
    @schema("Reset member PIN (admin)", S.PINOutput, {"pin": "567891"}, S.EmptyInput, {})
    def post(self, request, pk):
        return Response({"pin": accounts.reset_pin(actor=self.actor, subject=self.member(pk))})


class UnlockAPI(DemoAPI):
    @schema("Unlock account (admin)", S.SuccessOutput, {"success": True}, S.EmptyInput, {})
    def post(self, request, pk):
        accounts.unlock_member(actor=self.actor, subject=self.member(pk))
        return Response({"success": True})


class PINAPI(DemoAPI):
    @schema("Change acting user's PIN", S.SuccessOutput, {"success": True}, S.PINInput, {"current_pin": "234567", "new_pin": "345678"})
    def post(self, request):
        accounts.change_pin(actor=self.actor, **self.data(S.PINInput))
        return Response({"success": True})


FILTERS = [OpenApiParameter("category", str, enum=["kitchen", "bathroom", "laundry", "other"], examples=[OpenApiExample("Kitchen", value="kitchen")]), OpenApiParameter("priority", str, enum=["low", "medium", "high"], examples=[OpenApiExample("High", value="high")])]


class ChoresAPI(DemoAPI):
    @schema("List visible chores", S.ChoreOutput(many=True), CHORE_EXAMPLE, parameters=FILTERS + [OpenApiParameter("q", str, description="Title search for admins", examples=[OpenApiExample("Dishes", value="Dishes")])])
    def get(self, request):
        chores = services.visible_chores(actor=self.actor)
        for key in ("category", "priority"):
            if request.query_params.get(key):
                chores = chores.filter(**{key: request.query_params[key]})
        if self.actor.is_household_admin and request.query_params.get("q"):
            chores = chores.filter(title__icontains=request.query_params["q"])
        return Response(S.ChoreOutput(chores, many=True).data)

    @schema("Create and assign chore", S.ChoreOutput, CHORE_EXAMPLE, S.ChoreInput, CREATE_EXAMPLE, status=201)
    def post(self, request):
        chore = services.create_chore(actor=self.actor, **self.data(S.ChoreInput))
        return Response(S.ChoreOutput(chore).data, status=201)


class ChoreAPI(DemoAPI):
    @schema("Read visible chore", S.ChoreOutput, CHORE_EXAMPLE)
    def get(self, request, pk):
        return Response(S.ChoreOutput(self.chore(pk)).data)

    @schema("Edit chore (major changes need a note)", S.ChoreOutput, {**CHORE_EXAMPLE, "priority": "high"}, S.EditInput, {"priority": "high", "note": "Guests arriving"})
    def patch(self, request, pk):
        return Response(S.ChoreOutput(services.edit_chore(actor=self.actor, chore=self.chore(pk), **self.data(S.EditInput))).data)

    @schema("Delete chore permanently, preserving history", S.SuccessOutput, {"success": True})
    def delete(self, request, pk):
        services.delete_chore(actor=self.actor, chore=self.chore(pk))
        return Response({"success": True})


class DuplicateAPI(DemoAPI):
    @schema("Duplicate with new assignee/date", S.ChoreOutput, CHORE_EXAMPLE, S.DuplicateInput, {"assignee": 2, "due_date": "2026-09-08"}, status=201)
    def post(self, request, pk):
        return Response(S.ChoreOutput(services.duplicate_chore(actor=self.actor, chore=self.chore(pk), **self.data(S.DuplicateInput))).data, status=201)


class BulkAPI(DemoAPI):
    @schema("Bulk assign independent recurring series", S.ChoreOutput(many=True), {**CHORE_EXAMPLE, "series": 1, "scheduled_date": "2026-09-07"}, S.BulkInput, {"title": "Laundry", "assignees": [2, 3], "due_date": "2026-09-07", "frequency": "weekly"}, status=201)
    def post(self, request):
        return Response(S.ChoreOutput(recurrence.bulk_create(actor=self.actor, **self.data(S.BulkInput)), many=True).data, status=201)


def action_api(action, input, payload, summary):
    example = dict(CHORE_EXAMPLE)
    if action in {"submit", "approve", "catchup"}:
        example.update(status="completed", display_status="Completed", completed_at="2026-09-07T12:00:00Z")
    if action == "approve":
        example["requires_approval"] = True
    if action == "reject":
        example.update(status="pending", display_status="Rejected — resubmit", requires_approval=True)
    if action == "pause":
        example.update(reminders_paused_at="2026-09-07T12:00:00Z", reminders_paused_by=1)
    class ActionAPI(DemoAPI):
        @schema(summary, S.ChoreOutput, example, input, payload)
        def post(self, request, pk):
            chore = self.chore(pk)
            data = self.data(input)
            if action == "submit":
                completion.submit(actor=self.actor, chore=chore, **data)
            elif action in {"approve", "reject"}:
                completion.review(actor=self.actor, chore=chore, approve=action == "approve", **data)
            elif action == "undo":
                completion.undo(actor=self.actor, chore=chore)
            elif action == "reactivate":
                completion.reactivate(actor=self.actor, chore=chore, **data)
            elif action == "catchup":
                recurrence.resolve_catchup(actor=self.actor, chore=chore, **data)
            elif action == "pause":
                reminders.pause(actor=self.actor, chore=chore, **data)
            elif action == "resume":
                reminders.resume(actor=self.actor, chore=chore)
            chore.refresh_from_db()
            return Response(S.ChoreOutput(chore).data)
    ActionAPI.__name__ = action.title() + "API"
    return ActionAPI


class ScheduleAPI(DemoAPI):
    @schema("Preview one month of recurrence", S.ScheduleOutput(many=True), {"title": "Laundry", "date": "2026-09-14", "assignee": "Alex", "series_id": 1})
    def get(self, request):
        return Response(S.ScheduleOutput(recurrence.schedule_preview(actor=self.actor), many=True).data)


class DashboardAPI(DemoAPI):
    @schema("Dashboard counts and sections", S.DashboardOutput, {"counts": {"Today": 1, "Upcoming": 0, "Overdue": 0, "Pending approval": 0}, "sections": {"Today": [CHORE_EXAMPLE], "Upcoming": [], "Overdue": [], "Pending approval": []}, "workload": [], "locked_count": 0, "catchups": []}, parameters=FILTERS)
    def get(self, request):
        return Response(S.DashboardOutput(dashboard_data(self.actor, request.query_params)).data)


class WorkloadAPI(DemoAPI):
    @schema("Workload grouped by priority (admin)", S.WorkloadOutput(many=True), {"id": 2, "username": "Alex", "low": 0, "medium": 1, "high": 0, "total": 1}, parameters=[OpenApiParameter("sort", str, enum=["username", "workload"], examples=[OpenApiExample("Workload", value="workload")])])
    def get(self, request):
        accounts.require_admin(self.actor)
        return Response(S.WorkloadOutput(workload(self.actor, request.query_params.get("sort")), many=True).data)


class HistoryAPI(DemoAPI):
    @schema("Personal completion or full admin audit history", S.HistoryOutput(many=True), {"id": 1, "actor": 1, "subject": 2, "chore": 1, "chore_title": "Dishes", "chore_deleted": None, "action": "chore_created", "note": "", "created_at": "2026-09-07T12:00:00Z", "attempt": None})
    def get(self, request):
        events = AuditEvent.objects.filter(household=self.actor.household).select_related("attempt", "chore")
        if not self.actor.is_household_admin:
            events = events.filter(subject=self.actor, attempt__isnull=False)
        return Response(S.HistoryOutput(events, many=True).data)


class NotificationsAPI(DemoAPI):
    @schema("List all acting user's notifications", S.NotificationOutput(many=True), NOTIFICATION_EXAMPLE)
    def get(self, request):
        return Response(S.NotificationOutput(self.actor.notifications.all(), many=True).data)


class NotificationAPI(DemoAPI):
    @schema("Open notification and mark read", S.NotificationOutput, {**NOTIFICATION_EXAMPLE, "read_at": "2026-09-07T12:01:00Z"})
    def get(self, request, pk):
        notification = get_object_or_404(self.actor.notifications, pk=pk)
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at"])
        return Response(S.NotificationOutput(notification).data)


class AttemptsAPI(DemoAPI):
    @schema("Read submission attempts for a visible chore", S.AttemptOutput(many=True), {"id": 1, "chore": 1, "assignee": 2, "submitted_by": 2, "submitted_at": "2026-09-07T12:00:00Z", "due_date_at_submission": "2026-09-07", "note": "Done", "photo_url": "", "status": "completed", "reviewed_by": None, "reviewed_at": None, "rejection_reason": "", "undone_at": None})
    def get(self, request, pk):
        return Response(S.AttemptOutput(self.chore(pk).attempts.all(), many=True).data)


class PhotoAPI(DemoAPI):
    @schema("Download completion photo", OpenApiTypes.BINARY, "<binary PNG/JPEG/WebP image>")
    def get(self, request, pk):
        attempts = CompletionAttempt.objects.filter(chore__household=self.actor.household).exclude(photo="")
        if not self.actor.is_household_admin:
            attempts = attempts.filter(assignee=self.actor)
        return FileResponse(get_object_or_404(attempts, pk=pk).photo.open("rb"))
