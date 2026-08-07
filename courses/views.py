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

from .forms import CourseRequestForm, TeacherRequestForm
from .models import Course, CourseRequest, CourseEnrollment, Lesson, LessonProgress, Teacher, TeacherAssignment, TeacherRequest


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

    send_mail(
        subject=subject,
        message=message,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "webmaster@localhost"),
        recipient_list=[course_request.email],
        fail_silently=False,
    )

    course_request.verification_sent_at = timezone.now()
    course_request.save(update_fields=["verification_sent_at"])


def course_list(request):
    courses = Course.objects.filter(is_active=True).order_by("sort_order", "title")

    return render(request, "courses/course_list.html", {
        "courses": courses,
    })


def course_detail(request, slug):
    course = get_object_or_404(Course, slug=slug, is_active=True)
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
            "Заявка уже была отправлена недавно. Попробуйте ещё раз чуть позже.",
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
                send_verification_email(request, course_request)
                messages.success(
                    request,
                    "Заявка создана. Мы отправили ссылку подтверждения на ваш email.",
                )
            except Exception:
                messages.warning(
                    request,
                    "Заявка создана, но письмо подтверждения не отправилось. Мы проверим заявку вручную.",
                )
        else:
            messages.success(
                request,
                "Заявка создана. Мы подтвердим её через выбранный телефон или мессенджер.",
            )

        return redirect(course.get_absolute_url())

    messages.error(
        request,
        "Проверьте поля формы. Некоторые данные заполнены некорректно.",
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
        messages.error(request, "Ссылка подтверждения устарела. Отправьте заявку ещё раз.")
        return redirect("courses:list")
    except signing.BadSignature:
        messages.error(request, "Некорректная ссылка подтверждения.")
        return redirect("courses:list")

    course_request = get_object_or_404(CourseRequest, id=data.get("request_id"))

    if not course_request.is_verified:
        course_request.is_verified = True
        course_request.verified_at = timezone.now()
        course_request.save(update_fields=["is_verified", "verified_at"])

    messages.success(
        request,
        "Заявка подтверждена. Теперь преподаватель сможет открыть вам доступ к курсу.",
    )

    return redirect(course_request.course.get_absolute_url())


def activate_student_account(request, token):
    enrollment = get_object_or_404(
        CourseEnrollment.objects.select_related("user", "course"),
        invitation_token=token,
        is_active=True,
    )

    if enrollment.is_expired:
        messages.error(request, "Срок доступа к курсу истёк.")
        return redirect("courses:list")

    if not enrollment.user:
        messages.error(request, "Аккаунт ученика ещё не создан. Свяжитесь с преподавателем.")
        return redirect(enrollment.course.get_absolute_url())

    if request.method == "POST":
        form = SetPasswordForm(enrollment.user, request.POST)

        if form.is_valid():
            form.save()

            if not enrollment.activated_at:
                enrollment.activated_at = timezone.now()

            enrollment.last_access_at = timezone.now()
            enrollment.save(update_fields=["activated_at", "last_access_at"])

            login(request, enrollment.user)

            messages.success(request, "Аккаунт активирован. Добро пожаловать в курс.")
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
    enrollment = get_object_or_404(
        CourseEnrollment.objects.select_related("course"),
        user=request.user,
        course__slug=slug,
        is_active=True,
    )

    if enrollment.is_expired:
        messages.error(request, "Срок доступа к курсу истёк.")
        return redirect("courses:my_courses")

    enrollment.last_access_at = timezone.now()
    enrollment.save(update_fields=["last_access_at"])

    lessons = list(
        enrollment.course.lessons
        .filter(is_published=True)
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
        "progress_percent": enrollment.progress_percent(),
    })


@login_required
@require_POST
def mark_lesson_complete(request, slug, lesson_id):
    enrollment = get_object_or_404(
        CourseEnrollment,
        user=request.user,
        course__slug=slug,
        is_active=True,
    )
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
    enrollment = get_object_or_404(
        CourseEnrollment.objects.select_related("course"),
        user=request.user,
        course__slug=slug,
        is_active=True,
    )

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
    enrollment = get_object_or_404(
        CourseEnrollment.objects.select_related("course"),
        user=request.user,
        course__slug=slug,
        is_active=True,
    )

    form = TeacherRequestForm(request.POST, enrollment=enrollment)

    if form.is_valid():
        teacher_request = form.save(commit=False)
        teacher_request.enrollment = enrollment
        teacher_request.status = TeacherRequest.STATUS_NEW
        teacher_request.save()

        messages.success(
            request,
            "Заявка отправлена. Администратор школы рассмотрит её и назначит преподавателя.",
        )
    else:
        messages.error(
            request,
            "Проверьте заявку. Нужно выбрать преподавателя и тип заявки.",
        )

    return redirect("courses:my_course_teachers", slug=slug)
