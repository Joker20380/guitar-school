from datetime import timedelta

from django.db import migrations, models
from django.db.models import Count, Q
from django.utils import timezone


def merge_duplicate_enrollments(apps, schema_editor):
    Enrollment = apps.get_model("courses", "CourseEnrollment")
    LessonProgress = apps.get_model("courses", "LessonProgress")
    TeacherAssignment = apps.get_model("courses", "TeacherAssignment")
    TeacherRequest = apps.get_model("courses", "TeacherRequest")

    duplicate_groups = (
        Enrollment.objects
        .exclude(user_id=None)
        .values("user_id", "course_id")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
    )

    for group in duplicate_groups:
        rows = list(
            Enrollment.objects
            .filter(user_id=group["user_id"], course_id=group["course_id"])
            .order_by("created_at", "id")
        )
        canonical = max(
            rows,
            key=lambda row: (
                bool(row.activated_at),
                LessonProgress.objects.filter(enrollment_id=row.id).count(),
                -row.id,
            ),
        )

        for duplicate in (row for row in rows if row.id != canonical.id):
            for progress in LessonProgress.objects.filter(enrollment_id=duplicate.id):
                existing = LessonProgress.objects.filter(
                    enrollment_id=canonical.id,
                    lesson_id=progress.lesson_id,
                ).first()

                if existing:
                    changed = []
                    if progress.is_completed and not existing.is_completed:
                        existing.is_completed = True
                        existing.completed_at = progress.completed_at
                        changed.extend(("is_completed", "completed_at"))
                    if progress.student_note and not existing.student_note:
                        existing.student_note = progress.student_note
                        changed.append("student_note")
                    if changed:
                        existing.save(update_fields=changed)
                    progress.delete()
                else:
                    progress.enrollment_id = canonical.id
                    progress.save(update_fields=["enrollment"])

            TeacherAssignment.objects.filter(enrollment_id=duplicate.id).update(enrollment_id=canonical.id)
            TeacherRequest.objects.filter(enrollment_id=duplicate.id).update(enrollment_id=canonical.id)

            changed = []
            if not canonical.course_request_id and duplicate.course_request_id:
                canonical.course_request_id = duplicate.course_request_id
                changed.append("course_request")
            if not canonical.activated_at and duplicate.activated_at:
                canonical.activated_at = duplicate.activated_at
                changed.append("activated_at")
            if duplicate.last_access_at and (
                not canonical.last_access_at or duplicate.last_access_at > canonical.last_access_at
            ):
                canonical.last_access_at = duplicate.last_access_at
                changed.append("last_access_at")
            if duplicate.is_active and not canonical.is_active:
                canonical.is_active = True
                changed.append("is_active")
            if changed:
                canonical.save(update_fields=changed)

            duplicate.delete()


def set_existing_invitation_expiry(apps, schema_editor):
    Enrollment = apps.get_model("courses", "CourseEnrollment")
    valid_until = timezone.now() + timedelta(days=7)
    Enrollment.objects.filter(
        activated_at__isnull=True,
        invitation_used_at__isnull=True,
        invitation_expires_at__isnull=True,
    ).update(invitation_expires_at=valid_until)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("courses", "0005_teacherskill_teacher_teacherassignment_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="courseenrollment",
            name="invitation_expires_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Приглашение действительно до"),
        ),
        migrations.AddField(
            model_name="courseenrollment",
            name="invitation_used_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Приглашение использовано"),
        ),
        migrations.RunPython(merge_duplicate_enrollments, migrations.RunPython.noop),
        migrations.RunPython(set_existing_invitation_expiry, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="courseenrollment",
            constraint=models.UniqueConstraint(
                condition=Q(user__isnull=False),
                fields=("user", "course"),
                name="unique_user_course_enrollment",
            ),
        ),
    ]
