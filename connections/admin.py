from django.contrib import admin

from .models import ConnectionDiscord, ConnectionSlack


@admin.register(ConnectionDiscord)
class ConnectionDiscordAdmin(admin.ModelAdmin):
    list_display = ("name", "enabled", "status", "can_edit_sent", "updated_at")
    list_filter = ("enabled", "status", "can_edit_sent")
    readonly_fields = ("status", "status_message", "created_at", "updated_at")
    fieldsets = (
        (
            "General",
            {
                "fields": (
                    "name",
                    "enabled",
                    "status",
                    "status_message",
                    "created_at",
                    "updated_at",
                )
            },
        ),
        (
            "Discord Settings",
            {
                "fields": ("webhook_url", "can_edit_sent"),
                "description": (
                    "Webhook messages can always be edited using the same webhook URL. "
                    "Enable 'Can edit sent' to have the Update action patch the existing "
                    "Discord message instead of leaving it unchanged."
                ),
            },
        ),
    )


@admin.register(ConnectionSlack)
class ConnectionSlackAdmin(admin.ModelAdmin):
    list_display = ("name", "enabled", "status", "channel_id", "can_edit_sent", "updated_at")
    list_filter = ("enabled", "status", "can_edit_sent")
    readonly_fields = ("status", "status_message", "created_at", "updated_at")
    fieldsets = (
        (
            "General",
            {
                "fields": (
                    "name",
                    "enabled",
                    "status",
                    "status_message",
                    "created_at",
                    "updated_at",
                )
            },
        ),
        (
            "Slack Settings",
            {
                "fields": ("bot_token", "channel_id", "can_edit_sent"),
                "description": (
                    "Paste the Bot User OAuth Token (xoxb-...) and the channel ID. "
                    "Enable 'Can edit sent' to have the Update action call chat.update "
                    "on the existing Slack message instead of leaving it unchanged. "
                    "See README_SLACK_CONNECTION.md for setup instructions."
                ),
            },
        ),
    )
