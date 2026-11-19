from unittest.mock import patch
from django.test import TestCase, override_settings
from .forms import ContactMessageForm
from .models import ContactMessage


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['testserver'])
class ApplicationTests(TestCase):
    def payload(self, **changes):
        return dict({'name': 'José 李', 'email': 'student@example.com', 'phone': '+32470123456',
                     'subject': 'Online guitar lesson', 'message': '', 'website': ''}, **changes)

    def test_lesson_and_consultation_save_without_comment(self):
        for subject in ['Online guitar lesson', 'Consultation']:
            form = ContactMessageForm(self.payload(subject=subject))
            self.assertTrue(form.is_valid(), form.errors)
            entry = form.save()
            self.assertEqual(entry.subject, subject)
            self.assertEqual(entry.email, 'student@example.com')
            self.assertEqual(str(entry.phone), '+32470123456')

    def test_required_and_invalid_inputs(self):
        for field in ['name', 'email', 'phone', 'subject']:
            form = ContactMessageForm(self.payload(**{field: ''}))
            self.assertFalse(form.is_valid())
            self.assertIn(field, form.errors)
        for field, value in [('phone', '123'), ('email', 'wrong'), ('subject', 'arbitrary'),
                             ('website', 'spam'), ('message', 'x' * 1501), ('name', 'https://spam.com')]:
            form = ContactMessageForm(self.payload(**{field: value}))
            self.assertFalse(form.is_valid(), field)

    @patch('contacts.views.send_contact_notification')
    def test_success_redirect_and_refresh_does_not_duplicate(self, notify):
        response = self.client.post('/contacts/', self.payload())
        self.assertRedirects(response, '/contacts/#contact-form')
        self.client.get('/contacts/')
        self.assertEqual(ContactMessage.objects.count(), 1)
        notify.assert_called_once()

    @patch('contacts.views.send_contact_notification', side_effect=RuntimeError('offline'))
    def test_notification_failure_preserves_request_and_success(self, notify):
        response = self.client.post('/contacts/', self.payload(), follow=True)
        self.assertContains(response, 'Your request has been received')
        self.assertEqual(ContactMessage.objects.count(), 1)

    @patch('contacts.views.send_contact_notification')
    def test_invalid_post_does_not_save_or_notify(self, notify):
        response = self.client.post('/contacts/', self.payload(email='bad'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContactMessage.objects.count(), 0)
        notify.assert_not_called()

    def test_both_languages_and_required_fields(self):
        for lang, heading in [('en', 'Questions or ready for a lesson?'), ('ru', 'Есть вопросы или хотите на урок?')]:
            self.client.cookies['phoenix_songs_language'] = lang
            response = self.client.get('/contacts/')
            self.assertContains(response, heading)
            for field in ['name', 'email', 'phone', 'subject']:
                self.assertTrue(response.context['form'].fields[field].required)
            self.assertNotContains(response, 'name="telegram"')

    @patch('contacts.views.send_contact_notification')
    def test_russian_success(self, notify):
        self.client.cookies['phoenix_songs_language'] = 'ru'
        response = self.client.post('/contacts/', self.payload(), follow=True)
        self.assertContains(response, 'Заявка принята')

    def test_csrf_is_required(self):
        from django.test import Client
        response = Client(enforce_csrf_checks=True).post('/contacts/', self.payload())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ContactMessage.objects.exists())
