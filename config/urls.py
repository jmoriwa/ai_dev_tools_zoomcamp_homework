from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("api/", include("chores.api_urls")),
    path("", include("chores.urls")),
    path("admin/", admin.site.urls),
]
