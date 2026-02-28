"""Management command: list_messages – print all messages with send status."""

from django.core.management.base import BaseCommand
from messaging.models import Message


class Command(BaseCommand):
    help = "List all messages."

    def add_arguments(self, parser):
        parser.add_argument("--sent", action="store_true", help="Only sent messages.")
        parser.add_argument(
            "--unsent", action="store_true", help="Only unsent messages."
        )

    def handle(self, *args, **options):
        qs = Message.objects.all()
        if options["sent"]:
            qs = qs.filter(sent=True)
        elif options["unsent"]:
            qs = qs.filter(sent=False)
        for m in qs:
            sent_label = "SENT" if m.sent else "DRAFT"
            self.stdout.write(
                f"[{sent_label}] #{m.pk} {m.headline} ({m.created_at:%Y-%m-%d})"
            )
        self.stdout.write(f"\nTotal: {qs.count()}")
