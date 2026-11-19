from django.urls import path
from . import views

app_name = "pages"

urlpatterns = [
    path("reviews/", views.reviews, name="reviews"),
    path("reviews/new/", views.submit_review, name="submit_review"),
    path("", views.home, name="home"),
]
