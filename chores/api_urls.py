from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from . import api as A
from . import api_serializers as S

urlpatterns = [
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("members/", A.MembersAPI.as_view()),
    path("members/<int:pk>/", A.MemberAPI.as_view()),
    path("members/<int:pk>/role/", A.RoleAPI.as_view()),
    path("members/<int:pk>/reset/", A.ResetAPI.as_view()),
    path("members/<int:pk>/unlock/", A.UnlockAPI.as_view()),
    path("me/pin/", A.PINAPI.as_view()),
    path("chores/", A.ChoresAPI.as_view()),
    path("chores/<int:pk>/", A.ChoreAPI.as_view()),
    path("chores/<int:pk>/duplicate/", A.DuplicateAPI.as_view()),
    path("chores/bulk/", A.BulkAPI.as_view()),
    path("chores/<int:pk>/attempts/", A.AttemptsAPI.as_view()),
    path("schedule/", A.ScheduleAPI.as_view()),
    path("dashboard/", A.DashboardAPI.as_view()),
    path("workload/", A.WorkloadAPI.as_view()),
    path("history/", A.HistoryAPI.as_view()),
    path("notifications/", A.NotificationsAPI.as_view()),
    path("notifications/<int:pk>/", A.NotificationAPI.as_view()),
    path("photos/<int:pk>/", A.PhotoAPI.as_view()),
]

for action, serializer, example, summary in [
    ("submit", S.SubmissionInput, {"note": "All done"}, "Submit completion (multipart for photos)"),
    ("approve", S.EmptyInput, {}, "Approve pending submission (admin)"),
    ("reject", S.ReasonInput, {"reason": "Clean the edges"}, "Reject with required reason (admin)"),
    ("undo", S.EmptyInput, {}, "Undo own unreviewed completion within 15 minutes"),
    ("reactivate", S.NoteInput, {"note": "Needs another pass"}, "Reactivate completed chore (admin)"),
    ("catchup", S.CatchupInput, {"choice": "skip"}, "Resolve missed recurrence (admin)"),
    ("pause", S.PauseInput, {"reason": "Member away"}, "Pause reminders indefinitely (admin)"),
    ("resume", S.EmptyInput, {}, "Resume reminders (admin)"),
]:
    urlpatterns.append(path(f"chores/<int:pk>/{action}/", A.action_api(action, serializer, example, summary).as_view()))
