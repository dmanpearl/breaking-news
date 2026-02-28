"""
Dispatcher services – send a Message to all enabled Connections.
"""

import logging

import requests

from .models import Connection, ConnectionDiscord, ConnectionStatus

logger = logging.getLogger(__name__)


def send_to_discord(
    connection: ConnectionDiscord,
    headline: str,
    body: str,
    image_url: str | None = None,
):
    """Send a message via Discord webhook. Returns (success, discord_message_id)."""
    embeds = [
        {
            "title": headline,
            "description": body,
            "color": 0xE63946,
        }
    ]
    if image_url:
        embeds[0]["image"] = {"url": image_url}

    payload = {"embeds": embeds}
    try:
        resp = requests.post(
            connection.webhook_url + "?wait=true",
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        connection.status = ConnectionStatus.OK
        connection.status_message = "Last send successful."
        connection.save(update_fields=["status", "status_message", "updated_at"])
        return True, str(data.get("id", ""))
    except Exception as exc:
        logger.error("Discord send failed for %s: %s", connection.name, exc)
        connection.status = ConnectionStatus.ERROR
        connection.status_message = str(exc)
        connection.save(update_fields=["status", "status_message", "updated_at"])
        return False, ""


def edit_discord_message(
    connection: ConnectionDiscord,
    discord_message_id: str,
    headline: str,
    body: str,
    image_url: str | None = None,
):
    """Edit a previously sent Discord message using the bot token."""
    if not connection.bot_token or not connection.channel_id:
        return False, "Bot token or channel ID not configured."
    embeds = [{"title": headline, "description": body, "color": 0xE63946}]
    if image_url:
        embeds[0]["image"] = {"url": image_url}
    url = f"https://discord.com/api/v10/channels/{connection.channel_id}/messages/{discord_message_id}"
    headers = {"Authorization": f"Bot {connection.bot_token}"}
    try:
        resp = requests.patch(url, json={"embeds": embeds}, headers=headers, timeout=10)
        resp.raise_for_status()
        return True, ""
    except Exception as exc:
        logger.error("Discord edit failed for %s: %s", connection.name, exc)
        return False, str(exc)


def dispatch_message(message):
    """
    Dispatch a Message to all enabled connections.
    Creates/updates DeliveryReceipt records.
    """
    from messaging.models import DeliveryReceipt

    connections = Connection.objects.filter(enabled=True)
    image_url = None
    if message.image:
        # Build absolute URL – best effort, works when called from view with request
        image_url = message.image.url  # relative; Discord won't load relative URLs
        # Callers that have a request should pass absolute_image_url separately

    for conn in connections:
        concrete = conn.get_concrete()
        success = False
        remote_id = ""
        error_msg = ""

        if concrete.connection_type == "discord":
            success, remote_id = send_to_discord(
                concrete, message.headline, message.body, image_url
            )
        else:
            error_msg = f"Unknown connection type: {concrete.connection_type}"

        DeliveryReceipt.objects.update_or_create(
            message=message,
            connection=conn,
            defaults={
                "success": success,
                "remote_message_id": remote_id,
                "error": error_msg,
            },
        )

    message.sent = True
    message.save(update_fields=["sent"])
