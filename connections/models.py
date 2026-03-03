from django.db import models


class ConnectionStatus(models.TextChoices):
    OK = "ok", "OK"
    ERROR = "error", "Error"
    UNKNOWN = "unknown", "Unknown"


class ConnectionType(models.TextChoices):
    DISCORD = "discord", "Discord"
    SLACK = "slack", "Slack"


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
        if self.connection_type == ConnectionType.SLACK:
            try:
                return self.connectionslack
            except ConnectionSlack.DoesNotExist:
                pass
        return self


class ConnectionDiscord(Connection):
    """
    Discord webhook connection.

    Discord webhooks can always edit their own messages — no bot token needed.
    The only requirement is that we stored the message ID returned by the
    initial POST ?wait=true call (held in DeliveryReceipt.remote_message_id).

    can_edit_sent: when True, the Update action will PATCH the existing Discord
    message in-place rather than sending a new one.  Set to False if you want
    edits to remain local-only (the Discord message will not change).
    """

    webhook_url = models.URLField(
        help_text="Discord Incoming Webhook URL for this channel/server."
    )
    can_edit_sent = models.BooleanField(
        default=False,
        help_text=(
            "When enabled, editing a sent message will update it in Discord. "
            "Requires the original Discord message ID to have been stored on send."
        ),
    )

    class Meta:
        verbose_name = "Discord Connection"
        verbose_name_plural = "Discord Connections"

    def save(self, *args, **kwargs):
        self.connection_type = "discord"
        super().save(*args, **kwargs)


class ConnectionSlack(Connection):
    """
    Slack Bot Token connection.

    Uses the Slack Web API (chat.postMessage / chat.update / chat.delete).
    Requires a Bot Token (xoxb-...) with the chat:write scope, and the
    channel_id of the target channel.

    The message timestamp (ts) returned by chat.postMessage is stored in
    DeliveryReceipt.remote_message_id and used for edit/delete operations.

    can_edit_sent: when True, the Update action will call chat.update on the
    existing Slack message in-place.
    """

    bot_token = models.CharField(
        max_length=255,
        help_text=(
            "Slack Bot User OAuth Token (xoxb-...). "
            "Requires the chat:write scope."
        ),
    )
    channel_id = models.CharField(
        max_length=64,
        help_text=(
            "Slack channel ID (e.g. C08ABCDEF12). "
            "Right-click the channel in Slack → View channel details → copy the ID "
            "from the bottom of the About tab."
        ),
    )
    can_edit_sent = models.BooleanField(
        default=False,
        help_text=(
            "When enabled, editing a sent message will update it in Slack. "
            "Requires the original Slack message timestamp (ts) to have been stored on send."
        ),
    )

    class Meta:
        verbose_name = "Slack Connection"
        verbose_name_plural = "Slack Connections"

    def save(self, *args, **kwargs):
        self.connection_type = "slack"
        super().save(*args, **kwargs)
