from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.db.models import Count

from courses.models import CourseEnrollment


class Command(BaseCommand):
    help = "Read-only compatibility warning before applying inherited course migrations."

    def handle(self, *args, **options):
        if "courses_courseenrollment" not in connection.introspection.table_names():
            self.stdout.write("Fresh database: no existing enrollments.")
            return
        applied = MigrationRecorder(connection).applied_migrations()
        if ("courses", "0006_secure_course_access") not in applied:
            groups = CourseEnrollment.objects.exclude(user_id=None).values("user_id", "course_id").annotate(total=Count("pk")).filter(total__gt=1).count()
            if groups:
                raise CommandError("STOP: inherited migration 0006 merges duplicate enrollments destructively. Preserve a backup and reconcile duplicates and their contacts/progress before migration. No data changed.")
        self.stdout.write("No pending duplicate-enrollment merge found. This does not verify production backups, source synchronization or media compatibility.")
