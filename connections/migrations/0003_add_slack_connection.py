import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("connections", "0002_remove_bot_token_channel_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="connection",
            name="connection_type",
            field=models.CharField(
                choices=[("discord", "Discord"), ("slack", "Slack")],
                default="discord",
                max_length=32,
            ),
        ),
        migrations.CreateModel(
            name="ConnectionSlack",
            fields=[
                (
                    "connection_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="connections.connection",
                    ),
                ),
                (
                    "bot_token",
                    models.CharField(
                        max_length=255,
                        help_text="Slack Bot User OAuth Token (xoxb-...). Requires the chat:write scope.",
                    ),
                ),
                (
                    "channel_id",
                    models.CharField(
                        max_length=64,
                        help_text=(
                            "Slack channel ID (e.g. C08ABCDEF12). "
                            "Right-click the channel in Slack → View channel details → copy the ID "
                            "from the bottom of the About tab."
                        ),
                    ),
                ),
                (
                    "can_edit_sent",
                    models.BooleanField(
                        default=False,
                        help_text=(
                            "When enabled, editing a sent message will update it in Slack. "
                            "Requires the original Slack message timestamp (ts) to have been stored on send."
                        ),
                    ),
                ),
            ],
            options={
                "verbose_name": "Slack Connection",
                "verbose_name_plural": "Slack Connections",
            },
            bases=("connections.connection",),
        ),
    ]
