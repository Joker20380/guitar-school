from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from courses.models import Course, CourseEnrollment, Lesson
from journal.models import Article
from .models import Review


class ContentWorkflowTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser("test-editor", "editor@example.com", "Editor-password-194!")
        self.student = get_user_model().objects.create_user("test-student", "student@example.com", "Student-password-194!")
        self.course = Course.objects.create(title="Existing course", slug="existing")
        self.enrollment = CourseEnrollment.objects.create(course=self.course, user=self.student)

    def test_article_admin_preserves_two_languages_in_one_entity_and_url(self):
        self.client.force_login(self.admin)
        payload = {"title": "Test music story", "title_ru": "Тестовая история", "slug": "test-story", "content": "English test content", "content_ru": "Русский тестовый текст", "excerpt": "English summary", "excerpt_ru": "Русское описание", "is_published": "on"}
        response = self.client.post(reverse("admin:journal_article_add"), payload)
        self.assertEqual(response.status_code, 302)
        article = Article.objects.get()
        for language, title, content in [("en", payload["title"], payload["content"]), ("ru", payload["title_ru"], payload["content_ru"])]:
            self.client.cookies["phoenix_songs_language"] = language
            response = self.client.get(article.get_absolute_url())
            self.assertContains(response, title)
            self.assertContains(response, content)
        payload["content_ru"] = "Обновлённый русский текст"
        self.client.post(reverse("admin:journal_article_change", args=[article.pk]), payload)
        article.refresh_from_db()
        self.assertEqual(article.content, "English test content")
        self.assertEqual(article.content_ru, payload["content_ru"])
        self.assertEqual(Article.objects.count(), 1)
        article.is_published = False
        article.save()
        self.assertEqual(self.client.get(article.get_absolute_url()).status_code, 404)

    def test_admin_manual_review_and_student_moderation(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("admin:pages_review_add"), {"name": "Synthetic reviewer", "text": "Test-only manually imported review.", "is_published": "on"})
        self.assertEqual(response.status_code, 302)
        manual = Review.objects.get()
        self.assertFalse(manual.photo)
        self.client.force_login(self.student)
        self.client.post(reverse("pages:submit_review"), {"name": "José", "text": "Test-only student review.", "is_published": "on", "user": self.admin.pk})
        review = Review.objects.get(user=self.student)
        self.assertFalse(review.is_published)
        home = self.client.get("/")
        self.assertContains(home, manual.text)
        self.assertNotContains(home, review.text)
        self.assertLess(home.content.index(b'id="community"'), home.content.index(b'id="reviews"'))
        self.assertLess(home.content.index(b'id="reviews"'), home.content.index(b'id="start"'))
        self.client.force_login(self.admin)
        self.client.post(reverse("admin:pages_review_changelist"), {"action": "publish", "_selected_action": [review.pk]})
        self.assertContains(self.client.get("/"), review.text)
        manual.refresh_from_db()
        self.assertTrue(manual.is_published)

    def test_no_reviews_means_no_empty_home_block_and_only_students_submit(self):
        self.assertNotContains(self.client.get("/"), 'id="reviews"')
        self.assertEqual(self.client.get(reverse("pages:submit_review")).status_code, 302)
        stranger = get_user_model().objects.create_user("no-enrollment")
        self.client.force_login(stranger)
        self.assertEqual(self.client.post(reverse("pages:submit_review"), {"name": "Test", "text": "Test"}).status_code, 403)
        self.client.force_login(self.student)
        self.enrollment.access_expires_at = timezone.now() - timedelta(seconds=1)
        self.enrollment.save()
        self.assertEqual(self.client.get(reverse("pages:submit_review")).status_code, 403)

    def test_course_with_lesson_created_through_admin(self):
        self.client.force_login(self.admin)
        payload = {
            "title": "Admin-created course", "slug": "admin-created", "short_description": "Test summary", "description": "Test description", "level": "beginner", "format": "online", "is_active": "on", "sort_order": 10,
            "materials-TOTAL_FORMS": 0, "materials-INITIAL_FORMS": 0,
            "lessons-TOTAL_FORMS": 1, "lessons-INITIAL_FORMS": 0,
            "lessons-0-title": "Test lesson", "lessons-0-content": "Lesson body", "lessons-0-video_url": "https://youtu.be/abcdef12345", "lessons-0-homework": "Practise a chord", "lessons-0-sort_order": 2, "lessons-0-is_published": "on",
        }
        response = self.client.post(reverse("admin:courses_course_add"), payload)
        self.assertEqual(response.status_code, 302, getattr(response, "context", None) and response.context["adminform"].form.errors)
        course = Course.objects.get(slug="admin-created")
        lesson = Lesson.objects.get(course=course)
        self.assertEqual(lesson.content, "Lesson body")
        self.assertEqual(lesson.homework, "Practise a chord")
        self.assertEqual(lesson.sort_order, 2)
        self.assertTrue(lesson.is_published)
        self.assertIn("youtube-nocookie.com", lesson.video_embed_url)
        self.assertFalse(course.is_advertised)

    def test_independent_password_reset_token_expires_and_cannot_be_replayed(self):
        token = default_token_generator.make_token(self.student)
        uid = urlsafe_base64_encode(force_bytes(self.student.pk))
        response = self.client.get(reverse("password_reset_confirm", args=[uid, token]))
        self.assertEqual(response.status_code, 302)
        response = self.client.post(response.url, {"new_password1": "Changed-password-591!", "new_password2": "Changed-password-591!"})
        self.assertRedirects(response, reverse("password_reset_complete"))
        self.student.refresh_from_db()
        self.assertFalse(default_token_generator.check_token(self.student, token))
        with self.settings(PASSWORD_RESET_TIMEOUT=-1):
            self.assertFalse(default_token_generator.check_token(self.student, default_token_generator.make_token(self.student)))

    def test_all_public_surfaces_use_correct_blog_label_and_a9(self):
        exact_a9 = "Your guide to music from around the world. Discover artists, explore musical cultures, learn fascinating facts, get useful musical tips and find inspiration!"
        for language, label in [("en", "music blog"), ("ru", "Наш блог")]:
            self.client.cookies["phoenix_songs_language"] = language
            for url in ["/", "/contacts/", "/contacts/trial/", "/journal/", "/reviews/", "/accounts/login/", "/tuner/"]:
                response = self.client.get(url)
                self.assertContains(response, label)
                self.assertGreaterEqual(response.content.count(label.encode()), 3)
                self.assertNotContains(response, "Music Journal")
                self.assertNotContains(response, "Музыкальный журнал")
                self.assertNotContains(response, 'href="/courses/teachers/"')
            if language == "en":
                self.assertContains(self.client.get("/journal/"), exact_a9)
