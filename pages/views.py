from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import get_language
from config.i18n import bilingual as bt
from courses.models import CourseEnrollment
from .content import HOME_COPY
from .models import Review
from .forms import ReviewForm


def home(request):
    language = "ru" if get_language() == "ru" else "en"
    return render(request, "home.html", {"copy": HOME_COPY[language], "reviews": Review.objects.filter(is_published=True)[:6]})


def reviews(request):
    return render(request, "reviews.html", {"reviews": Review.objects.filter(is_published=True)})


@login_required
def submit_review(request):
    eligible = CourseEnrollment.objects.filter(user=request.user, is_active=True).filter(Q(access_expires_at__isnull=True) | Q(access_expires_at__gt=timezone.now())).exists()
    if not eligible:
        return HttpResponseForbidden(bt("An active student access is required.", "Нужен активный учебный доступ."))
    form = ReviewForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        review = form.save(commit=False)
        review.user = request.user
        review.is_published = False
        review.save()
        messages.success(request, bt("Thank you. Your review has been saved for moderation.", "Спасибо! Отзыв сохранён и ожидает модерации."))
        return redirect("pages:reviews")
    return render(request, "review_form.html", {"form": form})
