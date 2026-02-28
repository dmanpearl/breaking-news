from django.contrib import admin

from .models import Connection, ConnectionDiscord


@admin.register(ConnectionDiscord)
class ConnectionDiscordAdmin(admin.ModelAdmin):
    list_display = ("name", "enabled", "status", "can_edit_sent", "updated_at")
    list_filter = ("enabled", "status")
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
            {"fields": ("webhook_url", "bot_token", "channel_id", "can_edit_sent")},
        ),
    )
