"""
Management command: list_connections
Lists all connections with their status.
"""

from django.core.management.base import BaseCommand
from connections.models import Connection


class Command(BaseCommand):
    help = "List all connections and their status."

    def handle(self, *args, **options):
        conns = Connection.objects.all()
        if not conns.exists():
            self.stdout.write("No connections found.")
            return
        for c in conns:
            enabled = "✓" if c.enabled else "✗"
            self.stdout.write(
                f"[{enabled}] {c.name} | {c.connection_type} | {c.status}"
            )
