"""
Management command: create_superuser_quick
Creates a superuser non-interactively using arguments.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError


class Command(BaseCommand):
    help = "Create a superuser quickly (non-interactive)."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="admin")
        parser.add_argument("--email", default="")
        parser.add_argument("--password", required=True)
        parser.add_argument("--first-name", default="")
        parser.add_argument("--last-name", default="")

    def handle(self, *args, **options):
        User = get_user_model()
        username = options["username"]

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f"User '{username}' already exists — skipping."))
            return

        # Normalize blank email to None so the unique constraint allows
        # multiple users with no email address.
        raw_email = options["email"].strip()
        email = raw_email if raw_email else None

        try:
            User.objects.create_superuser(
                username=username,
                email=email,
                password=options["password"],
                first_name=options["first_name"],
                last_name=options["last_name"],
            )
        except IntegrityError as exc:
            raise CommandError(
                f"Could not create superuser '{username}': {exc}\n"
                "If this is an email conflict, pass a unique --email or omit it entirely."
            ) from exc

        self.stdout.write(self.style.SUCCESS(f"Superuser '{username}' created."))
