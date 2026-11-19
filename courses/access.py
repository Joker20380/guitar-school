from dataclasses import dataclass

from .models import CourseEnrollment


@dataclass(frozen=True)
class CourseAccessResult:
    enrollment: CourseEnrollment | None
    message: str = ""

    @property
    def allowed(self):
        return self.enrollment is not None and not self.message


def resolve_course_access(user, slug):
    enrollment = (
        CourseEnrollment.objects
        .select_related("course")
        .filter(user=user, course__slug=slug)
        .first()
    )

    if not enrollment:
        return CourseAccessResult(None, "У вас нет доступа к этому курсу.")

    if not enrollment.is_active:
        return CourseAccessResult(enrollment, "Доступ к курсу приостановлен или отозван.")

    if enrollment.is_expired:
        return CourseAccessResult(enrollment, "Срок доступа к курсу истёк.")

    return CourseAccessResult(enrollment)
