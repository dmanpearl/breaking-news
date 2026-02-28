from django.db import models


class ConnectionStatus(models.TextChoices):
    OK = "ok", "OK"
    ERROR = "error", "Error"
    UNKNOWN = "unknown", "Unknown"


class ConnectionType(models.TextChoices):
    DISCORD = "discord", "Discord"


class Connection(models.Model):
    """Base connection record. Subclassed by platform-specific models."""

    name = models.CharField(max_length=120)
    connection_type = models.CharField(
        max_length=32,
        choices=ConnectionType.choices,
        default=ConnectionType.DISCORD,
    )
    enabled = models.BooleanField(default=True)
    status = models.CharField(
        max_length=32,
        choices=ConnectionStatus.choices,
        default=ConnectionStatus.UNKNOWN,
    )
    status_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} [{self.get_connection_type_display()}]"

    def get_concrete(self):
        """Return the most-derived subclass instance."""
        if self.connection_type == ConnectionType.DISCORD:
            try:
                return self.connectiondiscord
            except ConnectionDiscord.DoesNotExist:
                pass
        return self


class ConnectionDiscord(Connection):
    """Discord-specific connection fields."""

    webhook_url = models.URLField(
        help_text="Discord Incoming Webhook URL for this channel/server."
    )
    bot_token = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional Bot token (needed for message editing).",
    )
    channel_id = models.CharField(
        max_length=64,
        blank=True,
        help_text="Channel ID (required when using bot token to edit messages).",
    )
    can_edit_sent = models.BooleanField(
        default=False,
        help_text="Whether previously sent messages can be edited via this connection.",
    )

    class Meta:
        verbose_name = "Discord Connection"
        verbose_name_plural = "Discord Connections"

    def save(self, *args, **kwargs):
        self.connection_type = "discord"
        super().save(*args, **kwargs)
