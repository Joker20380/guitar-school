from django.core import mail
from django.test import RequestFactory, TestCase, override_settings

from contacts.models import ContactMessage
from contacts.views import send_contact_notification
from courses.models import Course, CourseRequest
from courses.views import send_course_request_notification, send_verification_email


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="school@example.com",
    CONTACT_NOTIFY_EMAIL="admin@example.com",
)
class EmailNotificationTests(TestCase):
    def setUp(self):
        self.course = Course.objects.create(
            title="Почтовый курс",
            slug="email-course",
            short_description="Проверка почты",
            description="Тестовый курс",
        )
        self.course_request = CourseRequest.objects.create(
            course=self.course,
            name="Ученик",
            email="student@example.com",
        )

    def test_course_sends_student_verification_and_admin_notification(self):
        request = RequestFactory().get("/courses/email-course/", secure=True)

        send_verification_email(request, self.course_request)
        send_course_request_notification(self.course_request)

        self.course_request.refresh_from_db()
        self.assertIsNotNone(self.course_request.verification_sent_at)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[0].to, ["student@example.com"])
        self.assertEqual(mail.outbox[1].to, ["admin@example.com"])

    def test_contact_form_notification_is_delivered_to_admin(self):
        contact = ContactMessage.objects.create(
            name="Посетитель",
            email="visitor@example.com",
            message="Хочу записаться на урок",
        )

        sent = send_contact_notification(contact)

        self.assertTrue(sent)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["admin@example.com"])
