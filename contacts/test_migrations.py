from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ContactMigrationTests(TransactionTestCase):
    def test_old_contact_columns_survive_additive_trial_migration(self):
        old_target = [("contacts", "0001_initial")]
        new_target = [("contacts", "0002_contactmessage_direction_and_more")]
        executor = MigrationExecutor(connection)
        executor.migrate(old_target)
        try:
            old_apps = executor.loader.project_state(old_target).apps
            original = old_apps.get_model("contacts", "ContactMessage").objects.create(name="Legacy synthetic", email="legacy@example.com", phone="+442079460958", telegram="@legacy_contact", preferred_contact="telegram", message="Legacy message", status="replied")
            executor = MigrationExecutor(connection)
            executor.migrate(new_target)
            new_apps = executor.loader.project_state(new_target).apps
            preserved = new_apps.get_model("contacts", "ContactMessage").objects.get(pk=original.pk)
            self.assertEqual(preserved.name, original.name)
            self.assertEqual(preserved.email, original.email)
            self.assertEqual(preserved.telegram, original.telegram)
            self.assertEqual(preserved.message, original.message)
            self.assertEqual(preserved.status, original.status)
            self.assertIsNone(preserved.submission_key)
            self.assertEqual(preserved.direction, "")
        finally:
            MigrationExecutor(connection).migrate(new_target)
