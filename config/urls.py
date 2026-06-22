from django.contrib import admin
from django.urls import path, include, include

urlpatterns = [
    path("accounts/", include("django.contrib.auth.urls")),
    path("courses/", include("courses.urls")),
    path("admin/", admin.site.urls),
    path("", include("pages.urls")),
    path("tuner/", include("tuner.urls")),
]
