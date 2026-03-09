"""
Data migration: assign every APIKey that has no owner to the first superuser
found (ordered by date_joined). This prepares the table for the subsequent
schema migration that makes owner NOT NULL.
"""

from django.db import migrations


def assign_keys_to_superuser(apps, schema_editor):
    APIKey = apps.get_model("api", "APIKey")
    User = apps.get_model("core", "User")

    superuser = User.objects.filter(is_superuser=True).order_by("date_joined").first()
    if superuser is None:
        # No superuser exists yet (e.g. fresh DB). Leave keys as-is;
        # the NOT NULL constraint will be added after this runs, so
        # the admin must create a superuser before the next migration.
        return

    updated = APIKey.objects.filter(owner__isnull=True).update(owner=superuser)
    if updated:
        print(f"\n  Assigned {updated} API key(s) to superuser '{superuser.username}'.")


def reverse_assign(apps, schema_editor):
    # Reversing would set owner back to NULL for all keys — acceptable for rollback.
    APIKey = apps.get_model("api", "APIKey")
    APIKey.objects.all().update(owner=None)


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0003_apikeyusage_endpoint_referer"),
        ("core", "0003_user_email_nullable"),
    ]

    operations = [
        migrations.RunPython(assign_keys_to_superuser, reverse_code=reverse_assign),
    ]
