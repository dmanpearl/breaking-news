"""
Management command: create_superuser_quick
Creates a superuser non-interactively using env vars or arguments.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create a superuser quickly (non-interactive)."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="admin")
        parser.add_argument("--email", default="admin@example.com")
        parser.add_argument("--password", required=True)
        parser.add_argument("--first-name", default="Admin")
        parser.add_argument("--last-name", default="User")

    def handle(self, *args, **options):
        User = get_user_model()
        username = options["username"]
        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f"User '{username}' already exists."))
            return
        User.objects.create_superuser(
            username=username,
            email=options["email"],
            password=options["password"],
            first_name=options["first_name"],
            last_name=options["last_name"],
        )
        self.stdout.write(self.style.SUCCESS(f"Superuser '{username}' created."))
