from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from .admin_help import admin_guide

urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
    path("contacts/", include("contacts.urls")),
    path("journal/", include("journal.urls")),
    path("accounts/", include("django.contrib.auth.urls")),
    path("courses/", include("courses.urls")),
    path("admin/help/", admin.site.admin_view(admin_guide), name="admin_guide"),
    path("admin/", admin.site.urls),
    path("", include("pages.urls")),
    path("tuner/", include("tuner.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
