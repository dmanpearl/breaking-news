"""
Management command: seed_groups
Creates the 2 standard permission groups: visitor, editor.
Run this once after deploy: python manage.py seed_groups
"""

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from messaging.models import Message
from connections.models import Connection


class Command(BaseCommand):
    help = "Seed the two standard permission groups: visitor, editor."

    def handle(self, *args, **options):
        msg_ct = ContentType.objects.get_for_model(Message)
        conn_ct = ContentType.objects.get_for_model(Connection)

        # ---------- visitor ----------
        visitor, _ = Group.objects.get_or_create(name="visitor")
        view_message = Permission.objects.filter(
            codename="view_message", content_type=msg_ct
        ).first()
        view_connection = Permission.objects.filter(
            codename="view_connection", content_type=conn_ct
        ).first()
        visitor_perms = [p for p in [view_message, view_connection] if p]
        visitor.permissions.set(visitor_perms)

        # ---------- editor ----------
        editor, _ = Group.objects.get_or_create(name="editor")
        editor_perms = Permission.objects.filter(
            content_type=msg_ct,
            codename__in=["add_message", "change_message", "view_message"],
        )
        editor.permissions.set(editor_perms)

        # Remove the legacy admin group if it still exists in the database.
        deleted, _ = Group.objects.filter(name="admin").delete()
        if deleted:
            self.stdout.write(self.style.WARNING("Deleted legacy 'admin' group."))

        self.stdout.write(self.style.SUCCESS("Groups seeded: visitor, editor"))
