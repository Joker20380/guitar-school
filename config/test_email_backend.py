import json
from unittest.mock import MagicMock, patch

from django.core.mail import EmailMultiAlternatives, send_mail
from django.test import SimpleTestCase, override_settings


@override_settings(
    EMAIL_BACKEND="config.email_backend.BrevoEmailBackend",
    BREVO_API_KEY="test-api-key",
    DEFAULT_FROM_EMAIL="Школа гитары <jvov@mail.ru>",
    BREVO_REPLY_TO="jvov@mail.ru",
)
class BrevoEmailBackendTests(SimpleTestCase):
    @patch("config.email_backend.urlopen")
    def test_sends_django_email_through_https_api(self, mocked_urlopen):
        response = MagicMock(status=201)
        response.__enter__.return_value = response
        mocked_urlopen.return_value = response

        sent = send_mail("Тема", "Текст", None, ["student@example.com"])

        self.assertEqual(sent, 1)
        request = mocked_urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(request.full_url, "https://api.brevo.com/v3/smtp/email")
        self.assertEqual(request.headers["Api-key"], "test-api-key")
        self.assertEqual(payload["sender"]["email"], "jvov@mail.ru")
        self.assertEqual(payload["replyTo"]["email"], "jvov@mail.ru")
        self.assertEqual(payload["to"], [{"email": "student@example.com"}])
        self.assertEqual(payload["textContent"], "Текст")

    @patch("config.email_backend.urlopen")
    def test_sends_html_alternative(self, mocked_urlopen):
        response = MagicMock(status=201)
        response.__enter__.return_value = response
        mocked_urlopen.return_value = response
        message = EmailMultiAlternatives("Тема", "Текст", to=["student@example.com"])
        message.attach_alternative("<p>Текст</p>", "text/html")

        message.send()

        payload = json.loads(mocked_urlopen.call_args.args[0].data)
        self.assertEqual(payload["textContent"], "Текст")
        self.assertEqual(payload["htmlContent"], "<p>Текст</p>")

    @override_settings(BREVO_API_KEY="")
    def test_missing_api_key_raises_clear_error(self):
        with self.assertRaisesMessage(RuntimeError, "BREVO_API_KEY is not configured"):
            send_mail("Тема", "Текст", None, ["student@example.com"])
