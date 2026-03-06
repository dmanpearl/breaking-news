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
import os

import requests

from .models import Connection, ConnectionDiscord, ConnectionSlack, ConnectionStatus

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


def _fetch_attachment(field) -> tuple[bytes, str]:
    """Return (file_bytes, mime_type) for a Django FieldFile.

    Reads the file through Django's storage backend, which means:
      - Local (runserver): reads directly from MEDIA_ROOT — no HTTP.
      - Railway (Cloudinary): uses the Cloudinary SDK with API credentials
        via storage._open(), avoiding unauthenticated HTTP fetches that can
        return 401 on raw/private resources.

    MIME is derived from the stored filename (reliable for both environments
    because the original filename with extension is always preserved in the
    field's name attribute and in the Cloudinary public_id for raw resources).
    """
    import mimetypes
    file_bytes = field.read()
    # Rewind so the field is still usable after this call
    try:
        field.seek(0)
    except Exception:
        pass
    mime, _ = mimetypes.guess_type(field.name or "")
    if not mime:
        # Last resort: sniff the first 4 bytes for common magic numbers
        if file_bytes[:4] == b"%PDF":
            mime = "application/pdf"
        elif file_bytes[:6] in (b"GIF87a", b"GIF89a"):
            mime = "image/gif"
        elif file_bytes[:8] == b"\x89PNG\r\n\x1a\n":
            mime = "image/png"
        elif file_bytes[:2] in (b"\xff\xd8", b"\xff\xe0", b"\xff\xe1"):
            mime = "image/jpeg"
        else:
            mime = "image/png"
    return file_bytes, mime


def _build_embed(headline: str, body: str, attachment_name: str | None = None,
                 is_gif: bool = False) -> dict:
    # Discord rejects embeds with empty string fields — omit title/description
    # entirely when blank rather than sending "title": "".
    embed: dict = {"color": 0xE63946}
    if headline:
        embed["title"] = headline
    if body:
        embed["description"] = body
    # GIFs and PDFs must NOT be referenced inside the embed image field.
    # GIF: Discord strips animation, showing only the first frame.
    # PDF: Discord cannot render PDFs as embed images at all.
    # Both are sent as bare file attachments; Discord handles them natively
    # (GIF animates; PDF appears as a download card below the embed).
    if attachment_name and not is_gif:
        embed["image"] = {"url": f"attachment://{attachment_name}"}
    # Discord requires at least one non-color field in an embed.
    # This should never be reached because form validation prevents empty messages,
    # but guard here so a malformed call fails loudly rather than silently.
    if len(embed) == 1:  # only "color" key
        embed["description"] = "​"  # zero-width space — invisible but valid
    return embed


def _make_files_payload(file_bytes: bytes, mime: str, payload: dict, filename: str | None = None) -> dict:
    """Return a requests multipart files dict from pre-fetched image bytes.

    Accepts bytes + mime directly so callers that already fetched the image
    (to determine mime/gif status) don't fetch it a second time.
    filename should be the bare filename (no path) to send to Discord.
    """
    ext = _MIME_TO_EXT.get(mime, ".png")
    if not filename:
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
    image_field=None,
) -> tuple[bool, str, str]:
    """
    Send a new message via Discord webhook.

    ?wait=true makes Discord return the full message JSON so we can store
    the message ID for future edits.

    Returns (success, discord_message_id, error_message).
    """
    if image_field:
        _img_bytes, _mime = _fetch_attachment(image_field)
        _ext = _MIME_TO_EXT.get(_mime, ".png")
        attachment_name = os.path.basename(image_field.name) or f"upload{_ext}"
        gif = (_mime in _BARE_ATTACHMENT_MIMES)
    else:
        _img_bytes, _mime = None, None
        attachment_name = None
        gif = False
    embed = _build_embed(headline, body, attachment_name=attachment_name, is_gif=gif)
    payload = {"embeds": [embed]}
    url = _webhook_base_url(connection.webhook_url) + "?wait=true"

    try:
        if image_field:
            resp = requests.post(
                url, files=_make_files_payload(_img_bytes, _mime, payload, filename=attachment_name), timeout=30
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
    image_field=None,
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
    if image_field:
        _img_bytes, _mime = _fetch_attachment(image_field)
        _ext = _MIME_TO_EXT.get(_mime, ".png")
        attachment_name = os.path.basename(image_field.name) or f"upload{_ext}"
        gif = (_mime in _BARE_ATTACHMENT_MIMES)
    else:
        _img_bytes, _mime = None, None
        attachment_name = None
        gif = False
    embed = _build_embed(headline, body, attachment_name=attachment_name, is_gif=gif)
    payload = {"embeds": [embed]}

    # Discord PATCH attachment handling:
    #   image present  → include attachments:[{id:0}] so Discord REPLACES slot 0
    #                    with the new file[0] upload, instead of appending a 2nd copy.
    #   no image       → include attachments:[] to explicitly clear any old attachment.
    # Without one of these, Discord keeps the old attachment AND adds the new one.
    if image_field:
        payload["attachments"] = [{"id": 0}]
    else:
        payload["attachments"] = []

    try:
        if image_field:
            resp = requests.patch(
                edit_url,
                files=_make_files_payload(_img_bytes, _mime, payload, filename=attachment_name),
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


def delete_discord_webhook_message(
    connection: ConnectionDiscord,
    discord_message_id: str,
) -> tuple[bool, str]:
    """
    Delete a previously sent Discord webhook message.

    Uses DELETE /webhooks/{id}/{token}/messages/{message_id}.
    No bot token required — the webhook URL encodes the credentials.
    There is no time limit on deleting a webhook-owned message.

    Returns (success, error_message).
    """
    if not discord_message_id:
        return (
            False,
            "No Discord message ID stored — cannot delete.",
        )

    delete_url = (
        f"{_webhook_base_url(connection.webhook_url)}/messages/{discord_message_id}"
    )

    try:
        resp = requests.delete(delete_url, timeout=10)
        resp.raise_for_status()
        return True, ""

    except requests.HTTPError as exc:
        error_msg = _parse_http_error(exc)
        logger.error(
            "Discord delete failed for %s msg %s: %s",
            connection.name,
            discord_message_id,
            error_msg,
        )
        return False, error_msg

    except Exception as exc:
        error_msg = str(exc)
        logger.error(
            "Discord delete failed for %s msg %s: %s",
            connection.name,
            discord_message_id,
            exc,
        )
        return False, error_msg


# Result status codes for delete_sent_messages (mirrors edit pattern)
DELETE_OK = "ok"
DELETE_FAILED = "failed"
DELETE_SKIPPED_NO_ID = "skipped_no_id"
DELETE_SKIPPED_NOT_SENT = "skipped_not_sent"


def delete_sent_messages(message) -> dict[str, tuple[str, str]]:
    """
    For a message that has been sent, attempt to delete it from every Discord
    and Slack destination using the stored remote_message_id.

    Returns {connection_name: (status_code, detail_string)}.
    Status codes: DELETE_OK, DELETE_FAILED, DELETE_SKIPPED_NO_ID, DELETE_SKIPPED_NOT_SENT.
    """
    from messaging.models import DeliveryReceipt

    results = {}
    receipts = DeliveryReceipt.objects.filter(
        message=message, success=True
    ).select_related("connection")

    for receipt in receipts:
        concrete = receipt.connection.get_concrete()

        if concrete.connection_type not in ("discord", "slack"):
            continue

        if not receipt.remote_message_id:
            results[concrete.name] = (
                DELETE_SKIPPED_NO_ID,
                "No message ID stored — cannot delete.",
            )
            continue

        if concrete.connection_type == "discord":
            ok, err = delete_discord_webhook_message(
                concrete,
                receipt.remote_message_id,
            )
        else:  # slack
            ok, err = delete_slack_message(
                concrete,
                receipt.remote_message_id,
            )

        if ok:
            results[concrete.name] = (DELETE_OK, "")
        else:
            results[concrete.name] = (DELETE_FAILED, err)

    return results


# ── Slack ─────────────────────────────────────────────────────────────────────

_SLACK_POST_URL = "https://slack.com/api/chat.postMessage"
_SLACK_UPDATE_URL = "https://slack.com/api/chat.update"
_SLACK_DELETE_URL = "https://slack.com/api/chat.delete"
_SLACK_GET_UPLOAD_URL = "https://slack.com/api/files.getUploadURLExternal"
_SLACK_COMPLETE_UPLOAD_URL = "https://slack.com/api/files.completeUploadExternal"


def _slack_headers(bot_token: str) -> dict:
    # Only Authorization here. Content-Type is set per-request because it varies:
    #   - chat.postMessage / completeUploadExternal → application/json  (json= kwarg)
    #   - getUploadURLExternal                      → application/x-www-form-urlencoded  (data= kwarg)
    # requests sets the correct Content-Type automatically when you use json= or data=,
    # so we must NOT override it here or Step 1 will silently fail with ok:false.
    return {
        "Authorization": f"Bearer {bot_token}",
    }


def _build_slack_blocks(headline: str, body: str) -> list:
    """
    Build a Slack Block Kit payload from headline and body.

    Headline → bold header section.
    Body     → plain text section.
    At least one block is always present.
    """
    blocks = []
    if headline:
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{headline}*"},
            }
        )
    if body:
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": body},
            }
        )
    if not blocks:
        # Guard: form validation prevents this, but be safe.
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "\u200b"},  # zero-width space
            }
        )
    return blocks


def _parse_slack_error(resp: "requests.Response") -> str:
    """Return a human-readable error string from a Slack API response."""
    try:
        data = resp.json()
        return data.get("error", resp.text)
    except Exception:
        return resp.text



def _slack_upload_file(
    bot_token: str,
    channel_id: str,
    file_bytes: bytes,
    filename: str,
    mime: str,
) -> tuple[bool, str, str]:
    """
    Upload a file to Slack using the 3-step external upload flow required
    since May 2024 (files.upload is fully deprecated as of March 11, 2025).

    Steps:
      1. POST files.getUploadURLExternal  ->  upload_url + file_id
      2. POST raw bytes to upload_url     ->  HTTP 200
      3. POST files.completeUploadExternal with file_id + channel_id

    The filename passed here is the bare filename (e.g. "myreport.pdf").
    Slack preserves it as the download name when users click Download.

    Returns (success, file_id, error_message).
    """
    headers = _slack_headers(bot_token)

    # Step 1: get a one-time upload URL
    try:
        resp1 = requests.post(
            _SLACK_GET_UPLOAD_URL,
            headers=headers,
            data={
                "filename": filename,
                "length": len(file_bytes),
            },
            timeout=10,
        )
        resp1.raise_for_status()
        data1 = resp1.json()
        if not data1.get("ok"):
            return False, "", data1.get("error", "getUploadURLExternal failed")
        upload_url = data1["upload_url"]
        file_id = data1["file_id"]
    except Exception as exc:
        return False, "", f"getUploadURLExternal: {exc}"

    # Step 2: POST file bytes to the pre-signed upload URL as multipart form data.
    # Do NOT send the Authorization header here — Slack's pre-signed URL
    # rejects extra auth headers with a 400 error.
    # Must use multipart (files= kwarg) with the filename so Slack's CDN can
    # register the mimetype/filetype. Sending raw bytes (data=) causes Slack to
    # record mimetype='' and filetype='', which prevents the file from being
    # shared to the channel in step 3.
    try:
        resp2 = requests.post(
            upload_url,
            files={"filename": (filename, file_bytes, mime)},
            timeout=60,
        )
        if resp2.status_code != 200:
            return False, "", (
                f"Slack CDN upload failed: HTTP {resp2.status_code} — {resp2.text}"
            )
    except Exception as exc:
        return False, "", f"Slack CDN upload: {exc}"

    # Step 3: finalize and share to the channel.
    try:
        resp3 = requests.post(
            _SLACK_COMPLETE_UPLOAD_URL,
            headers=headers,
            json={
                "files": [{"id": file_id, "title": filename}],
                "channel_id": channel_id,
            },
            timeout=15,
        )
        resp3.raise_for_status()
        data3 = resp3.json()
        if not data3.get("ok"):
            return False, "", data3.get("error", "completeUploadExternal failed")
    except Exception as exc:
        return False, "", f"completeUploadExternal: {exc}"

    return True, file_id, ""


def send_to_slack(
    connection: ConnectionSlack,
    headline: str,
    body: str,
    image_field=None,
) -> tuple[bool, str, str]:
    """
    Send a new message via the Slack Web API (chat.postMessage).

    If an image or PDF is attached, it is uploaded first via the 3-step
    files.getUploadURLExternal flow and shared to the channel. The file
    upload is fire-and-forget relative to the text message: if the upload
    fails, the text message is still sent and the error is logged but does
    not mark the overall send as failed (the text always gets through).

    File bytes come from _fetch_attachment(), which reads through Django's
    storage backend — transparently Cloudinary on Railway, local disk in dev.
    The original filename (os.path.basename of the field name) is preserved
    so downloaded files keep their real name in both Slack and Discord.

    Returns (success, slack_ts, error_message).
    slack_ts is stored in DeliveryReceipt.remote_message_id for edit/delete.
    """
    blocks = _build_slack_blocks(headline, body)
    fallback_text = headline or body or "Breaking News"

    payload = {
        "channel": connection.channel_id,
        "text": fallback_text,
        "blocks": blocks,
    }

    try:
        resp = requests.post(
            _SLACK_POST_URL,
            headers=_slack_headers(connection.bot_token),
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("ok"):
            error_msg = data.get("error", "Unknown Slack error")
            logger.error("Slack send failed for %s: %s", connection.name, error_msg)
            connection.status = ConnectionStatus.ERROR
            connection.status_message = error_msg
            connection.save(update_fields=["status", "status_message", "updated_at"])
            return False, "", error_msg

        slack_ts = data.get("ts", "")
        connection.status = ConnectionStatus.OK
        connection.status_message = "Last send successful."
        connection.save(update_fields=["status", "status_message", "updated_at"])

    except requests.HTTPError as exc:
        error_msg = _parse_http_error(exc)
        logger.error("Slack send failed for %s: %s", connection.name, error_msg)
        connection.status = ConnectionStatus.ERROR
        connection.status_message = error_msg
        connection.save(update_fields=["status", "status_message", "updated_at"])
        return False, "", error_msg

    except Exception as exc:
        error_msg = str(exc)
        logger.error("Slack send failed for %s: %s", connection.name, exc)
        connection.status = ConnectionStatus.ERROR
        connection.status_message = error_msg
        connection.save(update_fields=["status", "status_message", "updated_at"])
        return False, "", error_msg

    # Upload attachment after a successful message send.
    # A file upload failure is non-fatal — the message text already delivered.
    if image_field:
        try:
            file_bytes, mime = _fetch_attachment(image_field)
            filename = os.path.basename(image_field.name or "attachment")
            ext = _MIME_TO_EXT.get(mime, "")
            if not filename or filename == "attachment":
                filename = f"attachment{ext}"
            ok_upload, _fid, upload_err = _slack_upload_file(
                connection.bot_token,
                connection.channel_id,
                file_bytes,
                filename,
                mime,
            )
            if not ok_upload:
                logger.error(
                    "Slack file upload failed for %s: %s", connection.name, upload_err
                )
        except Exception as exc:
            logger.error(
                "Slack file upload exception for %s: %s", connection.name, exc
            )

    return True, slack_ts, ""


def edit_slack_message(
    connection: ConnectionSlack,
    slack_ts: str,
    headline: str,
    body: str,
    image_field=None,
) -> tuple[bool, str]:
    """
    Edit a previously sent Slack message in-place via chat.update.

    Note on attachments during edit: chat.update can only modify the text/blocks
    of the original message. It cannot replace or remove files attached in a
    previous send — Slack does not support replacing file attachments via
    chat.update. If the edited message has an attachment, we upload it as a new
    file to the channel (same as send). This matches Discord's edit behaviour
    where the attachment is re-sent alongside the updated text.

    Returns (success, error_message).
    """
    if not slack_ts:
        return (
            False,
            "No Slack message timestamp stored — cannot edit.",
        )

    blocks = _build_slack_blocks(headline, body)
    fallback_text = headline or body or "Breaking News"

    payload = {
        "channel": connection.channel_id,
        "ts": slack_ts,
        "text": fallback_text,
        "blocks": blocks,
    }

    try:
        resp = requests.post(
            _SLACK_UPDATE_URL,
            headers=_slack_headers(connection.bot_token),
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("ok"):
            error_msg = data.get("error", "Unknown Slack error")
            logger.error(
                "Slack edit failed for %s ts %s: %s",
                connection.name,
                slack_ts,
                error_msg,
            )
            return False, error_msg

    except requests.HTTPError as exc:
        error_msg = _parse_http_error(exc)
        logger.error(
            "Slack edit failed for %s ts %s: %s", connection.name, slack_ts, error_msg
        )
        return False, error_msg

    except Exception as exc:
        error_msg = str(exc)
        logger.error(
            "Slack edit failed for %s ts %s: %s", connection.name, slack_ts, exc
        )
        return False, error_msg

    # Upload attachment if present. Non-fatal: text edit already succeeded.
    if image_field:
        try:
            file_bytes, mime = _fetch_attachment(image_field)
            filename = os.path.basename(image_field.name or "attachment")
            ext = _MIME_TO_EXT.get(mime, "")
            if not filename or filename == "attachment":
                filename = f"attachment{ext}"
            ok_upload, _fid, upload_err = _slack_upload_file(
                connection.bot_token,
                connection.channel_id,
                file_bytes,
                filename,
                mime,
            )
            if not ok_upload:
                logger.error(
                    "Slack file upload on edit failed for %s: %s",
                    connection.name,
                    upload_err,
                )
        except Exception as exc:
            logger.error(
                "Slack file upload exception on edit for %s: %s", connection.name, exc
            )

    return True, ""


def delete_slack_message(
    connection: ConnectionSlack,
    slack_ts: str,
) -> tuple[bool, str]:
    """
    Delete a previously sent Slack message via chat.delete.

    Returns (success, error_message).
    """
    if not slack_ts:
        return (
            False,
            "No Slack message timestamp stored — cannot delete.",
        )

    payload = {
        "channel": connection.channel_id,
        "ts": slack_ts,
    }

    try:
        resp = requests.post(
            _SLACK_DELETE_URL,
            headers=_slack_headers(connection.bot_token),
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("ok"):
            error_msg = data.get("error", "Unknown Slack error")
            logger.error(
                "Slack delete failed for %s ts %s: %s",
                connection.name,
                slack_ts,
                error_msg,
            )
            return False, error_msg

        return True, ""

    except requests.HTTPError as exc:
        error_msg = _parse_http_error(exc)
        logger.error(
            "Slack delete failed for %s ts %s: %s",
            connection.name,
            slack_ts,
            error_msg,
        )
        return False, error_msg

    except Exception as exc:
        error_msg = str(exc)
        logger.error(
            "Slack delete failed for %s ts %s: %s", connection.name, slack_ts, exc
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

    any_success = False
    errors = []

    for conn in connections:
        concrete = conn.get_concrete()
        success = False
        remote_id = ""
        error_msg = ""

        if concrete.connection_type == "discord":
            success, remote_id, error_msg = send_to_discord(
                concrete, message.headline, message.body, image_field=message.image or None
            )
        elif concrete.connection_type == "slack":
            success, remote_id, error_msg = send_to_slack(
                concrete, message.headline, message.body, image_field=message.image or None
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

    if not connections:
        # No enabled connections — mark as sent so the message is available
        # via the pull API and the UI shows it as delivered.
        message.sent = True
        message.last_error = ""
    elif any_success:
        message.sent = True
        message.last_error = ""
    else:
        message.sent = False
        message.last_error = "\n".join(errors)

    message.save(update_fields=["sent", "last_error"])


# Result status codes used by update_sent_messages
EDIT_OK = "ok"
EDIT_FAILED = "failed"
EDIT_SKIPPED_DISABLED = "skipped_disabled"  # can_edit_sent is False
EDIT_SKIPPED_NO_ID = "skipped_no_id"  # no stored message ID


def update_sent_messages(message) -> dict[str, tuple[str, str]]:
    """
    For a message that has already been sent, attempt to edit every
    Discord and Slack destination in-place using the stored remote_message_id.

    can_edit_sent = False on a connection means we skip it intentionally
    (the local record is updated but the remote platform is not touched).

    Returns {connection_name: (status_code, detail_string)}.
    Status codes: EDIT_OK, EDIT_FAILED, EDIT_SKIPPED_DISABLED, EDIT_SKIPPED_NO_ID.
    """
    from messaging.models import DeliveryReceipt

    results = {}
    receipts = DeliveryReceipt.objects.filter(
        message=message, success=True
    ).select_related("connection")

    for receipt in receipts:
        concrete = receipt.connection.get_concrete()

        if concrete.connection_type not in ("discord", "slack"):
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
                "No message ID stored — cannot edit.",
            )
            continue

        if concrete.connection_type == "discord":
            ok, err = edit_discord_webhook_message(
                concrete,
                receipt.remote_message_id,
                message.headline,
                message.body,
                image_field=message.image or None,
            )
        else:  # slack
            ok, err = edit_slack_message(
                concrete,
                receipt.remote_message_id,
                message.headline,
                message.body,
                image_field=message.image or None,
            )

        if ok:
            results[concrete.name] = (EDIT_OK, "")
        else:
            results[concrete.name] = (EDIT_FAILED, err)
            receipt.error = f"Edit failed: {err}"
            receipt.save(update_fields=["error"])

    return results
