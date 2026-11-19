from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm
from django.db import close_old_connections, connection
from django.test import Client, RequestFactory, TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone

from contacts.forms import ContactMessageForm
from contacts.models import ContactMessage
from contacts.views import send_contact_notification
from .admin import CourseRequestAdmin
from .forms import CourseRequestForm
from .models import Course, CourseEnrollment, CourseRequest, Lesson, LessonProgress
from .views import send_verification_email


class AuditRegressionTests(TestCase):
    def setUp(self):
        self.course = Course.objects.create(title="Test course", slug="audit-course")
        self.user = get_user_model().objects.create_user("audit-student", password="Before-934!")
        self.enrollment = CourseEnrollment.objects.create(
            course=self.course, user=self.user, student_name="Test student",
            access_expires_at=timezone.now() + timedelta(days=1),
            invitation_expires_at=timezone.now() + timedelta(days=1),
        )

    def test_consumed_token_cannot_reset_password_by_post(self):
        url = reverse("courses:activate", args=[self.enrollment.invitation_token])
        first = {"new_password1": "First-password-194!", "new_password2": "First-password-194!"}
        self.client.post(url, first)
        self.client.logout()
        self.client.post(url, {"new_password1": "Second-password-194!", "new_password2": "Second-password-194!"})
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(first["new_password1"]))

    def test_activation_rolls_back_password_and_token_together(self):
        url = reverse("courses:activate", args=[self.enrollment.invitation_token])
        with patch.object(CourseEnrollment, "save", side_effect=RuntimeError("local failure")):
            with self.assertRaises(RuntimeError):
                self.client.post(url, {"new_password1": "First-password-194!", "new_password2": "First-password-194!"})
        self.enrollment.refresh_from_db()
        self.user.refresh_from_db()
        self.assertIsNone(self.enrollment.invitation_used_at)
        self.assertTrue(self.user.check_password("Before-934!"))

    def test_legacy_activation_before_used_timestamp_field_is_also_consumed(self):
        self.enrollment.activated_at = timezone.now()
        self.enrollment.save()
        self.assertFalse(self.enrollment.can_activate_invitation)
        response = self.client.post(reverse("courses:activate", args=[self.enrollment.invitation_token]), {"new_password1": "Replay-password-194!", "new_password2": "Replay-password-194!"})
        self.assertRedirects(response, reverse("login"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Before-934!"))

    def test_unicode_names_in_all_remaining_contact_forms(self):
        for name in ["Élodie", "José", "Müller", "Елена", "José 李", "E\u0301lodie", "O’Connor"]:
            with self.subTest(name=name):
                contact = ContactMessageForm({"name": name, "email": "test@example.com", "phone": "+442079460958", "subject": "Consultation"})
                course = CourseRequestForm({"name": name, "messenger": "@test_student", "verification_channel": "messenger"})
                self.assertTrue(contact.is_valid(), contact.errors)
                self.assertTrue(course.is_valid(), course.errors)
        for name in ["<script>José</script>", "https://bad.test", "123", "A" * 121, "Élodie\nInjected"]:
            form = CourseRequestForm({"name": name, "messenger": "@test_student", "verification_channel": "messenger"})
            self.assertFalse(form.is_valid(), name)

    def test_legacy_messenger_only_request_visible_in_admin(self):
        entry = CourseRequest.objects.create(course=self.course, name="Legacy test", messenger="@legacy_student", verification_channel="messenger")
        staff = get_user_model().objects.create_superuser("local-admin", "admin@example.com", "Test-admin-194!")
        self.client.force_login(staff)
        response = self.client.get(reverse("admin:courses_courserequest_change", args=[entry.pk]))
        self.assertContains(response, "@legacy_student")

    def test_admin_preserves_messenger_when_issuing_and_updating_access(self):
        entry = CourseRequest.objects.create(course=self.course, name="Contact test", email="audit-student", messenger="@saved_contact", is_verified=True)
        manager = CourseRequestAdmin(CourseRequest, admin.site)
        request = RequestFactory().get("/admin/")
        with patch.object(manager, "message_user"), patch("courses.admin.send_mail", return_value=1):
            manager.create_student_accounts(request, CourseRequest.objects.filter(pk=entry.pk))
            self.enrollment.refresh_from_db()
            self.assertEqual(self.enrollment.messenger, "@saved_contact")
            entry.messenger = ""
            entry.save()
            manager.create_student_accounts(request, CourseRequest.objects.filter(pk=entry.pk))
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.messenger, "@saved_contact")

    @override_settings(CONTACT_NOTIFY_EMAIL="admin@example.com")
    def test_email_zero_and_exception_never_mark_success(self):
        entry = CourseRequest.objects.create(course=self.course, name="Mail test", email="audit-student", is_verified=True)
        contact = ContactMessage.objects.create(name="Mail test", message="Test")
        request = RequestFactory().get("/courses/")
        with patch("courses.views.send_mail", return_value=0):
            self.assertFalse(send_verification_email(request, entry))
        with patch("contacts.views.send_mail", return_value=0):
            self.assertFalse(send_contact_notification(contact))
        manager = CourseRequestAdmin(CourseRequest, admin.site)
        for outcome in [0, RuntimeError("offline")]:
            with patch.object(manager, "message_user"), patch("courses.admin.send_mail", **({"side_effect": outcome} if isinstance(outcome, Exception) else {"return_value": outcome})):
                manager.create_student_accounts(request, CourseRequest.objects.filter(pk=entry.pk))
            self.enrollment.refresh_from_db()
            self.assertIsNone(self.enrollment.invitation_sent_at)
        with patch("courses.views.send_mail", side_effect=RuntimeError("offline")):
            with self.assertRaises(RuntimeError):
                send_verification_email(request, entry)
        entry.refresh_from_db()
        self.assertIsNone(entry.verification_sent_at)
        self.assertTrue(CourseRequest.objects.filter(pk=entry.pk).exists())

    def test_access_matrix_read_and_write_including_hidden_course(self):
        lesson = Lesson.objects.create(course=self.course, title="Visible material", is_published=True)
        hidden = Lesson.objects.create(course=self.course, title="Hidden material", is_published=False)
        read_url = reverse("courses:student_course", args=[self.course.slug])
        write_url = reverse("courses:mark_lesson_complete", args=[self.course.slug, lesson.pk])
        self.assertEqual(self.client.get(read_url).status_code, 302)
        self.assertEqual(self.client.post(write_url, {"complete": "1"}).status_code, 302)
        stranger = get_user_model().objects.create_user("stranger")
        for actor, active, expiry in [(stranger, True, 1), (self.user, False, 1), (self.user, True, -1)]:
            self.client.force_login(actor)
            self.enrollment.is_active = active
            self.enrollment.access_expires_at = timezone.now() + timedelta(days=expiry)
            self.enrollment.save()
            self.assertRedirects(self.client.get(read_url), reverse("courses:my_courses"), fetch_redirect_response=False)
            self.assertRedirects(self.client.post(write_url, {"complete": "1"}), reverse("courses:my_courses"), fetch_redirect_response=False)
            self.assertFalse(LessonProgress.objects.filter(is_completed=True).exists())
        self.enrollment.is_active = True
        self.enrollment.access_expires_at = timezone.now() + timedelta(days=1)
        self.enrollment.save()
        self.course.is_active = False
        self.course.save()
        self.client.force_login(self.user)
        page = self.client.get(read_url)
        self.assertContains(page, "Visible material")
        self.assertNotContains(page, "Hidden material")
        self.client.post(write_url, {"complete": "1"})
        self.assertTrue(LessonProgress.objects.get(enrollment=self.enrollment, lesson=lesson).is_completed)
        hidden_url = reverse("courses:mark_lesson_complete", args=[self.course.slug, hidden.pk])
        self.assertEqual(self.client.post(hidden_url, {"complete": "1"}).status_code, 404)

    def test_expiry_boundary_is_closed(self):
        boundary = timezone.now()
        self.enrollment.access_expires_at = boundary
        self.enrollment.invitation_expires_at = boundary
        with patch("courses.models.timezone.now", return_value=boundary):
            self.assertFalse(self.enrollment.has_access)
            self.assertFalse(self.enrollment.can_activate_invitation)


class ConcurrentInvitationTests(TransactionTestCase):
    @skipUnlessDBFeature("has_select_for_update")
    def test_overlapping_posts_only_one_password_commits(self):
        student = get_user_model().objects.create_user("concurrent-student")
        course = Course.objects.create(title="Concurrent", slug="concurrent")
        enrollment = CourseEnrollment.objects.create(course=course, user=student)
        url = reverse("courses:activate", args=[enrollment.invitation_token])
        first_holds_lock = Event()
        second_attempts_lock = Event()
        original_save = SetPasswordForm.save

        def delayed_save(form, commit=True):
            first_holds_lock.set()
            self.assertTrue(second_attempts_lock.wait(10), "Second SQL request did not overlap")
            return original_save(form, commit=commit)

        def attempt(password, second=False):
            close_old_connections()
            try:
                if second:
                    self.assertTrue(first_holds_lock.wait(10))

                def observe(execute, sql, params, many, context):
                    if second and "FOR UPDATE" in sql:
                        second_attempts_lock.set()
                    return execute(sql, params, many, context)

                with connection.execute_wrapper(observe):
                    response = Client().post(url, {"new_password1": password, "new_password2": password})
                    return response.status_code, response.url
            finally:
                close_old_connections()

        with patch.object(SetPasswordForm, "save", delayed_save), ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(attempt, "First-concurrent-934!")
            second = pool.submit(attempt, "Second-concurrent-934!", True)
            results = [first.result(timeout=20), second.result(timeout=20)]
        student.refresh_from_db()
        enrollment.refresh_from_db()
        self.assertTrue(student.check_password("First-concurrent-934!"))
        self.assertFalse(student.check_password("Second-concurrent-934!"))
        self.assertIsNotNone(enrollment.invitation_used_at)
        self.assertEqual(results[1], (302, reverse("login")))
