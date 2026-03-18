from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_user_email_nullable"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserPreferences",
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
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="preferences",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "sidebar_width",
                    models.PositiveIntegerField(
                        default=280,
                        help_text="History sidebar width in pixels (180-480).",
                    ),
                ),
            ],
            options={
                "verbose_name": "User Preferences",
                "verbose_name_plural": "User Preferences",
            },
        ),
    ]
