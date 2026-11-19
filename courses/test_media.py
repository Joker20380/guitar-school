import io
import tempfile
from datetime import timedelta
from pathlib import Path

from PIL import Image
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.forms import modelform_factory
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone, translation

from .models import Course, CourseEnrollment, CourseMaterial, Lesson, LessonMaterial, Teacher


def upload(name="notes.pdf", data=b"%PDF-1.4 test document"):
    return SimpleUploadedFile(name, data)


def photo():
    output = io.BytesIO()
    Image.new("RGB", (16, 16), color="blue").save(output, "PNG")
    return upload("photo.png", output.getvalue())


class MediaTests(TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.paths = Path(temp.name)
        settings = override_settings(MEDIA_ROOT=self.paths / "public", PRIVATE_MEDIA_ROOT=self.paths / "private")
        settings.enable()
        self.addCleanup(settings.disable)
        U = get_user_model()
        self.student = U.objects.create_user(username="student")
        self.other = U.objects.create_user(username="other")
        self.admin = U.objects.create_superuser(username="admin", email="", password="test")
        self.course = Course.objects.create(title="Course", slug="test-course", short_description="Short", description="Description")
        self.lesson = Lesson.objects.create(course=self.course, title="Lesson", video_file=upload("lesson.mp4", b"0123456789"))
        self.enrollment = CourseEnrollment.objects.create(course=self.course, user=self.student, student_name="Student", access_expires_at=timezone.now() + timedelta(days=1))
        self.material = LessonMaterial.objects.create(lesson=self.lesson, title="Private notes", file=upload())
        self.course_material = CourseMaterial.objects.create(course=self.course, title="Course handbook", file=upload("handbook.pdf"))

    def body(self, response):
        return b"".join(response.streaming_content) if response.streaming else response.content

    def test_files_are_stored_outside_public_media_and_download_with_original_name(self):
        self.assertTrue(Path(self.material.file.path).is_relative_to(self.paths / "private"))
        self.assertNotIn("/media/", self.material.file.url)
        self.client.force_login(self.student)
        for item in (self.material, self.course_material):
            response = self.client.get(item.file.url)
            self.assertEqual(response.status_code, 200)
            self.assertIn("attachment;", response["Content-Disposition"])
            self.assertIn(Path(item.file.name).name, response["Content-Disposition"])
            self.assertIn("no-store", response["Cache-Control"])
            self.assertEqual(response["X-Content-Type-Options"], "nosniff")
            self.assertEqual(self.body(response), b"%PDF-1.4 test document")

    def test_anonymous_and_unenrolled_cannot_download(self):
        for url in (self.material.file.url, self.course_material.file.url, self.lesson.video_file.url):
            self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.other)
        for url in (self.material.file.url, self.course_material.file.url, self.lesson.video_file.url):
            self.assertEqual(self.client.get(url).status_code, 404)

    def test_revoked_and_expired_access_denied_even_with_range(self):
        self.client.force_login(self.student)
        for active, expires in ((False, None), (True, timezone.now() - timedelta(seconds=1))):
            self.enrollment.is_active, self.enrollment.access_expires_at = active, expires
            self.enrollment.save()
            for url in (self.material.file.url, self.course_material.file.url, self.lesson.video_file.url):
                self.assertEqual(self.client.get(url, HTTP_RANGE="bytes=0-2").status_code, 404)

    def test_hidden_material_and_hidden_lesson_denied(self):
        self.client.force_login(self.student)
        self.material.is_published = False
        self.material.save()
        self.course_material.is_published = False
        self.course_material.save()
        self.assertEqual(self.client.get(self.material.file.url).status_code, 404)
        self.assertEqual(self.client.get(self.course_material.file.url).status_code, 404)
        self.material.is_published = True
        self.material.save()
        self.lesson.is_published = False
        self.lesson.save()
        self.assertEqual(self.client.get(self.material.file.url).status_code, 404)
        self.assertEqual(self.client.get(self.lesson.video_file.url).status_code, 404)

    def test_hidden_catalog_course_retains_existing_student_access(self):
        self.course.is_active = False
        self.course.save()
        self.client.force_login(self.student)
        response = self.client.get(self.material.file.url)
        self.assertEqual(response.status_code, 200)
        self.body(response)

    def test_admin_can_preview_draft_but_staff_without_permission_cannot(self):
        self.material.is_published = False
        self.material.save()
        self.client.force_login(self.admin)
        response = self.client.get(self.material.file.url)
        self.assertEqual(response.status_code, 200)
        self.body(response)
        self.other.is_staff = True
        self.other.save()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.material.file.url).status_code, 404)
        self.other.user_permissions.add(Permission.objects.get(codename="view_lessonmaterial"))
        response = self.client.get(self.material.file.url)
        self.assertEqual(response.status_code, 200)
        self.body(response)
        self.assertEqual(self.client.get(self.course_material.file.url).status_code, 404)

    def test_video_supports_range_suffix_open_end_and_head(self):
        self.client.force_login(self.student)
        for value, body, content_range in (
            ("bytes=2-5", b"2345", "bytes 2-5/10"),
            ("bytes=-3", b"789", "bytes 7-9/10"),
            ("bytes=8-", b"89", "bytes 8-9/10"),
            ("bytes=7-99", b"789", "bytes 7-9/10"),
        ):
            response = self.client.get(self.lesson.video_file.url, HTTP_RANGE=value)
            self.assertEqual(response.status_code, 206)
            self.assertEqual(response["Content-Range"], content_range)
            self.assertEqual(response["Content-Type"], "video/mp4")
            self.assertEqual(int(response["Content-Length"]), len(body))
            self.assertEqual(self.body(response), body)
        response = self.client.head(self.lesson.video_file.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Length"], "10")
        self.assertEqual(self.body(response), b"")

    def test_invalid_ranges_return_416(self):
        self.client.force_login(self.student)
        for value in ("bytes=99-", "bytes=-0", "bytes=5-2", "bytes=", "bytes=0-1,3-4", "bytes=-"):
            response = self.client.get(self.lesson.video_file.url, HTTP_RANGE=value)
            self.assertEqual(response.status_code, 416, value)
            self.assertEqual(response["Content-Range"], "bytes */10")

    def test_missing_deleted_or_unregistered_file_is_404(self):
        self.client.force_login(self.student)
        url = self.material.file.url
        self.material.file.storage.delete(self.material.file.name)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(reverse("courses:private_file", kwargs={"name": "../config/settings.py"})).status_code, 404)
        url = self.course_material.file.url
        self.course_material.delete()
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_material_requires_exactly_one_source_and_safe_url(self):
        for kwargs in ({}, {"file": upload(), "external_url": "https://example.com/file"}, {"external_url": "javascript:alert(1)"}, {"external_url": "ftp://example.com/file"}):
            with self.subTest(kwargs=tuple(kwargs)):
                with self.assertRaises(ValidationError):
                    CourseMaterial(course=self.course, title="Resource", **kwargs).full_clean()
        CourseMaterial(course=self.course, title="Link", external_url="https://example.com/folder?q=notes").full_clean()

    def test_large_files_and_executable_extensions_are_rejected(self):
        oversized = upload()
        oversized.size = 15 * 1024 * 1024 + 1
        for file in (oversized, upload("notes.html"), upload("notes.svg"), upload("notes.exe")):
            with self.assertRaises(ValidationError):
                LessonMaterial(lesson=self.lesson, title="Invalid", file=file).full_clean()

    def test_image_form_validates_real_image_size_and_public_storage(self):
        Form = modelform_factory(Teacher, fields=("full_name", "slug", "short_bio", "photo_file", "photo_url"))
        data = {"full_name": "Teacher", "slug": "teacher", "short_bio": "Teacher bio", "photo_url": "https://example.com/fallback.jpg"}
        form = Form(data, {"photo_file": photo()})
        self.assertTrue(form.is_valid(), form.errors)
        teacher = form.save()
        self.assertTrue(teacher.image_url.startswith("/media/images/"))
        self.assertTrue(Path(teacher.photo_file.path).is_relative_to(self.paths / "public"))
        invalid = Form({**data, "slug": "invalid"}, {"photo_file": upload("fake.png", b"<script>alert(1)</script>")})
        self.assertFalse(invalid.is_valid())
        oversized = photo()
        oversized.size = 5 * 1024 * 1024 + 1
        self.assertFalse(Form({**data, "slug": "large"}, {"photo_file": oversized}).is_valid())
        self.assertFalse(Form({**data, "slug": "bad-url", "photo_url": "javascript:alert(1)"}).is_valid())

    def test_clearing_image_restores_external_link(self):
        Form = modelform_factory(Course, fields=("cover_file", "cover_image"))
        self.course.cover_file = photo()
        self.course.cover_image = "https://example.com/cover.jpg"
        self.course.save()
        self.assertNotEqual(self.course.cover_url, self.course.cover_image)
        form = Form({"cover_file-clear": "on", "cover_image": self.course.cover_image}, instance=self.course)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().cover_url, "https://example.com/cover.jpg")

    def test_student_resources_are_rendered_in_both_languages_and_public_pages_hide_them(self):
        CourseMaterial.objects.create(course=self.course, title="External folder", external_url="https://example.com/folder")
        CourseMaterial.objects.create(course=self.course, title="Hidden resource", external_url="https://example.com/hidden", is_published=False)
        LessonMaterial.objects.create(lesson=self.lesson, title="Hidden lesson resource", external_url="https://example.com/hidden-lesson", is_published=False)
        self.course.cover_image = "https://example.com/cover.jpg"
        self.course.save()
        self.lesson.content = "https://example.com/notes\n<script>alert(1)</script>"
        self.lesson.video_url = "https://youtu.be/abcdefghijk"
        self.lesson.save()
        for lang in ("en", "ru"):
            self.client.cookies["phoenix_songs_language"] = lang
            public = self.client.get(self.course.get_absolute_url())
            self.assertContains(public, self.course.cover_url)
            self.assertNotContains(public, "Private notes")
            self.assertNotContains(public, "External folder")
            self.assertNotContains(public, self.lesson.video_file.url)
            self.client.force_login(self.student)
            response = self.client.get(reverse("courses:student_course", kwargs={"slug": self.course.slug}))
            self.assertContains(response, "Private notes")
            self.assertContains(response, "Course handbook")
            self.assertContains(response, "External folder")
            self.assertContains(response, 'href="https://example.com/notes"')
            self.assertContains(response, "&lt;script&gt;")
            self.assertContains(response, '<video class="lesson-uploaded-video"')
            self.assertNotContains(response, "youtube-nocookie.com/embed/abcdefghijk")
            self.assertNotContains(response, "Hidden resource")
            self.assertNotContains(response, "Hidden lesson resource")
            self.client.logout()

    def test_admin_can_upload_and_replace_lesson_material(self):
        self.client.force_login(self.admin)
        url = reverse("admin:courses_lessonmaterial_add")
        response = self.client.post(url, {"lesson": self.lesson.pk, "title": "Admin upload", "file": upload("admin.pdf"), "sort_order": 10, "is_published": "on", "_save": "Save"})
        self.assertEqual(response.status_code, 302)
        material = LessonMaterial.objects.get(title="Admin upload")
        old_url = material.file.url
        response = self.client.post(reverse("admin:courses_lessonmaterial_change", args=[material.pk]), {"lesson": self.lesson.pk, "title": material.title, "file-clear": "on", "external_url": "https://example.com/replacement", "sort_order": 10, "is_published": "on", "_save": "Save"})
        self.assertEqual(response.status_code, 302)
        material.refresh_from_db()
        self.assertFalse(material.file)
        self.assertEqual(material.resource_url, "https://example.com/replacement")
        self.assertEqual(self.client.get(old_url).status_code, 404)

    def test_admin_inline_course_upload_and_forms(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("admin:courses_course_add"), {
            "title": "Inline course", "slug": "inline-course", "short_description": "Short", "description": "Description",
            "level": "beginner", "format": "online", "sort_order": 10, "cover_file": photo(),
            "materials-TOTAL_FORMS": 1, "materials-INITIAL_FORMS": 0,
            "materials-MIN_NUM_FORMS": 0, "materials-MAX_NUM_FORMS": 1000,
            "materials-0-title": "Inline notes", "materials-0-file": upload("inline.pdf"),
            "materials-0-sort_order": 10, "materials-0-is_published": "on",
            "lessons-TOTAL_FORMS": 0, "lessons-INITIAL_FORMS": 0,
            "lessons-MIN_NUM_FORMS": 0, "lessons-MAX_NUM_FORMS": 1000,
            "_save": "Save",
        })
        self.assertEqual(response.status_code, 302)
        course = Course.objects.get(slug="inline-course")
        self.assertTrue(course.cover_file)
        self.assertTrue(course.materials.get().file)
        for model in ("course", "lesson", "teacher", "coursematerial", "lessonmaterial"):
            response = self.client.get(reverse(f"admin:courses_{model}_add"))
            self.assertContains(response, 'enctype="multipart/form-data"')
            self.assertContains(response, 'type="file"')
            self.assertContains(response, reverse("admin_guide"))

    def test_help_is_only_available_to_staff(self):
        self.assertEqual(self.client.get(reverse("admin_guide")).status_code, 302)
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("admin_guide")).status_code, 302)
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin_guide"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("Инструкция".encode(), self.body(response))
