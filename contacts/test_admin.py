from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import ContactMessage


class ContactAdminTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            "test-admin", "admin@example.com", "Synthetic-password-194!"
        )

    def reply_in_admin(self, entry):
        before = ContactMessage.objects.values().get(pk=entry.pk)
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("admin:contacts_contactmessage_change", args=[entry.pk]),
            {field: str(getattr(entry, field) or "") for field in (
                "name", "direction", "email", "phone", "telegram", "other_contact",
                "preferred_contact", "subject", "message",
            )} | {"status": "replied", "_save": "Save"},
        )
        entry.refresh_from_db()
        self.assertEqual(entry.status, "replied")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ContactMessage.objects.count(), 1)
        after = ContactMessage.objects.values().get(pk=entry.pk)
        for field, value in before.items():
            if field not in {"status", "updated_at"}:
                self.assertEqual(after[field], value, field)

    def test_public_trial_then_admin_reply_without_message(self):
        form = self.client.get(reverse("contacts:trial")).context["form"]
        response = self.client.post(reverse("contacts:trial"), {
            "name": "Élodie Müller", "direction": "russian", "phone": "+33142345678",
            "preferred_contact": "other", "other_contact": "student@example.com",
            "submission_token": form.initial["submission_token"],
        })
        self.assertEqual(response.status_code, 302)
        entry = ContactMessage.objects.get()
        self.assertEqual(entry.message, "")
        self.assertEqual(entry.status, "new")
        self.assertEqual(entry.direction, "russian")
        self.assertEqual(entry.other_contact, "student@example.com")
        self.assertIsNotNone(entry.submission_key)
        self.reply_in_admin(entry)

    def test_legacy_message_and_contacts_survive_admin_reply(self):
        entry = ContactMessage.objects.create(
            name="José Müller", email="legacy@example.com", phone="+442079460958",
            telegram="@legacy_student", preferred_contact="telegram",
            subject="Historical enquiry", message="Please keep this original message.",
        )
        self.reply_in_admin(entry)
