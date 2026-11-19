from django.urls import path

from . import views
from . import trial

app_name = "contacts"

urlpatterns = [
    path("trial/", trial.trial_page, name="trial"),
    path("trial/success/", trial.trial_success, name="trial_success"),
    path("", views.contact_page, name="contact"),
]
