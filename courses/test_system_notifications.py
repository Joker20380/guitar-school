from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Course, CourseEnrollment


class SystemNotificationTests(TestCase):
    def setUp(self):
        self.client.cookies["phoenix_songs_language"] = "ru"
        self.user = get_user_model().objects.create_user(
            username="expired-student",
            password="test-password",
        )
        self.course = Course.objects.create(
            title="Курс с истёкшим доступом",
            slug="expired-course",
            short_description="Проверка уведомления",
            description="Тестовый курс",
        )
        CourseEnrollment.objects.create(
            course=self.course,
            user=self.user,
            student_name="Ученик",
            access_expires_at=timezone.now() - timedelta(minutes=1),
        )
        self.client.force_login(self.user)

    def test_expired_course_message_is_rendered_as_global_notification(self):
        response = self.client.get(
            reverse("courses:student_course", kwargs={"slug": self.course.slug}),
            follow=True,
        )

        self.assertRedirects(response, reverse("courses:my_courses"))
        self.assertContains(response, "system-notifications")
        self.assertContains(response, "system-notification error")
        self.assertContains(response, "Срок доступа к курсу истёк.")

    def test_rendered_message_is_consumed_and_not_batched_later(self):
        self.client.get(
            reverse("courses:student_course", kwargs={"slug": self.course.slug}),
            follow=True,
        )

        response = self.client.get(reverse("pages:home"))

        self.assertNotContains(response, "Срок доступа к курсу истёк.")
