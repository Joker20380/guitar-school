from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import DatabaseError, close_old_connections
from django.test import Client, TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.urls import reverse

from .models import ContactMessage
from .trial import TrialForm


class TrialTests(TestCase):
    def payload(self, **changes):
        page = self.client.get(reverse("contacts:trial"))
        return {"name": "Élodie Müller", "direction": "guitar", "phone": "+442079460958", "preferred_contact": "whatsapp", "submission_token": page.context["form"].initial["submission_token"], **changes}

    def test_entry_points_reset_direction(self):
        for direction in ["russian", "guitar", "", "unknown"]:
            response = self.client.get(reverse("contacts:trial"), {"direction": direction})
            self.assertEqual(response.context["form"].initial["direction"], direction if direction in {"russian", "guitar"} else "")
        self.assertNotIn("email", response.context["form"].fields)
        required = {name for name, field in response.context["form"].fields.items() if field.required and not field.widget.is_hidden}
        self.assertEqual(required, {"name", "direction", "phone"})

    def test_international_names_phones_channels_and_undecided(self):
        for name, phone in [("Élodie", "+33142345678"), ("José", "+14155552671"), ("Müller", "+4930123456"), ("Елена", "+79161712233")]:
            for channel in ["whatsapp", "telegram", "other"]:
                form = TrialForm({"name": name, "phone": phone, "direction": "undecided", "preferred_contact": channel, "submission_token": "checked-by-view"})
                self.assertTrue(form.is_valid(), form.errors)

    def test_conditional_fields_ignore_stale_hidden_values(self):
        form = TrialForm(self.payload(telegram="invalid space", other_contact="<bad>"))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["telegram"], "")
        self.assertEqual(form.cleaned_data["other_contact"], "")
        form = TrialForm(self.payload(preferred_contact="telegram", telegram="bad space"))
        self.assertFalse(form.is_valid())
        self.assertIn("telegram", form.errors)
        form = TrialForm(self.payload(preferred_contact="other", other_contact="test@example.com"))
        self.assertTrue(form.is_valid(), form.errors)

    def test_saved_data_visible_in_admin(self):
        data = self.payload(preferred_contact="other", direction="undecided", other_contact="reply@example.com")
        response = self.client.post(reverse("contacts:trial"), data, follow=True)
        self.assertContains(response, "Thank you for your request!")
        entry = ContactMessage.objects.get()
        for field in ["name", "direction", "preferred_contact", "other_contact"]:
            self.assertEqual(getattr(entry, field), data[field])
        self.assertEqual(str(entry.phone), data["phone"])
        self.assertEqual(entry.email, "")
        admin = get_user_model().objects.create_superuser("preview-admin", "admin@example.com", "Preview-password-194!")
        self.client.force_login(admin)
        page = self.client.get(reverse("admin:contacts_contactmessage_change", args=[entry.pk]))
        for value in [data["name"], data["phone"], data["other_contact"], "undecided"]:
            self.assertContains(page, value)

    def test_success_requires_saved_submission_and_duplicate_does_not_notify_twice(self):
        self.assertRedirects(self.client.get(reverse("contacts:trial_success")), reverse("contacts:trial"))
        data = self.payload()
        with patch("contacts.trial.notify_trial") as notify:
            for unused in range(2):
                response = self.client.post(reverse("contacts:trial"), data)
                self.assertRedirects(response, reverse("contacts:trial_success"))
            notify.assert_called_once()
        self.assertEqual(ContactMessage.objects.count(), 1)

    def test_invalid_submission_and_database_failure_preserve_values_without_success(self):
        for field, value in [("name", "123"), ("direction", "invalid"), ("phone", "02079460958"), ("phone", "+12"), ("website", "bot")]:
            response = self.client.post(reverse("contacts:trial"), self.payload(**{field: value}))
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors)
            self.assertFalse(ContactMessage.objects.exists())
            self.assertNotContains(response, "Thank you for your request!")
        data = self.payload()
        with patch("contacts.trial.ContactMessage.objects.get_or_create", side_effect=DatabaseError("local failure")):
            response = self.client.post(reverse("contacts:trial"), data)
        self.assertContains(response, "could not save")
        self.assertContains(response, data["name"])
        self.assertFalse(ContactMessage.objects.exists())

    def test_valid_replay_returns_original_result_without_editing_the_request(self):
        data = self.payload(preferred_contact="telegram", telegram="@first_student")
        headers = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
        first = self.client.post(reverse("contacts:trial"), data, **headers)
        original = ContactMessage.objects.values().get()
        replay = self.client.post(reverse("contacts:trial"), {
            **data, "name": "José", "direction": "russian", "phone": "+33142345678",
            "preferred_contact": "other", "other_contact": "different@example.com",
        }, **headers)
        self.assertEqual(replay.json(), first.json())
        self.assertEqual(ContactMessage.objects.count(), 1)
        self.assertEqual(ContactMessage.objects.values().get(), original)

    @override_settings(CONTACT_NOTIFY_EMAIL="admin@example.com", TELEGRAM_BOT_TOKEN="local-test-token", TELEGRAM_NOTIFY_CHAT_ID="test-recipient")
    def test_failed_notifications_do_not_undo_request_or_claim_delivery(self):
        data = self.payload(preferred_contact="telegram", telegram="@test_student")
        with patch("contacts.notifications.send_mail", return_value=0), patch("contacts.notifications.urlopen", side_effect=OSError("offline")):
            response = self.client.post(reverse("contacts:trial"), data)
        self.assertRedirects(response, reverse("contacts:trial_success"))
        entry = ContactMessage.objects.get()
        self.assertEqual(entry.telegram, "@test_student")
        self.assertEqual(entry.email_notification_status, "failed")
        self.assertEqual(entry.telegram_notification_status, "failed")

    def test_csrf_token_binding_and_expiry(self):
        data = self.payload()
        self.assertEqual(Client(enforce_csrf_checks=True).post(reverse("contacts:trial"), data).status_code, 403)
        stranger = Client()
        response = stranger.post(reverse("contacts:trial"), data)
        self.assertContains(response, "form has expired")
        with patch("django.core.signing.time.time", return_value=99999999999):
            response = self.client.post(reverse("contacts:trial"), data)
        self.assertContains(response, "form has expired")
        self.assertFalse(ContactMessage.objects.exists())

    def test_ajax_validation_database_failure_and_retry_contract(self):
        data = self.payload()
        headers = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
        invalid = self.client.post(reverse("contacts:trial"), {**data, "name": ""}, **headers)
        self.assertEqual(invalid.status_code, 400)
        self.assertFalse(invalid.json()["saved"])
        with patch("contacts.trial.ContactMessage.objects.get_or_create", side_effect=DatabaseError("local failure")):
            failed = self.client.post(reverse("contacts:trial"), data, **headers)
        self.assertEqual(failed.status_code, 503)
        self.assertFalse(failed.json()["saved"])
        accepted = self.client.post(reverse("contacts:trial"), data, **headers)
        self.assertEqual(accepted.status_code, 200)
        self.assertTrue(accepted.json()["saved"])
        replay = self.client.post(reverse("contacts:trial"), data, **headers)
        self.assertEqual(replay.json(), accepted.json())
        self.assertEqual(ContactMessage.objects.count(), 1)


class ConcurrentTrialTests(TransactionTestCase):
    @skipUnlessDBFeature("has_select_for_update")
    def test_same_submission_in_two_overlapping_requests_creates_one_record(self):
        browser = Client()
        form = browser.get(reverse("contacts:trial")).context["form"]
        data = {"name": "Test student", "direction": "guitar", "phone": "+442079460958", "submission_token": form.initial["submission_token"]}
        barrier = Barrier(2)

        def send():
            close_old_connections()
            try:
                client = Client()
                client.cookies = browser.cookies.copy()
                barrier.wait(timeout=10)
                return client.post(reverse("contacts:trial"), data).status_code
            finally:
                close_old_connections()

        with patch("contacts.trial.notify_trial") as notify, ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(send) for unused in range(2)]
            self.assertEqual([future.result(timeout=20) for future in futures], [302, 302])
        self.assertEqual(ContactMessage.objects.count(), 1)
        notify.assert_called_once()
