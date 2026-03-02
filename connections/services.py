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
import requests

from .models import Connection, ConnectionDiscord, ConnectionStatus

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────


# MIME → extension map. Cloudinary strips extensions from public IDs, so the
# URL path has no extension (e.g. .../git_merge_feels_like_cfn3n1). We derive
# the extension from the HTTP Content-Type header, which Cloudinary always
# supplies correctly. Works for images and PDFs.
_MIME_TO_EXT = {
    "image/gif":       ".gif",
    "image/jpeg":      ".jpg",
    "image/jpg":       ".jpg",
    "image/png":       ".png",
    "image/webp":      ".webp",
    "application/pdf": ".pdf",
}

# MIME types sent as bare file attachments (not referenced in embed image field).
# GIF: Discord strips animation when embed-referenced, showing only first frame.
# PDF: Discord cannot render PDFs as embed images at all.
# Both appear as native Discord attachment cards below the embed.
_BARE_ATTACHMENT_MIMES = {"image/gif", "application/pdf"}


def _fetch_image(image_url: str) -> tuple[bytes, str]:
    """Return (file_bytes, mime_type) for an image URL.

    Absolute URL  → fetch from CDN (Cloudinary on Railway).
    Relative URL  → read from local MEDIA_ROOT (runserver).

    MIME detection strategy (in priority order):
      1. HTTP Content-Type header  — accurate for images (Cloudinary sniffs them).
      2. URL path extension        — Cloudinary raw resources (PDFs) return
                                     application/octet-stream as a generic header,
                                     so we fall back to guessing from the URL path.
      3. Hard-coded default        — image/png if all else fails.
    """
    import mimetypes
    import os
    from urllib.parse import urlparse
    from django.conf import settings

    # Vague MIME types that Cloudinary returns for raw resources.
    # Treat these as "unknown" and fall back to URL-path guessing.
    _VAGUE_MIMES = {"application/octet-stream", "binary/octet-stream", ""}

    parsed = urlparse(image_url)
    if parsed.scheme:
        resp = requests.get(image_url, timeout=30)
        resp.raise_for_status()
        mime = resp.headers.get("Content-Type", "").split(";")[0].strip()
        if not mime or mime in _VAGUE_MIMES:
            # Cloudinary raw resources return octet-stream — guess from URL path.
            # For raw resources Cloudinary preserves the original filename in the
            # URL (e.g. .../message_images/report.pdf), so this works reliably.
            guessed, _ = mimetypes.guess_type(parsed.path)
            mime = guessed or "image/png"
        return resp.content, mime
    else:
        rel = parsed.path
        media_url_prefix = settings.MEDIA_URL.rstrip("/")
        if rel.startswith(media_url_prefix):
            rel = rel[len(media_url_prefix):]
        local_path = os.path.join(settings.MEDIA_ROOT, rel.lstrip("/"))
        with open(local_path, "rb") as fh:
            file_bytes = fh.read()
        mime, _ = mimetypes.guess_type(local_path)
        return file_bytes, mime or "image/png"


def _build_embed(headline: str, body: str, attachment_name: str | None = None,
                 is_gif: bool = False) -> dict:
    embed = {"title": headline, "description": body, "color": 0xE63946}
    # GIFs and PDFs must NOT be referenced inside the embed image field.
    # GIF: Discord strips animation, showing only the first frame.
    # PDF: Discord cannot render PDFs as embed images at all.
    # Both are sent as bare file attachments; Discord handles them natively
    # (GIF animates; PDF appears as a download card below the embed).
    if attachment_name and not is_gif:
        embed["image"] = {"url": f"attachment://{attachment_name}"}
    return embed


def _make_files_payload(file_bytes: bytes, mime: str, payload: dict) -> dict:
    """Return a requests multipart files dict from pre-fetched image bytes.

    Accepts bytes + mime directly so callers that already fetched the image
    (to determine mime/gif status) don't fetch it a second time.
    """
    ext = _MIME_TO_EXT.get(mime, ".png")
    filename = f"upload{ext}"
    return {
        "files[0]": (filename, file_bytes, mime),
        "payload_json": (None, json.dumps(payload), "application/json"),
    }


def _parse_http_error(exc: requests.HTTPError) -> str:
    try:
        detail = exc.response.json()
    except Exception:
        detail = exc.response.text if exc.response else str(exc)
    return f"HTTP {exc.response.status_code}: {detail}"


def _webhook_base_url(webhook_url: str) -> str:
    """Strip any query string from a webhook URL."""
    url = webhook_url.rstrip("/")
    return url[: url.index("?")] if "?" in url else url


# ── Public API ────────────────────────────────────────────────────────────────


def send_to_discord(
    connection: ConnectionDiscord,
    headline: str,
    body: str,
    image_url: str | None = None,
) -> tuple[bool, str, str]:
    """
    Send a new message via Discord webhook.

    ?wait=true makes Discord return the full message JSON so we can store
    the message ID for future edits.

    Returns (success, discord_message_id, error_message).
    """
    if image_url:
        _img_bytes, _mime = _fetch_image(image_url)
        _ext = _MIME_TO_EXT.get(_mime, ".png")
        attachment_name = f"upload{_ext}"
        gif = (_mime in _BARE_ATTACHMENT_MIMES)
    else:
        _img_bytes, _mime = None, None
        attachment_name = None
        gif = False
    embed = _build_embed(headline, body, attachment_name=attachment_name, is_gif=gif)
    payload = {"embeds": [embed]}
    url = _webhook_base_url(connection.webhook_url) + "?wait=true"

    try:
        if image_url:
            resp = requests.post(
                url, files=_make_files_payload(_img_bytes, _mime, payload), timeout=30
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
    image_url: str | None = None,
) -> tuple[bool, str]:
    """
    Edit a previously sent Discord webhook message in-place.

    Uses PATCH /webhooks/{id}/{token}/messages/{message_id}.
    No bot token required — the webhook URL already encodes the credentials.

    Returns (success, error_message).
    """
    if not discord_message_id:
        return (
            False,
            "No Discord message ID stored. The original message may have been sent "
            "without ?wait=true, or the receipt was not saved.",
        )

    edit_url = (
        f"{_webhook_base_url(connection.webhook_url)}/messages/{discord_message_id}"
    )
    if image_url:
        _img_bytes, _mime = _fetch_image(image_url)
        _ext = _MIME_TO_EXT.get(_mime, ".png")
        attachment_name = f"upload{_ext}"
        gif = (_mime in _BARE_ATTACHMENT_MIMES)
    else:
        _img_bytes, _mime = None, None
        attachment_name = None
        gif = False
    embed = _build_embed(headline, body, attachment_name=attachment_name, is_gif=gif)
    payload = {"embeds": [embed]}

    # API v10 requires explicitly passing attachments: [] to clear old attachments
    # when re-sending without an image, otherwise the old image stays.
    if not image_url:
        payload["attachments"] = []

    try:
        if image_url:
            resp = requests.patch(
                edit_url,
                files=_make_files_payload(_img_bytes, _mime, payload),
                timeout=30,
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

    Stores the Discord message ID in DeliveryReceipt.remote_message_id so
    future edits can PATCH the same Discord message in-place.
    """
    from messaging.models import DeliveryReceipt

    connections = Connection.objects.filter(enabled=True)

    image_url = None
    if message.image:
        try:
            image_url = message.image.url
        except Exception:
            image_url = None

    any_success = False
    errors = []

    for conn in connections:
        concrete = conn.get_concrete()
        success = False
        remote_id = ""
        error_msg = ""

        if concrete.connection_type == "discord":
            success, remote_id, error_msg = send_to_discord(
                concrete, message.headline, message.body, image_url=image_url
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


# Result status codes used by update_sent_messages
EDIT_OK = "ok"
EDIT_FAILED = "failed"
EDIT_SKIPPED_DISABLED = "skipped_disabled"  # can_edit_sent is False
EDIT_SKIPPED_NO_ID = "skipped_no_id"  # no stored message ID


def update_sent_messages(message) -> dict[str, tuple[str, str]]:
    """
    For a message that has already been sent, attempt to edit every Discord
    destination in-place using the stored remote_message_id.

    can_edit_sent = False on a connection means we skip it intentionally
    (the local record is updated but Discord is not touched).

    Returns {connection_name: (status_code, detail_string)}.
    Status codes: EDIT_OK, EDIT_FAILED, EDIT_SKIPPED_DISABLED, EDIT_SKIPPED_NO_ID.
    """
    from messaging.models import DeliveryReceipt

    image_url = None
    if message.image:
        try:
            image_url = message.image.url
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
            results[concrete.name] = (
                EDIT_SKIPPED_DISABLED,
                "Editing disabled on this connection (can_edit_sent = False).",
            )
            continue

        if not receipt.remote_message_id:
            results[concrete.name] = (
                EDIT_SKIPPED_NO_ID,
                "No Discord message ID stored — cannot edit.",
            )
            continue

        ok, err = edit_discord_webhook_message(
            concrete,
            receipt.remote_message_id,
            message.headline,
            message.body,
            image_url=image_url,
        )

        if ok:
            results[concrete.name] = (EDIT_OK, "")
        else:
            results[concrete.name] = (EDIT_FAILED, err)
            receipt.error = f"Edit failed: {err}"
            receipt.save(update_fields=["error"])

    return results
