"""
Management command: test_connections
Sends a test ping to all enabled connections and reports results.
"""

from django.core.management.base import BaseCommand

from connections.models import Connection
from connections.services import send_to_discord, send_to_slack


class Command(BaseCommand):
    help = "Send a test ping to all enabled connections."

    def handle(self, *args, **options):
        connections = Connection.objects.filter(enabled=True)
        if not connections.exists():
            self.stdout.write(self.style.WARNING("No enabled connections found."))
            return
        for conn in connections:
            concrete = conn.get_concrete()
            if concrete.connection_type == "discord":
                ok, rid, err = send_to_discord(
                    concrete,
                    "🔔 Connection Test",
                    "This is a test ping from Breaking News.",
                )
                if ok:
                    self.stdout.write(self.style.SUCCESS(f"[OK] {conn.name}"))
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            f"[FAIL] {conn.name}: {concrete.status_message}"
                        )
                    )
            elif concrete.connection_type == "slack":
                ok, ts, err = send_to_slack(
                    concrete,
                    "🔔 Connection Test",
                    "This is a test ping from Breaking News.",
                )
                if ok:
                    self.stdout.write(self.style.SUCCESS(f"[OK] {conn.name}"))
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            f"[FAIL] {conn.name}: {concrete.status_message}"
                        )
                    )
            else:
                self.stdout.write(
                    self.style.WARNING(f"[SKIP] {conn.name}: unsupported type")
                )
