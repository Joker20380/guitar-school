from config.i18n import bilingual as bt
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
        return CourseAccessResult(None, bt('You do not have access to this course.', 'У вас нет доступа к этому курсу.'))

    if not enrollment.is_active:
        return CourseAccessResult(enrollment, bt('Access to this course is suspended or revoked.', 'Доступ к курсу приостановлен или отозван.'))

    if enrollment.is_expired:
        return CourseAccessResult(enrollment, bt('Your access to this course has expired.', 'Срок доступа к курсу истёк.'))

    return CourseAccessResult(enrollment)
