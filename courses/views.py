from config.i18n import bilingual as bt
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.db.models import Prefetch
from django.db import transaction

from .access import resolve_course_access
from .forms import CourseRequestForm, TeacherRequestForm
from .models import Course, CourseRequest, CourseEnrollment, Lesson, LessonProgress, Teacher, TeacherAssignment, TeacherRequest
from .models import LessonMaterial


REQUEST_COOLDOWN_SECONDS = 30
VERIFY_MAX_AGE_SECONDS = 60 * 60 * 24
VERIFY_SALT = "course-request-verification"


def get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")

    if forwarded:
        return forwarded.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR")


def build_verification_token(course_request):
    return signing.dumps(
        {"request_id": course_request.id},
        salt=VERIFY_SALT,
    )


def send_verification_email(request, course_request):
    token = build_verification_token(course_request)
    url = request.build_absolute_uri(f"/courses/verify/{token}/")

    subject = "Подтверждение заявки на курс гитары"
    message = (
        f"Здравствуйте, {course_request.name}!\n\n"
        f"Подтвердите заявку на курс «{course_request.course.title}» по ссылке:\n"
        f"{url}\n\n"
        "Если вы не отправляли заявку, просто проигнорируйте это письмо."
    )

    sent = send_mail(
        subject=subject,
        message=message,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "webmaster@localhost"),
        recipient_list=[course_request.email],
        fail_silently=False,
    )

    if sent == 1:
        course_request.verification_sent_at = timezone.now()
        course_request.save(update_fields=["verification_sent_at"])
    return sent == 1


def send_course_request_notification(course_request):
    recipient = getattr(settings, "CONTACT_NOTIFY_EMAIL", "")
    if not recipient:
        return False

    sent = send_mail(
        subject=f"Новая заявка на курс: {course_request.course.title}",
        message=(
            "На сайте школы создана новая заявка.\n\n"
            f"Курс: {course_request.course.title}\n"
            f"Имя: {course_request.name}\n"
            f"Email: {course_request.email or '-'}\n"
            f"Телефон: {course_request.phone or '-'}\n"
            f"Мессенджер: {course_request.messenger or '-'}\n"
            f"Канал подтверждения: {course_request.get_verification_channel_display()}\n"
            f"Комментарий: {course_request.message or '-'}\n"
        ),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "webmaster@localhost"),
        recipient_list=[recipient],
        fail_silently=False,
    )
    return sent == 1


def course_list(request):
    courses = Course.objects.filter(is_active=True, is_advertised=True).order_by("sort_order", "title")

    return render(request, "courses/course_list.html", {
        "courses": courses,
    })


def course_detail(request, slug):
    course = get_object_or_404(Course, slug=slug, is_active=True)
    if not course.is_advertised:
        if request.user.is_authenticated and resolve_course_access(request.user, slug).allowed:
            return redirect("courses:student_course", slug=slug)
        return redirect("contacts:trial")
    lessons = course.lessons.filter(is_published=True).order_by("sort_order", "id")
    form = CourseRequestForm(initial={
        "preferred_format": course.format,
        "verification_channel": CourseRequest.VERIFY_EMAIL,
    })

    return render(request, "courses/course_detail.html", {
        "course": course,
        "lessons": lessons,
        "form": form,
    })


@require_POST
def course_apply(request, slug):
    course = get_object_or_404(Course, slug=slug, is_active=True)
    lessons = course.lessons.filter(is_published=True).order_by("sort_order", "id")

    now_ts = timezone.now().timestamp()
    last_ts = request.session.get("last_course_request_ts")

    if last_ts and now_ts - float(last_ts) < REQUEST_COOLDOWN_SECONDS:
        messages.error(
            request,
            bt('You recently sent a request. Please wait before trying again.', 'Заявка уже была отправлена недавно. Попробуйте ещё раз чуть позже.'),
        )
        return redirect(course.get_absolute_url())

    form = CourseRequestForm(request.POST)

    if form.is_valid():
        course_request = form.save(commit=False)
        course_request.course = course
        course_request.ip_address = get_client_ip(request)
        course_request.user_agent = request.META.get("HTTP_USER_AGENT", "")[:300]
        course_request.save()

        request.session["last_course_request_ts"] = now_ts

        if course_request.verification_channel == CourseRequest.VERIFY_EMAIL:
            try:
                if not send_verification_email(request, course_request):
                    raise RuntimeError("Email backend did not accept the message")
                messages.success(
                    request,
                    bt('Your request is saved. The email service accepted the confirmation message; delivery is not confirmed.', 'Заявка создана. Почтовый сервис принял письмо подтверждения; доставка не подтверждена.'),
                )
            except Exception:
                messages.warning(
                    request,
                    bt('Your request is saved, but the confirmation email failed. We will review your request manually.', 'Заявка создана, но письмо подтверждения не отправилось. Мы проверим заявку вручную.'),
                )
        else:
            messages.success(
                request,
                bt('Your request is saved. We will confirm it using your phone or messenger.', 'Заявка создана. Мы подтвердим её через выбранный телефон или мессенджер.'),
            )

        try:
            send_course_request_notification(course_request)
        except Exception:
            messages.warning(
                request,
                bt('Your request is saved, but the additional school notification failed.', 'Заявка сохранена, но служебное уведомление школе не отправилось.'),
            )

        return redirect(course.get_absolute_url())

    messages.error(
        request,
        bt('Please check the highlighted fields.', 'Проверьте поля формы. Некоторые данные заполнены некорректно.'),
    )

    return render(request, "courses/course_detail.html", {
        "course": course,
        "lessons": lessons,
        "form": form,
    })


def verify_course_request(request, token):
    try:
        data = signing.loads(
            token,
            salt=VERIFY_SALT,
            max_age=VERIFY_MAX_AGE_SECONDS,
        )
    except signing.SignatureExpired:
        messages.error(request, bt('The confirmation link has expired. Please submit a new request.', 'Ссылка подтверждения устарела. Отправьте заявку ещё раз.'))
        return redirect("courses:list")
    except signing.BadSignature:
        messages.error(request, bt('Invalid confirmation link.', 'Некорректная ссылка подтверждения.'))
        return redirect("courses:list")

    course_request = get_object_or_404(CourseRequest, id=data.get("request_id"))

    if not course_request.is_verified:
        course_request.is_verified = True
        course_request.verified_at = timezone.now()
        course_request.save(update_fields=["is_verified", "verified_at"])

    messages.success(
        request,
        bt('Your request is confirmed. A teacher can now grant access to the course.', 'Заявка подтверждена. Теперь преподаватель сможет открыть вам доступ к курсу.'),
    )

    return redirect(course_request.course.get_absolute_url())


@transaction.atomic
def activate_student_account(request, token):
    enrollment = get_object_or_404(
        CourseEnrollment.objects.select_for_update(of=("self",)).select_related("user", "course"),
        invitation_token=token,
    )

    if enrollment.invitation_used_at or enrollment.activated_at:
        messages.info(request, bt('This invitation has already been used. Please sign in.', 'Приглашение уже использовано. Войдите в личный кабинет.'))
        return redirect("login")

    if enrollment.invitation_is_expired:
        messages.error(request, bt('This invitation has expired. Please request a new one from the school.', 'Срок действия приглашения истёк. Запросите новое приглашение у школы.'))
        return redirect("courses:list")

    if not enrollment.has_access:
        messages.error(request, bt('Your course access has expired or been revoked.', 'Доступ к курсу истёк или был отозван.'))
        return redirect("courses:list")

    if not enrollment.user:
        messages.error(request, bt('Your student account is not ready yet. Please contact your teacher.', 'Аккаунт ученика ещё не создан. Свяжитесь с преподавателем.'))
        return redirect(enrollment.course.get_absolute_url())

    if request.method == "POST":
        form = SetPasswordForm(enrollment.user, request.POST)

        if form.is_valid():
            form.save()

            if not enrollment.activated_at:
                enrollment.activated_at = timezone.now()

            enrollment.invitation_used_at = timezone.now()
            enrollment.last_access_at = timezone.now()
            enrollment.save(update_fields=["activated_at", "invitation_used_at", "last_access_at"])

            login(request, enrollment.user)

            messages.success(request, bt('Account activated. Welcome to the course.', 'Аккаунт активирован. Добро пожаловать в курс.'))
            return redirect("courses:student_course", slug=enrollment.course.slug)
    else:
        form = SetPasswordForm(enrollment.user)

    return render(request, "courses/activate.html", {
        "form": form,
        "enrollment": enrollment,
        "course": enrollment.course,
    })


@login_required
def my_courses(request):
    enrollments = (
        CourseEnrollment.objects
        .select_related("course")
        .filter(user=request.user, is_active=True)
        .order_by("-created_at")
    )

    return render(request, "courses/my_courses.html", {
        "enrollments": enrollments,
    })


@login_required
def student_course(request, slug):
    access = resolve_course_access(request.user, slug)

    if not access.allowed:
        messages.error(request, access.message)
        return redirect("courses:my_courses")

    enrollment = access.enrollment

    enrollment.last_access_at = timezone.now()
    enrollment.save(update_fields=["last_access_at"])

    lessons = list(
        enrollment.course.lessons
        .filter(is_published=True)
        .prefetch_related(Prefetch("materials", queryset=LessonMaterial.objects.filter(is_published=True), to_attr="published_materials"))
        .order_by("sort_order", "id")
    )

    existing_progress = {
        progress.lesson_id: progress
        for progress in LessonProgress.objects.filter(enrollment=enrollment)
    }

    lesson_rows = []

    for lesson in lessons:
        progress = existing_progress.get(lesson.id)

        if not progress:
            progress = LessonProgress.objects.create(
                enrollment=enrollment,
                lesson=lesson,
            )

        lesson_rows.append({
            "lesson": lesson,
            "progress": progress,
        })

    return render(request, "courses/student_course.html", {
        "course": enrollment.course,
        "enrollment": enrollment,
        "lesson_rows": lesson_rows,
        "course_materials": enrollment.course.materials.filter(is_published=True),
        "progress_percent": enrollment.progress_percent(),
    })


@login_required
@require_POST
def mark_lesson_complete(request, slug, lesson_id):
    access = resolve_course_access(request.user, slug)

    if not access.allowed:
        messages.error(request, access.message)
        return redirect("courses:my_courses")

    enrollment = access.enrollment
    lesson = get_object_or_404(
        Lesson,
        id=lesson_id,
        course=enrollment.course,
        is_published=True,
    )

    progress, created = LessonProgress.objects.get_or_create(
        enrollment=enrollment,
        lesson=lesson,
    )

    complete = request.POST.get("complete") == "1"

    progress.is_completed = complete
    progress.completed_at = timezone.now() if complete else None
    progress.save(update_fields=["is_completed", "completed_at", "updated_at"])

    return redirect("courses:student_course", slug=slug)


def teacher_list(request):
    teachers = (
        Teacher.objects
        .filter(is_active=True)
        .prefetch_related("skills")
        .order_by("sort_order", "full_name")
    )

    return render(request, "courses/teacher_list.html", {
        "teachers": teachers,
    })


def teacher_detail(request, slug):
    teacher = get_object_or_404(
        Teacher.objects.prefetch_related("skills"),
        slug=slug,
        is_active=True,
    )

    return render(request, "courses/teacher_detail.html", {
        "teacher": teacher,
    })


@login_required
def my_course_teachers(request, slug):
    access = resolve_course_access(request.user, slug)

    if not access.allowed:
        messages.error(request, access.message)
        return redirect("courses:my_courses")

    enrollment = access.enrollment

    assignments = (
        TeacherAssignment.objects
        .select_related("teacher")
        .filter(enrollment=enrollment, is_active=True, teacher__is_active=True)
        .order_by("-is_primary", "teacher__sort_order", "teacher__full_name")
    )

    active_teachers = (
        Teacher.objects
        .filter(is_active=True)
        .prefetch_related("skills")
        .order_by("sort_order", "full_name")
    )

    teacher_requests = (
        TeacherRequest.objects
        .select_related("current_teacher", "requested_teacher")
        .filter(enrollment=enrollment)
        .order_by("-created_at")[:10]
    )

    form = TeacherRequestForm(enrollment=enrollment)

    return render(request, "courses/my_course_teachers.html", {
        "course": enrollment.course,
        "enrollment": enrollment,
        "assignments": assignments,
        "active_teachers": active_teachers,
        "teacher_requests": teacher_requests,
        "form": form,
    })


@login_required
@require_POST
def request_teacher(request, slug):
    access = resolve_course_access(request.user, slug)

    if not access.allowed:
        messages.error(request, access.message)
        return redirect("courses:my_courses")

    enrollment = access.enrollment

    form = TeacherRequestForm(request.POST, enrollment=enrollment)

    if form.is_valid():
        teacher_request = form.save(commit=False)
        teacher_request.enrollment = enrollment
        teacher_request.status = TeacherRequest.STATUS_NEW
        teacher_request.save()

        messages.success(
            request,
            bt('Your request is saved. The school will review it and assign a teacher.', 'Заявка отправлена. Администратор школы рассмотрит её и назначит преподавателя.'),
        )
    else:
        messages.error(
            request,
            bt('Please choose a teacher and a request type.', 'Проверьте заявку. Нужно выбрать преподавателя и тип заявки.'),
        )

    return redirect("courses:my_course_teachers", slug=slug)
