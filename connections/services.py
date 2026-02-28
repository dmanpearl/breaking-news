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
    image_path: str | None = None,
):
    """
    Send a message via Discord webhook.

    Images are uploaded as multipart form data so Discord can display them
    without needing a publicly accessible URL (relative /media/ paths won't work).

    Returns (success: bool, discord_message_id: str, error: str).
    """
    embed = {
        "title": headline,
        "description": body,
        "color": 0xE63946,
    }

    # When attaching an image we tell Discord to reference the attachment
    # by the fixed name "upload.png" which matches the file part below.
    if image_path:
        embed["image"] = {"url": "attachment://upload.png"}

    payload = {"embeds": [embed]}

    url = connection.webhook_url + "?wait=true"

    try:
        if image_path:
            import json

            with open(image_path, "rb") as fh:
                file_bytes = fh.read()

            # Guess mime type from extension
            import mimetypes

            mime, _ = mimetypes.guess_type(image_path)
            mime = mime or "image/png"

            files = {
                "file": ("upload.png", file_bytes, mime),
                "payload_json": (None, json.dumps(payload), "application/json"),
            }
            resp = requests.post(url, files=files, timeout=30)
        else:
            resp = requests.post(url, json=payload, timeout=10)

        resp.raise_for_status()
        data = resp.json()
        connection.status = ConnectionStatus.OK
        connection.status_message = "Last send successful."
        connection.save(update_fields=["status", "status_message", "updated_at"])
        return True, str(data.get("id", "")), ""

    except requests.HTTPError as exc:
        # Capture Discord's response body for actionable error messages
        try:
            detail = exc.response.json()
        except Exception:
            detail = exc.response.text if exc.response else str(exc)
        error_msg = f"HTTP {exc.response.status_code}: {detail}"
        logger.error("Discord send failed for %s: %s", connection.name, error_msg)
        connection.status = ConnectionStatus.ERROR
        connection.status_message = error_msg
        connection.save(update_fields=["status", "status_message", "updated_at"])
        return False, "", error_msg

    except Exception as exc:
        error_msg = str(exc)
        logger.error("Discord send failed for %s: %s", connection.name, exc)
        connection.status = ConnectionStatus.ERROR
        connection.status_message = error_msg
        connection.save(update_fields=["status", "status_message", "updated_at"])
        return False, "", error_msg


def edit_discord_message(
    connection: ConnectionDiscord,
    discord_message_id: str,
    headline: str,
    body: str,
    image_path: str | None = None,
):
    """Edit a previously sent Discord message using the bot token."""
    if not connection.bot_token or not connection.channel_id:
        return False, "Bot token or channel ID not configured."
    embeds = [{"title": headline, "description": body, "color": 0xE63946}]
    if image_path:
        embeds[0]["image"] = {"url": "attachment://upload.png"}
    url = f"https://discord.com/api/v10/channels/{connection.channel_id}/messages/{discord_message_id}"
    headers = {"Authorization": f"Bot {connection.bot_token}"}
    try:
        if image_path:
            import json
            import mimetypes

            with open(image_path, "rb") as fh:
                file_bytes = fh.read()
            mime, _ = mimetypes.guess_type(image_path)
            mime = mime or "image/png"
            files = {
                "file": ("upload.png", file_bytes, mime),
                "payload_json": (
                    None,
                    json.dumps({"embeds": embeds}),
                    "application/json",
                ),
            }
            resp = requests.patch(url, files=files, headers=headers, timeout=30)
        else:
            resp = requests.patch(
                url, json={"embeds": embeds}, headers=headers, timeout=10
            )
        resp.raise_for_status()
        return True, ""
    except Exception as exc:
        logger.error("Discord edit failed for %s: %s", connection.name, exc)
        return False, str(exc)


def dispatch_message(message):
    """
    Dispatch a Message to all enabled connections.
    Creates/updates DeliveryReceipt records.

    Sets message.sent = True only if at least one connection succeeded.
    Sets message.last_error if all connections failed.
    """
    from messaging.models import DeliveryReceipt

    connections = Connection.objects.filter(enabled=True)

    # Resolve the absolute filesystem path to the image file (if any)
    image_path = None
    if message.image:
        try:
            image_path = message.image.path  # absolute path on disk
        except Exception:
            image_path = None

    any_success = False
    errors = []

    for conn in connections:
        concrete = conn.get_concrete()
        success = False
        remote_id = ""
        error_msg = ""

        if concrete.connection_type == "discord":
            success, remote_id, error_msg = send_to_discord(
                concrete, message.headline, message.body, image_path
            )
        else:
            error_msg = f"Unknown connection type: {concrete.connection_type}"

        if success:
            any_success = True
        else:
            errors.append(f"[{conn.name}] {error_msg}")

        DeliveryReceipt.objects.update_or_create(
            message=message,
            connection=conn,
            defaults={
                "success": success,
                "remote_message_id": remote_id,
                "error": error_msg,
            },
        )

    # Only mark sent if at least one destination accepted the message
    if any_success:
        message.sent = True
        message.last_error = ""
    else:
        message.sent = False
        message.last_error = "\n".join(errors) if errors else "No enabled connections."

    message.save(update_fields=["sent", "last_error"])
