"""
Management command: seed_groups
Creates the 3 standard permission groups: admin, editor, visitor.
"""

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from messaging.models import Message
from connections.models import Connection


class Command(BaseCommand):
    help = "Seed the three standard permission groups: admin, editor, visitor."

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

        # ---------- admin ----------
        admin_group, _ = Group.objects.get_or_create(name="admin")
        all_perms = Permission.objects.filter(content_type__in=[msg_ct, conn_ct])
        admin_group.permissions.set(all_perms)

        self.stdout.write(self.style.SUCCESS("Groups seeded: visitor, editor, admin"))
