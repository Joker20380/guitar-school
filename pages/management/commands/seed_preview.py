import json
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from courses.models import Course, CourseEnrollment, Lesson
from journal.models import Article


class Command(BaseCommand):
    help = "Create synthetic preview data only in config.preview_settings."

    def handle(self, *args, **options):
        if settings.SETTINGS_MODULE != "config.preview_settings":
            raise CommandError("This command only accepts config.preview_settings.")
        credentials_path = settings.BASE_DIR / ".preview" / "access.json"
        credentials_path.parent.mkdir(mode=0o700, exist_ok=True)
        credentials = json.loads(credentials_path.read_text()) if credentials_path.exists() else {"password": secrets.token_urlsafe(24)}
        for username, staff in [("preview-admin", True), ("preview-student", False)]:
            user, created = get_user_model().objects.get_or_create(username=username, defaults={"email": f"{username}@example.com", "first_name": "Preview", "is_staff": staff, "is_superuser": staff})
            if created:
                user.set_password(credentials["password"])
                user.save()
        credentials.update({"admin": "preview-admin", "student": "preview-student"})
        credentials_path.write_text(json.dumps(credentials))
        credentials_path.chmod(0o600)
        course, unused = Course.objects.get_or_create(slug="preview-guitar", defaults={"title": "Preview course / Тестовый курс", "description": "Synthetic course for local checks only.", "short_description": "Test data — not a public offer.", "format": "online", "is_advertised": False})
        Lesson.objects.get_or_create(course=course, title="First chord / Первый аккорд", defaults={"content": "Test learning material. Listen to each string before playing a chord.", "homework": "Test homework: practise a chord slowly.", "is_published": True, "sort_order": 1})
        Lesson.objects.get_or_create(course=course, title="Hidden draft / Скрытый черновик", defaults={"content": "Not visible to students.", "is_published": False, "sort_order": 2})
        CourseEnrollment.objects.get_or_create(course=course, user=get_user_model().objects.get(username="preview-student"), defaults={"student_name": "Preview Student", "access_expires_at": timezone.now() + timedelta(days=30), "activated_at": timezone.now(), "invitation_used_at": timezone.now()})
        Article.objects.get_or_create(slug="preview-first-chord", defaults={"title": "Preview article: listen before you play", "title_ru": "Тестовая статья: сначала слушай", "excerpt": "Synthetic content to check the bilingual editor and layout.", "excerpt_ru": "Тестовый материал для проверки редактора и вёрстки.", "content": "This is a local preview article, not an imported school publication.\n\nListen to each string. Leave room between sounds. A simple chord can become the beginning of your own song.", "content_ru": "Это локальная тестовая статья, а не перенесённая публикация школы.\n\nПослушай каждую струну. Оставь место между звуками. Простой аккорд может стать началом собственной песни.", "is_published": True, "published_at": timezone.now()})
        self.stdout.write("Synthetic preview data ready. Local credentials: .preview/access.json (not tracked). No reviews fabricated.")
