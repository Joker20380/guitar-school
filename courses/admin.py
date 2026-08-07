from django.conf import settings
from django.contrib import admin
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.utils import timezone

from .models import (
    Course,
    CourseRequest,
    CourseEnrollment,
    Lesson,
    LessonProgress,
    Teacher,
    TeacherAssignment,
    TeacherRequest,
    TeacherSkill,
)


class LessonInline(admin.StackedInline):
    model = Lesson
    extra = 0
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
    list_display = ("title", "level", "format", "is_active", "sort_order", "updated_at")
    list_filter = ("level", "format", "is_active")
    list_editable = ("is_active", "sort_order")
    search_fields = ("title", "short_description", "description")
    prepopulated_fields = {"slug": ("title",)}
    inlines = (LessonInline,)


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "sort_order", "is_published", "created_at")
    list_filter = ("course", "is_published")
    list_editable = ("sort_order", "is_published")
    search_fields = ("title", "short_description", "content", "homework")
    fields = (
        "course",
        "title",
        "short_description",
        "content",
        "video_url",
        "online_meeting_url",
        "homework",
        "sort_order",
        "is_published",
    )


@admin.register(CourseRequest)
class CourseRequestAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "course",
        "phone",
        "email",
        "verification_channel",
        "is_verified",
        "status",
        "created_at",
    )
    list_filter = ("status", "verification_channel", "is_verified", "course", "created_at")
    search_fields = ("name", "phone", "email", "message")
    readonly_fields = (
        "ip_address",
        "user_agent",
        "created_at",
        "verified_at",
        "verification_sent_at",
    )
    actions = ("create_student_accounts",)

    fieldsets = (
        ("Заявка", {
            "fields": (
                "course",
                "name",
                "phone",
                "email",
                "verification_channel",
                "preferred_format",
                "message",
                "status",
            )
        }),
        ("Подтверждение", {
            "fields": (
                "is_verified",
                "verified_at",
                "verification_sent_at",
            )
        }),
        ("Техническая информация", {
            "fields": (
                "ip_address",
                "user_agent",
                "created_at",
            )
        }),
    )

    @admin.action(description="Создать аккаунт ученика и выдать доступ")
    def create_student_accounts(self, request, queryset):
        created_count = 0
        skipped_count = 0

        for course_request in queryset.select_related("course"):
            if not course_request.email:
                skipped_count += 1
                continue

            username = course_request.email.lower().strip()

            user, user_created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": course_request.email,
                    "first_name": course_request.name,
                },
            )

            if user_created:
                user.set_unusable_password()
                user.save(update_fields=["password"])

            enrollment, enrollment_created = CourseEnrollment.objects.get_or_create(
                course=course_request.course,
                user=user,
                defaults={
                    "course_request": course_request,
                    "student_name": course_request.name,
                    "email": course_request.email,
                    "phone": course_request.phone,
                    "is_active": True,
                    "invitation_sent_at": timezone.now(),
                },
            )

            if not enrollment.course_request:
                enrollment.course_request = course_request

            enrollment.student_name = course_request.name
            enrollment.email = course_request.email
            enrollment.phone = course_request.phone
            enrollment.is_active = True
            enrollment.invitation_sent_at = timezone.now()
            enrollment.save()

            course_request.status = CourseRequest.STATUS_ENROLLED
            course_request.save(update_fields=["status"])

            activation_url = request.build_absolute_uri(
                f"/courses/activate/{enrollment.invitation_token}/"
            )

            if course_request.email:
                send_mail(
                    subject="Доступ к курсу гитары",
                    message=(
                        f"Здравствуйте, {course_request.name}!\n\n"
                        f"Вам открыт доступ к курсу «{course_request.course.title}».\n"
                        f"Активируйте аккаунт по ссылке:\n{activation_url}\n\n"
                        "Если вы не отправляли заявку, просто проигнорируйте это письмо."
                    ),
                    from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "webmaster@localhost"),
                    recipient_list=[course_request.email],
                    fail_silently=True,
                )

            created_count += 1

        self.message_user(
            request,
            f"Готово. Доступ выдан: {created_count}. Пропущено без email: {skipped_count}.",
        )


class LessonProgressInline(admin.TabularInline):
    model = LessonProgress
    extra = 0
    readonly_fields = ("created_at", "updated_at")


class TeacherAssignmentInline(admin.TabularInline):
    model = TeacherAssignment
    extra = 0
    raw_id_fields = ("teacher", "assigned_by")
    fields = ("teacher", "is_primary", "is_active", "assigned_by", "notes")


@admin.register(CourseEnrollment)
class CourseEnrollmentAdmin(admin.ModelAdmin):
    list_display = (
        "student_name",
        "course",
        "email",
        "phone",
        "is_active",
        "activated_at",
        "last_access_at",
        "created_at",
    )
    list_filter = ("is_active", "course", "created_at", "activated_at")
    search_fields = ("student_name", "email", "phone", "user__username", "course__title")
    raw_id_fields = ("user", "course_request")
    readonly_fields = (
        "access_token",
        "invitation_token",
        "created_at",
        "activated_at",
        "last_access_at",
    )
    inlines = (TeacherAssignmentInline, LessonProgressInline)


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ("enrollment", "lesson", "is_completed", "completed_at", "updated_at")
    list_filter = ("is_completed", "lesson__course", "completed_at")
    search_fields = (
        "enrollment__student_name",
        "enrollment__email",
        "lesson__title",
        "student_note",
    )
    raw_id_fields = ("enrollment", "lesson")


@admin.register(TeacherSkill)
class TeacherSkillAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "sort_order")
    list_editable = ("sort_order",)
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "teaching_level",
        "lesson_format",
        "experience_years",
        "is_active",
        "sort_order",
    )
    list_filter = ("teaching_level", "lesson_format", "is_active", "skills")
    list_editable = ("is_active", "sort_order")
    search_fields = ("full_name", "short_bio", "bio")
    prepopulated_fields = {"slug": ("full_name",)}
    filter_horizontal = ("skills",)
    raw_id_fields = ("user",)


@admin.register(TeacherAssignment)
class TeacherAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "teacher",
        "enrollment",
        "is_primary",
        "is_active",
        "assigned_by",
        "assigned_at",
    )
    list_filter = ("is_primary", "is_active", "teacher", "assigned_at")
    search_fields = (
        "teacher__full_name",
        "enrollment__student_name",
        "enrollment__email",
        "enrollment__course__title",
    )
    raw_id_fields = ("teacher", "enrollment", "assigned_by")
    readonly_fields = ("assigned_at", "updated_at")


@admin.register(TeacherRequest)
class TeacherRequestAdmin(admin.ModelAdmin):
    list_display = (
        "enrollment",
        "request_type",
        "current_teacher",
        "requested_teacher",
        "status",
        "created_at",
    )
    list_filter = ("status", "request_type", "requested_teacher", "created_at")
    search_fields = (
        "enrollment__student_name",
        "enrollment__email",
        "enrollment__course__title",
        "current_teacher__full_name",
        "requested_teacher__full_name",
        "message",
    )
    raw_id_fields = ("enrollment", "current_teacher", "requested_teacher")
    readonly_fields = ("created_at", "updated_at")
