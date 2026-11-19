from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from contacts.models import ContactMessage


class IntegrityCommandTests(TestCase):
    def test_snapshot_detects_changes_without_exporting_contacts(self):
        message = ContactMessage.objects.create(name="Private synthetic name", phone="+442079460958")
        with TemporaryDirectory() as directory:
            snapshot = Path(directory) / "integrity.json"
            call_command("check_data_integrity", save=snapshot, stdout=StringIO())
            self.assertEqual(snapshot.stat().st_mode & 0o777, 0o600)
            self.assertNotIn(message.name, snapshot.read_text())
            call_command("check_data_integrity", verify=snapshot, stdout=StringIO())
            message.name = "Changed synthetic name"
            message.save()
            with self.assertRaisesMessage(CommandError, "contacts_contactmessage"):
                call_command("check_data_integrity", verify=snapshot, stdout=StringIO())

    def test_new_content_types_are_allowed_but_existing_snapshot_is_protected(self):
        with TemporaryDirectory() as directory:
            snapshot = Path(directory) / "integrity.json"
            call_command("check_data_integrity", save=snapshot, stdout=StringIO())
            ContentType.objects.create(app_label="synthetic", model="migration_added_model")
            call_command("check_data_integrity", verify=snapshot, stdout=StringIO())
            with self.assertRaisesMessage(CommandError, "already exists"):
                call_command("check_data_integrity", save=snapshot, stdout=StringIO())
