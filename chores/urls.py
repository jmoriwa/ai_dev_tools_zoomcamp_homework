from django.urls import path
from . import views
from . import chore_views

app_name = "chores"
urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("schedule/", chore_views.schedule, name="schedule"),
    path("chores/bulk/", chore_views.bulk_create, name="bulk_create"),
    path("history/", chore_views.history, name="history"),
    path("photos/<int:pk>/", chore_views.attempt_photo, name="attempt_photo"),
    path("chores/", chore_views.chore_list, name="chore_list"),
    path("chores/new/", chore_views.chore_form, name="chore_create"),
    path("chores/<int:pk>/", chore_views.chore_detail, name="chore_detail"),
    path("chores/<int:pk>/edit/", chore_views.chore_form, name="chore_edit"),
    path("chores/<int:pk>/duplicate/", chore_views.chore_form, {"duplicate": True}, name="chore_duplicate"),
    path("chores/<int:pk>/delete/", chore_views.chore_delete, name="chore_delete"),
    path("", views.home, name="home"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("pin/", views.change_pin_view, name="change_pin"),
    path("members/", views.members, name="members"),
    path("members/<int:pk>/role/", views.member_action, {"action": "role"}, name="member_role"),
    path("members/<int:pk>/reset/", views.member_action, {"action": "reset"}, name="member_reset"),
    path("members/<int:pk>/unlock/", views.member_action, {"action": "unlock"}, name="member_unlock"),
]
for action in ("submit", "approve", "reject", "undo", "reactivate", "catchup"):
    urlpatterns.append(path(f"chores/<int:pk>/{action}/", chore_views.completion_action, {"action": action}, name=f"chore_{action}"))
