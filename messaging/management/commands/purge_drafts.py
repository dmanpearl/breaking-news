"""Management command: purge_drafts – delete unsent messages."""

from django.core.management.base import BaseCommand
from messaging.models import Message


class Command(BaseCommand):
    help = "Delete all unsent (draft) messages."

    def add_arguments(self, parser):
        parser.add_argument("--confirm", action="store_true", required=True)

    def handle(self, *args, **options):
        qs = Message.objects.filter(sent=False)
        count = qs.count()
        qs.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} draft message(s)."))
