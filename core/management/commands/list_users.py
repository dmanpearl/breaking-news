"""
Management command: list_users
Lists all users or shows details for a single user.

Examples:
    python manage.py list_users
    python manage.py list_users --username dmanpearl
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "List all users, or show details for a specific user."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            default="",
            help="Show details for a single user instead of listing all.",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        username = options["username"].strip()

        if username:
            # Single-user detail view
            try:
                u = User.objects.get(username=username)
            except User.DoesNotExist:
                raise CommandError(f"User '{username}' not found.")

            groups = ", ".join(u.groups.values_list("name", flat=True)) or "—"
            self.stdout.write(f"""
Username   : {u.username}
Name       : {u.get_full_name() or '—'}
Email      : {u.email or '—'}
Active     : {u.is_active}
Staff      : {u.is_staff}
Superuser  : {u.is_superuser}
Groups     : {groups}
Date joined: {u.date_joined:%Y-%m-%d %H:%M:%S}
Last login : {u.last_login.strftime('%Y-%m-%d %H:%M:%S') if u.last_login else '—'}
""".strip())
        else:
            # Full list
            users = User.objects.order_by("username")
            count = users.count()
            if not count:
                self.stdout.write("No users found.")
                return

            self.stdout.write(
                f"\n{'USERNAME':<20} {'NAME':<26} {'EMAIL':<30} {'SUPER':>5} {'STAFF':>5} {'ACTIVE':>6}"
            )
            self.stdout.write("-" * 93)
            for u in users:
                self.stdout.write(
                    f"{u.username:<20} {u.get_full_name():<26} {(u.email or ''):<30}"
                    f" {'Y' if u.is_superuser else 'N':>5}"
                    f" {'Y' if u.is_staff else 'N':>5}"
                    f" {'Y' if u.is_active else 'N':>6}"
                )
            self.stdout.write(f"\n{count} user{'s' if count != 1 else ''} total.")
