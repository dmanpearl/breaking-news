import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0004_apikey_assign_owner_to_superuser"),
        ("core", "0003_user_email_nullable"),
    ]

    operations = [
        # Make owner required (NOT NULL) and switch to CASCADE so deleting
        # a user also deletes their keys rather than leaving orphaned rows.
        migrations.AlterField(
            model_name="apikey",
            name="owner",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="api_keys",
                to=settings.AUTH_USER_MODEL,
                help_text="The Breaking News user account that owns this key. "
                "Deactivating or deleting the user will revoke the key.",
            ),
        ),
        # Allowed origins: comma-separated list of permitted Origin/Referer
        # values. Leave blank to allow requests from any origin (e.g. server-
        # to-server keys). Example: reader.breakingnewsguys.com
        migrations.AddField(
            model_name="apikey",
            name="allowed_origins",
            field=models.CharField(
                max_length=500,
                blank=True,
                default="",
                help_text=(
                    "Comma-separated list of permitted origins "
                    "(e.g. reader.breakingnewsguys.com, localhost:8080). "
                    "Leave blank to allow any origin."
                ),
            ),
        ),
    ]
