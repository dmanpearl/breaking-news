"""
Breaking News Public API  —  v1
================================
All endpoints (except /health) require a Bearer token:

    Authorization: Bearer <your_api_key>

Obtain a key from the Breaking News admin panel under API → API Keys.
"""

import asyncio
import json
from datetime import datetime
from typing import Optional

from asgiref.sync import sync_to_async
from django.http import StreamingHttpResponse
from django.utils.dateparse import parse_datetime
from ninja import NinjaAPI, Query
from ninja.errors import HttpError

from messaging.models import Message

from .auth import APIKeyAuth
from .schemas import ErrorSchema, HealthSchema, MessageListSchema, MessageSchema

# ---------------------------------------------------------------------------
# API instance
# ---------------------------------------------------------------------------

api = NinjaAPI(
    title="Breaking News API",
    version="1.0",
    description=(
        "Read-only access to Breaking News messages.\n\n"
        "All endpoints except `/health` require an `Authorization: Bearer <key>` header.\n\n"
        "Contact your Breaking News administrator to obtain an API key."
    ),
    auth=APIKeyAuth(),
    urls_namespace="api",
)

# ---------------------------------------------------------------------------
# Health check (no auth — useful for uptime monitors)
# ---------------------------------------------------------------------------


@api.get(
    "/health",
    auth=None,
    response=HealthSchema,
    summary="Health check",
    tags=["system"],
)
def health(request):
    """Returns `{status: ok}`. No authentication required."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------


@api.get(
    "/messages/latest",
    response={200: MessageSchema, 404: ErrorSchema},
    summary="Get the latest sent message",
    tags=["messages"],
)
def latest_message(request):
    """
    Returns the most recently sent message.

    Only messages with `sent=true` are returned — drafts and failed sends
    are never exposed through the API.
    """
    msg = Message.objects.filter(sent=True).first()
    if not msg:
        raise HttpError(404, "No sent messages found.")
    return msg


@api.get(
    "/messages",
    response={200: MessageListSchema, 400: ErrorSchema},
    summary="List sent messages",
    tags=["messages"],
)
def list_messages(
    request,
    since: Optional[str] = Query(
        None,
        description=(
            "ISO 8601 timestamp — return only messages updated after this time. "
            "Example: `2025-03-01T00:00:00Z`"
        ),
    ),
    limit: int = Query(50, ge=1, le=200, description="Maximum results to return (1–200)."),
    offset: int = Query(0, ge=0, description="Pagination offset."),
):
    """
    Returns a paginated list of sent messages, newest first.

    Use `since` to poll for new messages incrementally — pass the
    `updated_at` of the last message you received and you will only get
    messages that have changed since then.
    """
    qs = Message.objects.filter(sent=True)

    if since:
        parsed = parse_datetime(since)
        if parsed is None:
            raise HttpError(
                400,
                "Invalid `since` value. Use ISO 8601 format, e.g. 2025-03-01T00:00:00Z",
            )
        qs = qs.filter(updated_at__gt=parsed)

    total = qs.count()
    results = list(qs[offset : offset + limit])
    return {"count": total, "results": results}


@api.get(
    "/messages/{message_id}",
    response={200: MessageSchema, 404: ErrorSchema},
    summary="Get a single message by ID",
    tags=["messages"],
)
def get_message(request, message_id: int):
    """
    Returns a single sent message by its numeric ID.

    Returns 404 if the message does not exist or has not been sent.
    """
    try:
        msg = Message.objects.get(pk=message_id, sent=True)
    except Message.DoesNotExist:
        raise HttpError(404, f"Message {message_id} not found.")
    return msg


# ---------------------------------------------------------------------------
# Server-Sent Events (SSE) stream
# ---------------------------------------------------------------------------


def _sse_event(data: dict, event: str = "message") -> str:
    """Format a single SSE event string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _message_to_dict(msg: Message) -> dict:
    """Serialize a Message to a plain dict for SSE payload."""
    image_url = None
    if msg.image:
        try:
            image_url = msg.image.url
        except Exception:
            pass
    return {
        "id": msg.pk,
        "headline": msg.headline,
        "body": msg.body,
        "image_url": image_url,
        "sent": msg.sent,
        "created_at": msg.created_at.isoformat(),
        "updated_at": msg.updated_at.isoformat(),
        "sender": msg.display_sender_full if msg.created_by else None,
    }


def _get_last_sent_id():
    """Return the PK of the most recent sent message, or 0."""
    return Message.objects.filter(sent=True).values_list("id", flat=True).first() or 0


def _get_new_messages(last_id):
    """Return a list of sent messages with PK > last_id, oldest first.
    select_related ensures created_by is loaded in-thread, not lazily in async.
    """
    return list(
        Message.objects.select_related("created_by")
        .filter(sent=True, id__gt=last_id)
        .order_by("id")
    )


# Async-safe wrappers for ORM calls
_async_get_last_sent_id = sync_to_async(_get_last_sent_id)
_async_get_new_messages = sync_to_async(_get_new_messages)


async def _stream_messages(poll_interval: int = 5):
    """
    Async generator that yields SSE-formatted events.

    Sends a `connected` event immediately, then polls the database every
    `poll_interval` seconds (default 5s) for new sent messages.  A `heartbeat`
    event is sent every 30 seconds to keep the connection alive through proxies.

    All ORM access is delegated to sync helper functions wrapped with
    sync_to_async so Django's connection-per-thread rule is respected.
    """
    import time as _time

    yield _sse_event({"message": "Connected to Breaking News stream."}, event="connected")

    last_id = await _async_get_last_sent_id()
    heartbeat_counter = 0

    while True:
        await asyncio.sleep(poll_interval)
        heartbeat_counter += poll_interval

        new_messages = await _async_get_new_messages(last_id)
        for msg in new_messages:
            yield _sse_event(_message_to_dict(msg), event="message")
            last_id = msg.pk

        if heartbeat_counter >= 30:
            yield _sse_event({"ts": _time.time()}, event="heartbeat")
            heartbeat_counter = 0


@api.get(
    "/stream",
    auth=None,  # Auth handled manually below — SSE clients can't set headers in browser
    summary="SSE stream of new messages",
    tags=["stream"],
    response={200: None},
    include_in_schema=True,
)
async def stream_messages(request, key: str = Query(..., description="Your API key.")):
    """
    **Server-Sent Events stream.**

    Establishes a persistent connection and pushes new sent messages
    to the client in real time.

    Because browser `EventSource` cannot set custom headers, authentication
    uses a `?key=<your_api_key>` query parameter instead of the
    `Authorization` header.

    **Client example (JavaScript):**
    ```javascript
    const es = new EventSource(
      'https://www.breakingnewsguys.com/api/v1/stream?key=YOUR_KEY'
    );
    es.addEventListener('message', e => {
      const msg = JSON.parse(e.data);
      console.log(msg.headline, msg.body);
    });
    es.addEventListener('heartbeat', () => console.log('alive'));
    es.addEventListener('connected', e => console.log('ready', e.data));
    ```

    **⚠️ Swagger UI cannot test this endpoint.** Swagger makes a standard
    HTTP request and waits for the full response — it has no concept of a
    streaming connection and will spin forever. Use one of the methods below
    to test SSE:

    **curl — local dev:**
    ```bash
    curl -N "http://127.0.0.1:8000/api/v1/stream?key=YOUR_KEY"
    ```

    **curl — production (always use `www.`):**
    ```bash
    curl -N "https://www.breakingnewsguys.com/api/v1/stream?key=YOUR_KEY"
    ```

    > **Note:** Always use `https://www.breakingnewsguys.com` (with `www`).
    > The apex domain (`breakingnewsguys.com`) redirects via Squarespace and
    > strips query parameters, which breaks the `?key=` authentication.

    **Browser console:**
    ```javascript
    const es = new EventSource('/api/v1/stream?key=YOUR_KEY');
    es.addEventListener('message', e => console.log(JSON.parse(e.data)));
    ```
    """
    _authenticate = sync_to_async(APIKey.authenticate)
    api_key = await _authenticate(key)
    if api_key is None:
        from django.http import HttpResponse

        return HttpResponse("Unauthorized", status=401)

    response = StreamingHttpResponse(
        _stream_messages(),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"  # Disables Nginx/Railway response buffering
    return response


# Import here to avoid circular import
from .models import APIKey  # noqa: E402
