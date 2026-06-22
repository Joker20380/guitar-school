import secrets
import re
from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from phonenumber_field.modelfields import PhoneNumberField


def generate_access_token():
    return secrets.token_urlsafe(32)


class Course(models.Model):
    LEVEL_BEGINNER = "beginner"
    LEVEL_INTERMEDIATE = "intermediate"
    LEVEL_ADVANCED = "advanced"

    LEVEL_CHOICES = [
        (LEVEL_BEGINNER, "Новичок"),
        (LEVEL_INTERMEDIATE, "Средний уровень"),
        (LEVEL_ADVANCED, "Продвинутый уровень"),
    ]

    FORMAT_ONLINE = "online"
    FORMAT_OFFLINE = "offline"
    FORMAT_HYBRID = "hybrid"

    FORMAT_CHOICES = [
        (FORMAT_ONLINE, "Онлайн"),
        (FORMAT_OFFLINE, "Офлайн"),
        (FORMAT_HYBRID, "Онлайн + офлайн"),
    ]

    title = models.CharField("Название курса", max_length=180)
    slug = models.SlugField("URL-адрес", max_length=200, unique=True)
    short_description = models.CharField("Краткое описание", max_length=260)
    description = models.TextField("Полное описание")

    level = models.CharField("Уровень", max_length=32, choices=LEVEL_CHOICES, default=LEVEL_BEGINNER)
    format = models.CharField("Формат", max_length=32, choices=FORMAT_CHOICES, default=FORMAT_OFFLINE)

    duration = models.CharField("Длительность", max_length=120, blank=True)
    price = models.CharField("Цена", max_length=120, blank=True)
    cover_image = models.CharField("Изображение / фон", max_length=500, blank=True)

    is_active = models.BooleanField("Показывать на сайте", default=True)
    sort_order = models.PositiveIntegerField("Порядок", default=100)

    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "Курс"
        verbose_name_plural = "Курсы"
        ordering = ["sort_order", "title"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("courses:detail", kwargs={"slug": self.slug})


class Lesson(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="lessons",
        verbose_name="Курс",
    )
    title = models.CharField("Название урока", max_length=180)
    short_description = models.CharField("Краткое описание", max_length=260, blank=True)
    content = models.TextField("Материалы урока", blank=True)

    video_url = models.URLField("Ссылка на видео", blank=True)
    online_meeting_url = models.URLField("Ссылка на онлайн-урок", blank=True)
    homework = models.TextField("Домашнее задание", blank=True)

    is_published = models.BooleanField("Показывать", default=True)
    sort_order = models.PositiveIntegerField("Порядок", default=100)

    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Урок"
        verbose_name_plural = "Уроки"
        ordering = ["sort_order", "id"]

    @property
    def video_embed_url(self):
        """
        Возвращает безопасную embed-ссылку только для поддерживаемых видеоплатформ.
        Сырой iframe из админки не принимаем.
        """
        raw_url = (self.video_url or "").strip()

        if not raw_url:
            return ""

        parsed = urlparse(raw_url)
        host = parsed.netloc.lower().replace("www.", "").replace("m.", "")
        path = parsed.path.strip("/")

        video_id = ""

        if host in {"youtube.com", "youtube-nocookie.com"}:
            if path == "watch":
                video_id = parse_qs(parsed.query).get("v", [""])[0]
            elif path.startswith("embed/"):
                video_id = path.split("/", 1)[1].split("/")[0]
            elif path.startswith("shorts/"):
                video_id = path.split("/", 1)[1].split("/")[0]

            if video_id and re.match(r"^[A-Za-z0-9_-]{6,64}$", video_id):
                return f"https://www.youtube-nocookie.com/embed/{video_id}?rel=0&modestbranding=1"

        if host == "youtu.be":
            video_id = path.split("/")[0]

            if video_id and re.match(r"^[A-Za-z0-9_-]{6,64}$", video_id):
                return f"https://www.youtube-nocookie.com/embed/{video_id}?rel=0&modestbranding=1"

        if host == "vimeo.com":
            video_id = path.split("/")[0]

            if video_id and video_id.isdigit():
                return f"https://player.vimeo.com/video/{video_id}"

        if host == "player.vimeo.com" and path.startswith("video/"):
            video_id = path.split("/", 1)[1].split("/")[0]

            if video_id and video_id.isdigit():
                return f"https://player.vimeo.com/video/{video_id}"

        return ""

    def __str__(self):
        return f"{self.course.title} — {self.title}"


class CourseRequest(models.Model):
    STATUS_NEW = "new"
    STATUS_CONTACTED = "contacted"
    STATUS_ENROLLED = "enrolled"
    STATUS_REJECTED = "rejected"

    STATUS_CHOICES = [
        (STATUS_NEW, "Новая"),
        (STATUS_CONTACTED, "Связались"),
        (STATUS_ENROLLED, "Записан"),
        (STATUS_REJECTED, "Отклонена"),
    ]

    VERIFY_EMAIL = "email"
    VERIFY_PHONE = "phone"
    VERIFY_MESSENGER = "messenger"

    VERIFY_CHOICES = [
        (VERIFY_EMAIL, "Email"),
        (VERIFY_PHONE, "Телефон"),
        (VERIFY_MESSENGER, "Мессенджер"),
    ]

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="requests",
        verbose_name="Курс",
    )
    name = models.CharField("Имя", max_length=120)
    phone = PhoneNumberField("Телефон", region="BE", blank=True)
    messenger = models.CharField("Мессенджер", max_length=80, blank=True)
    email = models.EmailField("Email", blank=True)

    verification_channel = models.CharField(
        "Способ подтверждения",
        max_length=32,
        choices=VERIFY_CHOICES,
        default=VERIFY_EMAIL,
    )
    is_verified = models.BooleanField("Подтверждена", default=False)
    verified_at = models.DateTimeField("Дата подтверждения", null=True, blank=True)
    verification_sent_at = models.DateTimeField("Подтверждение отправлено", null=True, blank=True)

    ip_address = models.GenericIPAddressField("IP-адрес", null=True, blank=True)
    user_agent = models.CharField("User-Agent", max_length=300, blank=True)

    preferred_format = models.CharField(
        "Предпочтительный формат",
        max_length=32,
        choices=Course.FORMAT_CHOICES,
        blank=True,
    )
    message = models.TextField("Комментарий", blank=True)

    status = models.CharField("Статус", max_length=32, choices=STATUS_CHOICES, default=STATUS_NEW)
    created_at = models.DateTimeField("Дата заявки", auto_now_add=True)

    class Meta:
        verbose_name = "Заявка на курс"
        verbose_name_plural = "Заявки на курсы"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} — {self.course.title}"


class CourseEnrollment(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="enrollments",
        verbose_name="Курс",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="course_enrollments",
        verbose_name="Ученик",
        null=True,
        blank=True,
    )
    course_request = models.OneToOneField(
        CourseRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="enrollment",
        verbose_name="Заявка",
    )

    student_name = models.CharField("Имя ученика", max_length=120)
    email = models.EmailField("Email", blank=True)
    phone = PhoneNumberField("Телефон", region="BE", blank=True)
    messenger = models.CharField("Мессенджер", max_length=80, blank=True)

    access_token = models.CharField(
        "Старый токен доступа",
        max_length=96,
        db_index=True,
        default=generate_access_token,
        editable=False,
    )
    invitation_token = models.CharField(
        "Токен активации",
        max_length=96,
        db_index=True,
        default=generate_access_token,
        editable=False,
    )

    is_active = models.BooleanField("Доступ активен", default=True)
    access_expires_at = models.DateTimeField("Доступ до", null=True, blank=True)

    invitation_sent_at = models.DateTimeField("Приглашение отправлено", null=True, blank=True)
    activated_at = models.DateTimeField("Аккаунт активирован", null=True, blank=True)
    last_access_at = models.DateTimeField("Последний вход", null=True, blank=True)

    notes = models.TextField("Заметки преподавателя", blank=True)

    created_at = models.DateTimeField("Дата выдачи доступа", auto_now_add=True)

    class Meta:
        verbose_name = "Доступ к курсу"
        verbose_name_plural = "Доступы к курсам"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student_name} — {self.course.title}"

    @property
    def is_expired(self):
        return bool(self.access_expires_at and self.access_expires_at < timezone.now())

    @property
    def has_access(self):
        return self.is_active and not self.is_expired

    def progress_percent(self):
        total = self.course.lessons.filter(is_published=True).count()

        if not total:
            return 0

        completed = self.lesson_progress.filter(is_completed=True).count()
        return round(completed / total * 100)


class LessonProgress(models.Model):
    enrollment = models.ForeignKey(
        CourseEnrollment,
        on_delete=models.CASCADE,
        related_name="lesson_progress",
        verbose_name="Доступ к курсу",
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name="student_progress",
        verbose_name="Урок",
    )

    is_completed = models.BooleanField("Завершён", default=False)
    completed_at = models.DateTimeField("Дата завершения", null=True, blank=True)
    student_note = models.TextField("Заметка ученика", blank=True)

    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "Прогресс урока"
        verbose_name_plural = "Прогресс уроков"
        unique_together = ("enrollment", "lesson")
        ordering = ["lesson__sort_order", "lesson__id"]

    def __str__(self):
        return f"{self.enrollment.student_name} — {self.lesson.title}"
