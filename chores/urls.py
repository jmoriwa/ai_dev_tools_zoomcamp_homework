from django.urls import path
from . import views

app_name = "chores"
urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("pin/", views.change_pin_view, name="change_pin"),
    path("members/", views.members, name="members"),
    path("members/<int:pk>/role/", views.member_action, {"action": "role"}, name="member_role"),
    path("members/<int:pk>/reset/", views.member_action, {"action": "reset"}, name="member_reset"),
    path("members/<int:pk>/unlock/", views.member_action, {"action": "unlock"}, name="member_unlock"),
]
