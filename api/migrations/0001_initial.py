import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="APIKey",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "label",
                    models.CharField(
                        help_text="Human-readable name for this key (e.g. 'Acme Corp integration').",
                        max_length=120,
                    ),
                ),
                (
                    "key_hash",
                    models.CharField(
                        editable=False,
                        help_text="SHA-256 hash of the bearer token. The plaintext is never stored.",
                        max_length=64,
                        unique=True,
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Deactivate to revoke access without deleting the record.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "last_used_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="Updated on each authenticated request.",
                        null=True,
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        blank=True,
                        help_text="Optional — link this key to a Breaking News user account.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="api_keys",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "API Key",
                "verbose_name_plural": "API Keys",
                "ordering": ["-created_at"],
            },
        ),
    ]
