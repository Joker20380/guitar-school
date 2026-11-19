import secrets
import re
from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.db import models

from config.i18n import bilingual as bt
from django.urls import reverse
from django.utils import timezone
from phonenumber_field.modelfields import PhoneNumberField
from django.core.exceptions import ValidationError

from .media import (
    private_storage, private_material_path, public_image_path,
    validate_image_extension, validate_image_size, validate_material_extension,
    validate_material_size, validate_resource_url, validate_video_extension,
)


def generate_access_token():
    return secrets.token_urlsafe(32)


class Course(models.Model):
    LEVEL_BEGINNER = "beginner"
    LEVEL_INTERMEDIATE = "intermediate"
    LEVEL_ADVANCED = "advanced"

    LEVEL_CHOICES = [
        (LEVEL_BEGINNER, bt("Beginner", "Новичок")),
        (LEVEL_INTERMEDIATE, bt("Intermediate", "Средний уровень")),
        (LEVEL_ADVANCED, bt("Advanced", "Продвинутый уровень")),
    ]

    FORMAT_ONLINE = "online"
    FORMAT_OFFLINE = "offline"
    FORMAT_HYBRID = "hybrid"

    FORMAT_CHOICES = [
        (FORMAT_ONLINE, bt("Online", "Онлайн")),
        (FORMAT_OFFLINE, bt("In person", "Очно")),
        (FORMAT_HYBRID, bt("Hybrid", "Смешанный формат")),
    ]

    title = models.CharField("Название курса", max_length=180)
    slug = models.SlugField("URL-адрес", max_length=200, unique=True)
    short_description = models.CharField("Краткое описание", max_length=260)
    description = models.TextField("Полное описание")

    level = models.CharField("Уровень", max_length=32, choices=LEVEL_CHOICES, default=LEVEL_BEGINNER)
    format = models.CharField("Формат", max_length=32, choices=FORMAT_CHOICES, default=FORMAT_OFFLINE)

    duration = models.CharField("Длительность", max_length=120, blank=True)
    price = models.CharField("Цена", max_length=120, blank=True)
    cover_image = models.URLField(
        "Ссылка на обложку", max_length=500, blank=True, validators=[validate_resource_url],
        help_text="Прямая ссылка https://… на изображение. Используется, если обложка не загружена файлом.",
    )
    cover_file = models.ImageField(
        "Загрузить обложку", upload_to=public_image_path, blank=True,
        validators=[validate_image_extension, validate_image_size],
        help_text="JPG, PNG или WebP, до 5 МБ. Загруженный файл используется вместо ссылки.",
    )

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

    @property
    def cover_url(self):
        return self.cover_file.url if self.cover_file else self.cover_image


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

    video_url = models.URLField("Ссылка на видео", max_length=1000, blank=True, validators=[validate_resource_url])
    video_file = models.FileField(
        "Загрузить видео", upload_to=private_material_path, storage=private_storage,
        max_length=255, blank=True,
        validators=[validate_video_extension, validate_material_size],
        help_text="MP4 или WebM, до 15 МБ. Для больших видео используйте ссылку. Файл имеет приоритет над ссылкой.",
    )
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
    invitation_expires_at = models.DateTimeField("Приглашение действительно до", null=True, blank=True)
    invitation_used_at = models.DateTimeField("Приглашение использовано", null=True, blank=True)
    activated_at = models.DateTimeField("Аккаунт активирован", null=True, blank=True)
    last_access_at = models.DateTimeField("Последний вход", null=True, blank=True)

    notes = models.TextField("Заметки преподавателя", blank=True)

    created_at = models.DateTimeField("Дата выдачи доступа", auto_now_add=True)

    class Meta:
        verbose_name = "Доступ к курсу"
        verbose_name_plural = "Доступы к курсам"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=("user", "course"),
                condition=models.Q(user__isnull=False),
                name="unique_user_course_enrollment",
            ),
        ]

    def __str__(self):
        return f"{self.student_name} — {self.course.title}"

    @property
    def is_expired(self):
        return bool(self.access_expires_at and self.access_expires_at <= timezone.now())

    @property
    def has_access(self):
        return self.is_active and not self.is_expired

    @property
    def invitation_is_expired(self):
        return bool(self.invitation_expires_at and self.invitation_expires_at <= timezone.now())

    @property
    def can_activate_invitation(self):
        return self.has_access and not self.invitation_used_at and not self.invitation_is_expired

    def progress_percent(self):
        total = self.course.lessons.filter(is_published=True).count()

        if not total:
            return 0

        completed = self.lesson_progress.filter(is_completed=True, lesson__is_published=True).count()
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


class TeacherSkill(models.Model):
    name = models.CharField("Навык", max_length=120, unique=True)
    slug = models.SlugField("URL-адрес", max_length=140, unique=True)
    sort_order = models.PositiveIntegerField("Порядок", default=100)

    class Meta:
        verbose_name = "Навык преподавателя"
        verbose_name_plural = "Навыки преподавателей"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class Teacher(models.Model):
    LEVEL_BEGINNER = "beginner"
    LEVEL_INTERMEDIATE = "intermediate"
    LEVEL_ADVANCED = "advanced"
    LEVEL_PRO = "pro"

    LEVEL_CHOICES = [
        (LEVEL_BEGINNER, bt("Beginners", "Новички")),
        (LEVEL_INTERMEDIATE, bt("Intermediate", "Средний уровень")),
        (LEVEL_ADVANCED, bt("Advanced", "Продвинутый уровень")),
        (LEVEL_PRO, bt("Professional", "Профессиональный уровень")),
    ]

    FORMAT_ONLINE = "online"
    FORMAT_OFFLINE = "offline"
    FORMAT_HYBRID = "hybrid"

    FORMAT_CHOICES = [
        (FORMAT_ONLINE, bt("Online", "Онлайн")),
        (FORMAT_OFFLINE, bt("In person", "Очно")),
        (FORMAT_HYBRID, bt("Hybrid", "Смешанный формат")),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teacher_profile",
        verbose_name="Аккаунт пользователя",
    )
    full_name = models.CharField("Имя преподавателя", max_length=160)
    slug = models.SlugField("URL-адрес", max_length=180, unique=True)
    photo_url = models.URLField(
        "Фото / ссылка на изображение", max_length=500, blank=True, validators=[validate_resource_url],
        help_text="Прямая ссылка https://… на изображение. Используется, если фото не загружено файлом.",
    )
    photo_file = models.ImageField(
        "Загрузить фото", upload_to=public_image_path, blank=True,
        validators=[validate_image_extension, validate_image_size],
        help_text="JPG, PNG или WebP, до 5 МБ. Загруженный файл используется вместо ссылки.",
    )

    short_bio = models.CharField("Краткое описание", max_length=260)
    bio = models.TextField("Биография / описание", blank=True)

    skills = models.ManyToManyField(
        TeacherSkill,
        blank=True,
        related_name="teachers",
        verbose_name="Навыки",
    )

    teaching_level = models.CharField(
        "Уровень преподавания",
        max_length=32,
        choices=LEVEL_CHOICES,
        default=LEVEL_BEGINNER,
    )
    lesson_format = models.CharField(
        "Формат занятий",
        max_length=32,
        choices=FORMAT_CHOICES,
        default=FORMAT_HYBRID,
    )

    experience_years = models.PositiveIntegerField("Опыт, лет", default=0)
    sort_order = models.PositiveIntegerField("Порядок", default=100)
    is_active = models.BooleanField("Показывать на сайте", default=True)

    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "Преподаватель"
        verbose_name_plural = "Преподаватели"
        ordering = ["sort_order", "full_name"]

    def __str__(self):
        return self.full_name

    def get_absolute_url(self):
        return reverse("courses:teacher_detail", kwargs={"slug": self.slug})

    @property
    def image_url(self):
        return self.photo_file.url if self.photo_file else self.photo_url


class MaterialBase(models.Model):
    title = models.CharField("Название материала", max_length=180)
    file = models.FileField(
        "Загрузить файл", upload_to=private_material_path, storage=private_storage,
        max_length=255, blank=True,
        validators=[validate_material_extension, validate_material_size],
        help_text="До 15 МБ: документы, ноты, табулатуры, изображения, аудио, видео или ZIP. Заполните файл или ссылку.",
    )
    external_url = models.URLField(
        "Ссылка на ресурс", max_length=1000, blank=True, validators=[validate_resource_url],
        help_text="Полная ссылка https://… на файл, папку или страницу. Доступ на внешнем сервисе настройте отдельно.",
    )
    sort_order = models.PositiveIntegerField("Порядок", default=100)
    is_published = models.BooleanField("Показывать ученикам", default=True)

    class Meta:
        abstract = True
        ordering = ["sort_order", "id"]

    def clean(self):
        super().clean()
        if bool(self.file) == bool(self.external_url):
            raise ValidationError("Укажите что-то одно: загруженный файл или ссылку на ресурс.")

    @property
    def resource_url(self):
        return self.file.url if self.file else self.external_url

    def __str__(self):
        return self.title


class CourseMaterial(MaterialBase):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="materials", verbose_name="Курс")

    class Meta(MaterialBase.Meta):
        verbose_name = "Материал курса"
        verbose_name_plural = "Материалы курса"


class LessonMaterial(MaterialBase):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="materials", verbose_name="Урок")

    class Meta(MaterialBase.Meta):
        verbose_name = "Материал урока"
        verbose_name_plural = "Материалы урока"


class TeacherAssignment(models.Model):
    enrollment = models.ForeignKey(
        CourseEnrollment,
        on_delete=models.CASCADE,
        related_name="teacher_assignments",
        verbose_name="Доступ ученика к курсу",
    )
    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.CASCADE,
        related_name="student_assignments",
        verbose_name="Преподаватель",
    )
    is_primary = models.BooleanField("Основной преподаватель", default=False)
    is_active = models.BooleanField("Активно", default=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teacher_assignments_created",
        verbose_name="Назначил",
    )
    notes = models.TextField("Заметки", blank=True)
    assigned_at = models.DateTimeField("Назначен", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "Назначение преподавателя"
        verbose_name_plural = "Назначения преподавателей"
        ordering = ["-is_primary", "-assigned_at"]

    def __str__(self):
        return f"{self.enrollment} — {self.teacher}"


class TeacherRequest(models.Model):
    TYPE_ADD = "add"
    TYPE_CHANGE = "change"

    TYPE_CHOICES = [
        (TYPE_ADD, bt("I want lessons with a teacher", "Хочу занятия с преподавателем")),
        (TYPE_CHANGE, bt("I want to change teachers", "Хочу сменить преподавателя")),
    ]

    STATUS_NEW = "new"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_NEW, "Новая"),
        (STATUS_APPROVED, "Одобрена"),
        (STATUS_REJECTED, "Отклонена"),
        (STATUS_CANCELLED, "Отменена"),
    ]

    enrollment = models.ForeignKey(
        CourseEnrollment,
        on_delete=models.CASCADE,
        related_name="teacher_requests",
        verbose_name="Ученик / курс",
    )
    request_type = models.CharField(
        "Тип заявки",
        max_length=32,
        choices=TYPE_CHOICES,
        default=TYPE_ADD,
    )
    current_teacher = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="change_requests_from",
        verbose_name="Текущий преподаватель",
    )
    requested_teacher = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_requests",
        verbose_name="Желаемый преподаватель",
    )
    message = models.TextField("Комментарий ученика", blank=True)
    status = models.CharField("Статус", max_length=32, choices=STATUS_CHOICES, default=STATUS_NEW)
    admin_comment = models.TextField("Комментарий администратора", blank=True)

    created_at = models.DateTimeField("Создана", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлена", auto_now=True)

    class Meta:
        verbose_name = "Заявка на преподавателя"
        verbose_name_plural = "Заявки на преподавателей"
        ordering = ["-created_at"]

    def __str__(self):
        teacher = self.requested_teacher.full_name if self.requested_teacher else "любой преподаватель"
        return f"{self.enrollment} — {teacher}"
