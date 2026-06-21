from django.urls import path
from . import views

app_name = "tuner"

urlpatterns = [
    path("", views.tuner_page, name="index"),
]
