"""
Dispatcher services – send a Message to all enabled Connections.

Discord webhook editing notes
------------------------------
A webhook can edit any message it originally sent, using the same token
embedded in the webhook URL.  No bot token is required.  The only
prerequisite is that the original POST was made with ?wait=true so Discord
returned the message JSON (including its ID), which we store in
DeliveryReceipt.remote_message_id.

Edit endpoint:
  PATCH /webhooks/{webhook.id}/{webhook.token}/messages/{message.id}

There is no Discord API flag to query whether a message is "editable" — a
webhook message is always editable by the same webhook that sent it, as long
as we have the message ID.  Our own can_edit_sent toggle is a local
permission gate, not a Discord concept.
"""

import json
import logging
import mimetypes

import requests

from .models import Connection, ConnectionDiscord, ConnectionStatus

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _build_embed(headline: str, body: str, with_attachment: bool = False) -> dict:
    embed = {"title": headline, "description": body, "color": 0xE63946}
    if with_attachment:
        # References the multipart file part named "files[0]"
        embed["image"] = {"url": "attachment://upload.png"}
    return embed


def _make_files_payload(image_path: str, payload: dict) -> dict:
    """Return a requests `files` dict for multipart upload."""
    with open(image_path, "rb") as fh:
        file_bytes = fh.read()
    mime, _ = mimetypes.guess_type(image_path)
    mime = mime or "image/png"
    return {
        "files[0]": ("upload.png", file_bytes, mime),
        "payload_json": (None, json.dumps(payload), "application/json"),
    }


def _parse_http_error(exc: requests.HTTPError) -> str:
    try:
        detail = exc.response.json()
    except Exception:
        detail = exc.response.text if exc.response else str(exc)
    return f"HTTP {exc.response.status_code}: {detail}"


# ── Public API ────────────────────────────────────────────────────────────────


def send_to_discord(
    connection: ConnectionDiscord,
    headline: str,
    body: str,
    image_path: str | None = None,
) -> tuple[bool, str, str]:
    """
    Send a new message via Discord webhook.

    Uses ?wait=true so Discord returns the full message JSON including the
    message ID we must store in order to edit the message later.

    Images are uploaded as multipart form data — Discord cannot fetch relative
    /media/ paths, so we push the bytes directly.

    Returns (success, discord_message_id, error_message).
    """
    embed = _build_embed(headline, body, with_attachment=bool(image_path))
    payload = {"embeds": [embed]}
    # ?wait=true is REQUIRED — without it Discord returns 204 No Content and
    # we cannot retrieve the message ID needed for future edits.
    url = connection.webhook_url.rstrip("/") + "?wait=true"

    try:
        if image_path:
            resp = requests.post(
                url, files=_make_files_payload(image_path, payload), timeout=30
            )
        else:
            resp = requests.post(url, json=payload, timeout=10)

        resp.raise_for_status()
        data = resp.json()
        discord_message_id = str(data.get("id", ""))

        connection.status = ConnectionStatus.OK
        connection.status_message = "Last send successful."
        connection.save(update_fields=["status", "status_message", "updated_at"])
        return True, discord_message_id, ""

    except requests.HTTPError as exc:
        error_msg = _parse_http_error(exc)
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


def edit_discord_webhook_message(
    connection: ConnectionDiscord,
    discord_message_id: str,
    headline: str,
    body: str,
    image_path: str | None = None,
) -> tuple[bool, str]:
    """
    Edit a previously sent Discord webhook message in-place.

    Uses the Webhook edit endpoint:
        PATCH /webhooks/{webhook.id}/{webhook.token}/messages/{message.id}

    This does NOT require a bot token — the webhook URL already encodes the
    credentials. The message ID comes from the DeliveryReceipt stored when
    the message was first sent via send_to_discord() with ?wait=true.

    Returns (success, error_message).
    """
    if not discord_message_id:
        return (
            False,
            "No Discord message ID stored — message may not have been sent with ?wait=true.",
        )

    # Build the edit URL from the webhook URL by appending /messages/{id}
    base_url = connection.webhook_url.rstrip("/")
    # Strip any existing query string (e.g. ?wait=true) before appending path
    if "?" in base_url:
        base_url = base_url[: base_url.index("?")]
    edit_url = f"{base_url}/messages/{discord_message_id}"

    embed = _build_embed(headline, body, with_attachment=bool(image_path))
    payload = {"embeds": [embed]}

    try:
        if image_path:
            resp = requests.patch(
                edit_url, files=_make_files_payload(image_path, payload), timeout=30
            )
        else:
            resp = requests.patch(edit_url, json=payload, timeout=10)

        resp.raise_for_status()
        return True, ""

    except requests.HTTPError as exc:
        error_msg = _parse_http_error(exc)
        logger.error(
            "Discord edit failed for %s msg %s: %s",
            connection.name,
            discord_message_id,
            error_msg,
        )
        return False, error_msg

    except Exception as exc:
        error_msg = str(exc)
        logger.error(
            "Discord edit failed for %s msg %s: %s",
            connection.name,
            discord_message_id,
            exc,
        )
        return False, error_msg


def dispatch_message(message) -> None:
    """
    Dispatch a Message to all enabled connections.

    - Creates/updates a DeliveryReceipt per connection.
    - Stores the Discord message ID in DeliveryReceipt.remote_message_id.
    - Sets message.sent = True only when at least one connection succeeded.
    - Sets message.last_error when all connections fail.
    """
    from messaging.models import DeliveryReceipt

    connections = Connection.objects.filter(enabled=True)

    image_path = None
    if message.image:
        try:
            image_path = message.image.path
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

    if any_success:
        message.sent = True
        message.last_error = ""
    else:
        message.sent = False
        message.last_error = "\n".join(errors) if errors else "No enabled connections."

    message.save(update_fields=["sent", "last_error"])


def update_sent_messages(message) -> dict:
    """
    For a message that has already been sent, edit every Discord destination
    that has a stored message ID and has can_edit_sent = True.

    Returns a summary dict: {connection_name: (success, error)}.
    """
    from messaging.models import DeliveryReceipt

    image_path = None
    if message.image:
        try:
            image_path = message.image.path
        except Exception:
            pass

    results = {}
    receipts = DeliveryReceipt.objects.filter(
        message=message, success=True
    ).select_related("connection")

    for receipt in receipts:
        concrete = receipt.connection.get_concrete()
        if concrete.connection_type != "discord":
            continue
        if not concrete.can_edit_sent:
            continue
        if not receipt.remote_message_id:
            results[concrete.name] = (False, "No stored message ID.")
            continue

        ok, err = edit_discord_webhook_message(
            concrete,
            receipt.remote_message_id,
            message.headline,
            message.body,
            image_path,
        )
        results[concrete.name] = (ok, err)

        # Update the receipt error field if the edit failed
        if not ok:
            receipt.error = f"Edit failed: {err}"
            receipt.save(update_fields=["error"])

    return results
