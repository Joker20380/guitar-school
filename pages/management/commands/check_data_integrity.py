import hashlib
import json
import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "Compare pre-existing database columns across additive migrations without exporting row contents."

    def add_arguments(self, parser):
        action = parser.add_mutually_exclusive_group(required=True)
        action.add_argument("--save", type=Path)
        action.add_argument("--verify", type=Path)

    def describe(self):
        result = {}
        with connection.cursor() as cursor:
            for table in connection.introspection.table_names(cursor):
                if table == "django_migrations":
                    continue
                columns = [field.name for field in connection.introspection.get_table_description(cursor, table)]
                constraints = connection.introspection.get_constraints(cursor, table)
                primary = next((value["columns"] for value in constraints.values() if value["primary_key"]), columns)
                specification = {"columns": columns, "order": primary}
                if table in {"django_content_type", "auth_permission"}:
                    cursor.execute(f"SELECT MAX(id) FROM {connection.ops.quote_name(table)}")
                    specification["max_id"] = cursor.fetchone()[0]
                result[table] = specification
        return result

    def fingerprint(self, table, specification):
        quoted = connection.ops.quote_name
        selected = ", ".join(quoted(column) for column in specification["columns"])
        ordering = ", ".join(quoted(column) for column in specification["order"])
        parameters = []
        condition = ""
        if "max_id" in specification:
            if specification["max_id"] is None:
                condition = " WHERE 1 = 0"
            else:
                condition = " WHERE id <= %s"
                parameters.append(specification["max_id"])
        digest = hashlib.sha256()
        count = 0
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT {selected} FROM {quoted(table)}{condition} ORDER BY {ordering}", parameters)
            while rows := cursor.fetchmany(512):
                for row in rows:
                    digest.update(json.dumps(row, default=str, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode())
                    digest.update(b"\n")
                    count += 1
        return {"rows": count, "sha256": digest.hexdigest()}

    def handle(self, *args, **options):
        if options["save"]:
            target = options["save"]
            if target.exists():
                raise CommandError("Snapshot already exists; choose a new path.")
            tables = self.describe()
            for table, specification in tables.items():
                specification["fingerprint"] = self.fingerprint(table, specification)
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w") as output:
                json.dump({"version": 1, "tables": tables}, output, sort_keys=True)
            self.stdout.write(f"Saved fingerprints for {len(tables)} tables; no row contents exported.")
        else:
            snapshot = json.loads(options["verify"].read_text())
            if snapshot.get("version") != 1:
                raise CommandError("Unsupported snapshot version.")
            changed = [table for table, specification in snapshot["tables"].items() if self.fingerprint(table, specification) != specification["fingerprint"]]
            if changed:
                raise CommandError("Pre-existing data changed in: " + ", ".join(changed))
            self.stdout.write(f"PASS: pre-existing data unchanged in {len(snapshot['tables'])} tables.")
