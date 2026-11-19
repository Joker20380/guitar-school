from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Course, CourseEnrollment, Lesson, LessonProgress


class CourseAccessSecurityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="student@example.com",
            password="old-test-password",
        )
        self.course = Course.objects.create(
            title="Безопасный курс",
            slug="secure-course",
            short_description="Проверка доступа",
            description="Тестовый курс",
        )
        self.lesson = Lesson.objects.create(course=self.course, title="Урок")
        self.enrollment = CourseEnrollment.objects.create(
            course=self.course,
            user=self.user,
            student_name="Ученик",
            access_expires_at=timezone.now() - timedelta(minutes=1),
        )
        self.client.force_login(self.user)

    def test_expired_access_cannot_change_lesson_progress(self):
        response = self.client.post(
            reverse(
                "courses:mark_lesson_complete",
                kwargs={"slug": self.course.slug, "lesson_id": self.lesson.id},
            ),
            {"complete": "1"},
            follow=True,
        )

        self.assertRedirects(response, reverse("courses:my_courses"))
        self.assertContains(response, "Срок доступа к курсу истёк.")
        self.assertFalse(LessonProgress.objects.exists())

    def test_expired_access_cannot_open_or_request_teachers(self):
        page = self.client.get(
            reverse("courses:my_course_teachers", kwargs={"slug": self.course.slug}),
            follow=True,
        )
        request = self.client.post(
            reverse("courses:request_teacher", kwargs={"slug": self.course.slug}),
            {},
            follow=True,
        )

        self.assertRedirects(page, reverse("courses:my_courses"))
        self.assertRedirects(request, reverse("courses:my_courses"))
        self.assertContains(page, "Срок доступа к курсу истёк.")
        self.assertContains(request, "Срок доступа к курсу истёк.")

    def test_database_rejects_duplicate_user_course_access(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            CourseEnrollment.objects.create(
                course=self.course,
                user=self.user,
                student_name="Дубликат",
            )


class InvitationSecurityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="invited@example.com")
        self.user.set_unusable_password()
        self.user.save(update_fields=["password"])
        self.course = Course.objects.create(
            title="Курс по приглашению",
            slug="invited-course",
            short_description="Проверка приглашения",
            description="Тестовый курс",
        )

    def test_invitation_is_one_time(self):
        enrollment = CourseEnrollment.objects.create(
            course=self.course,
            user=self.user,
            student_name="Новый ученик",
            invitation_expires_at=timezone.now() + timedelta(days=1),
            access_expires_at=timezone.now() + timedelta(days=30),
        )
        url = reverse("courses:activate", kwargs={"token": enrollment.invitation_token})

        response = self.client.post(
            url,
            {"new_password1": "Strong-test-password-934!", "new_password2": "Strong-test-password-934!"},
            follow=True,
        )

        enrollment.refresh_from_db()
        self.user.refresh_from_db()
        self.assertIsNotNone(enrollment.invitation_used_at)
        self.assertTrue(self.user.check_password("Strong-test-password-934!"))
        self.assertContains(response, "Аккаунт активирован")

        second_response = self.client.get(url, follow=True)
        self.assertContains(second_response, "Приглашение уже использовано")

    def test_expired_invitation_cannot_set_password(self):
        enrollment = CourseEnrollment.objects.create(
            course=self.course,
            user=self.user,
            student_name="Новый ученик",
            invitation_expires_at=timezone.now() - timedelta(seconds=1),
            access_expires_at=timezone.now() + timedelta(days=30),
        )

        response = self.client.get(
            reverse("courses:activate", kwargs={"token": enrollment.invitation_token}),
            follow=True,
        )

        self.assertContains(response, "Срок действия приглашения истёк")
