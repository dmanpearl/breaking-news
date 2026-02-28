"""Management command: resend_message – resend a message by ID."""

from django.core.management.base import BaseCommand, CommandError
from messaging.models import Message
from connections.services import dispatch_message


class Command(BaseCommand):
    help = "Resend a message to all enabled connections."

    def add_arguments(self, parser):
        parser.add_argument("message_id", type=int)

    def handle(self, *args, **options):
        try:
            msg = Message.objects.get(pk=options["message_id"])
        except Message.DoesNotExist:
            raise CommandError(f"Message {options['message_id']} not found.")
        dispatch_message(msg)
        self.stdout.write(self.style.SUCCESS(f"Message #{msg.pk} dispatched."))
