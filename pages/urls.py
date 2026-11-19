from django.urls import path
from . import views

app_name = "pages"

urlpatterns = [
    path("favicon.ico", views.favicon, name="favicon"),
    path("reviews/", views.reviews, name="reviews"),
    path("reviews/new/", views.submit_review, name="submit_review"),
    path("", views.home, name="home"),
]
