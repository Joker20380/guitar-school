from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.text import slugify

from .models import Course, Lesson, CourseRequest, CourseEnrollment, LessonProgress


User = get_user_model()


def make_unique_username(base):
    base = slugify(base) or "student"
    username = base[:120]
    counter = 1

    while User.objects.filter(username=username).exists():
        suffix = f"-{counter}"
        username = f"{base[:120 - len(suffix)]}{suffix}"
        counter += 1

    return username


class LessonInline(admin.StackedInline):
    model = Lesson
    extra = 1
    fields = (
        "title",
        "short_description",
        "content",
        "video_url",
        "online_meeting_url",
        "homework",
        "sort_order",
        "is_published",
    )


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "level", "format", "price", "is_active", "sort_order")
    list_filter = ("level", "format", "is_active")
    search_fields = ("title", "short_description", "description")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [LessonInline]


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "is_published", "sort_order")
    list_filter = ("course", "is_published")
    search_fields = ("title", "short_description", "homework", "content")


class LessonProgressInline(admin.TabularInline):
    model = LessonProgress
    extra = 0
    fields = ("lesson", "is_completed", "completed_at", "student_note")
    readonly_fields = ("completed_at",)


@admin.register(CourseRequest)
class CourseRequestAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "phone",
        "messenger",
        "email",
        "course",
        "verification_channel",
        "is_verified",
        "preferred_format",
        "status",
        "created_at",
    )
    list_filter = (
        "status",
        "verification_channel",
        "is_verified",
        "preferred_format",
        "course",
        "created_at",
    )
    search_fields = ("name", "phone", "messenger", "email", "message")
    readonly_fields = (
        "created_at",
        "verified_at",
        "verification_sent_at",
        "ip_address",
        "user_agent",
    )
    actions = ["create_student_accounts"]

    @admin.action(description="Создать аккаунт ученика и выдать доступ")
    def create_student_accounts(self, request, queryset):
        created_enrollments = 0
        created_users = 0
        sent_invites = 0
        skipped_no_email = 0

        for course_request in queryset.select_related("course"):
            if not course_request.email:
                skipped_no_email += 1
                continue

            user = User.objects.filter(email__iexact=course_request.email).first()

            if not user:
                username_base = course_request.email.split("@")[0]
                user = User(
                    username=make_unique_username(username_base),
                    email=course_request.email.lower(),
                    first_name=course_request.name[:150],
                    is_active=True,
                )
                user.set_unusable_password()
                user.save()
                created_users += 1

            enrollment, created = CourseEnrollment.objects.get_or_create(
                course_request=course_request,
                defaults={
                    "course": course_request.course,
                    "user": user,
                    "student_name": course_request.name,
                    "email": course_request.email.lower(),
                    "phone": course_request.phone,
                    "messenger": course_request.messenger,
                    "is_active": True,
                },
            )

            if not enrollment.user:
                enrollment.user = user

            enrollment.course = course_request.course
            enrollment.student_name = course_request.name
            enrollment.email = course_request.email.lower()
            enrollment.phone = course_request.phone
            enrollment.messenger = course_request.messenger
            enrollment.is_active = True
            enrollment.invitation_sent_at = timezone.now()
            enrollment.save()

            created_enrollments += int(created)

            course_request.status = CourseRequest.STATUS_ENROLLED
            course_request.save(update_fields=["status"])

            activate_url = request.build_absolute_uri(
                reverse("courses:activate", kwargs={"token": enrollment.invitation_token})
            )

            send_mail(
                subject=f"Доступ к курсу «{enrollment.course.title}»",
                message=(
                    f"Здравствуйте, {enrollment.student_name}!\n\n"
                    f"Вам открыт доступ к курсу «{enrollment.course.title}».\n\n"
                    f"Чтобы войти в личный кабинет ученика, задайте пароль по ссылке:\n"
                    f"{activate_url}\n\n"
                    "После активации вы сможете видеть уроки и отмечать прогресс."
                ),
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "webmaster@localhost"),
                recipient_list=[enrollment.email],
                fail_silently=True,
            )
            sent_invites += 1

        self.message_user(
            request,
            (
                f"Создано доступов: {created_enrollments}. "
                f"Создано пользователей: {created_users}. "
                f"Приглашений отправлено: {sent_invites}. "
                f"Без email пропущено: {skipped_no_email}."
            ),
        )


@admin.register(CourseEnrollment)
class CourseEnrollmentAdmin(admin.ModelAdmin):
    list_display = (
        "student_name",
        "user",
        "course",
        "email",
        "phone",
        "is_active",
        "progress_value",
        "created_at",
        "last_access_at",
        "activation_link",
    )
    list_filter = ("is_active", "course", "created_at")
    search_fields = ("student_name", "email", "phone", "messenger", "user__username", "course__title")
    readonly_fields = (
        "access_token",
        "invitation_token",
        "created_at",
        "invitation_sent_at",
        "activated_at",
        "last_access_at",
        "activation_link",
    )
    fields = (
        "course",
        "course_request",
        "user",
        "student_name",
        "email",
        "phone",
        "messenger",
        "is_active",
        "access_expires_at",
        "invitation_token",
        "activation_link",
        "access_token",
        "invitation_sent_at",
        "activated_at",
        "last_access_at",
        "notes",
        "created_at",
    )
    inlines = [LessonProgressInline]

    def progress_value(self, obj):
        return f"{obj.progress_percent()}%"

    progress_value.short_description = "Прогресс"

    def activation_link(self, obj):
        if not obj or not obj.invitation_token:
            return "-"

        return format_html(
            '<code>/courses/activate/{}/</code>',
            obj.invitation_token,
        )

    activation_link.short_description = "Ссылка активации"


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ("enrollment", "lesson", "is_completed", "completed_at", "updated_at")
    list_filter = ("is_completed", "lesson__course", "updated_at")
    search_fields = ("enrollment__student_name", "enrollment__email", "lesson__title")
