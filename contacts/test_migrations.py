from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from uuid import uuid4


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
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())

    def test_optional_message_migration_preserves_complete_existing_rows(self):
        old_target = [("contacts", "0002_contactmessage_direction_and_more")]
        new_target = [("contacts", "0003_contactmessage_message_optional")]
        executor = MigrationExecutor(connection)
        executor.migrate(old_target)
        try:
            old_model = executor.loader.project_state(old_target).apps.get_model("contacts", "ContactMessage")
            for message in ["Original historical message", ""]:
                old_model.objects.create(
                    name="Élodie Test", email="legacy@example.com", phone="+33142345678",
                    telegram="@legacy_student", other_contact="Other contact",
                    preferred_contact="telegram", direction="russian", message=message,
                    status="new", submission_key=uuid4(), email_notification_status="failed",
                )
            before = list(old_model.objects.order_by("pk").values())
            executor = MigrationExecutor(connection)
            executor.migrate(new_target)
            new_model = executor.loader.project_state(new_target).apps.get_model("contacts", "ContactMessage")
            self.assertEqual(list(new_model.objects.order_by("pk").values()), before)
            self.assertTrue(new_model._meta.get_field("message").blank)
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
