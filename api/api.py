"""
Breaking News Public API  —  v1
================================
All endpoints (except /health) require a Bearer token:

    Authorization: Bearer <your_api_key>

Obtain a key from the Breaking News admin panel under API → API Keys.
"""

import json
import time
from datetime import datetime
from typing import Optional

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


def _stream_messages(poll_interval: int = 5):
    """
    Generator that yields SSE-formatted events.

    Sends a `connected` event immediately on connection, then polls the
    database every `poll_interval` seconds for new sent messages and pushes
    them to the client as `message` events.

    Also sends a `heartbeat` event every 30 seconds to keep the connection
    alive through proxies and load balancers.

    NOTE: This is a polling-based SSE implementation. It does not require
    Django Channels or Redis. The trade-off is a delivery latency equal to
    `poll_interval` seconds (default 5s). For true zero-latency push,
    Django Channels + Redis would be needed.
    """
    # Send connected event immediately
    yield _sse_event({"message": "Connected to Breaking News stream."}, event="connected")

    last_id = (
        Message.objects.filter(sent=True).values_list("id", flat=True).first() or 0
    )
    heartbeat_counter = 0

    while True:
        time.sleep(poll_interval)
        heartbeat_counter += poll_interval

        # Check for new sent messages since last seen ID
        new_messages = Message.objects.filter(sent=True, id__gt=last_id).order_by("id")
        for msg in new_messages:
            yield _sse_event(_message_to_dict(msg), event="message")
            last_id = msg.pk

        # Heartbeat every 30 seconds to prevent proxy timeout
        if heartbeat_counter >= 30:
            yield _sse_event({"ts": time.time()}, event="heartbeat")
            heartbeat_counter = 0


@api.get(
    "/stream",
    auth=None,  # Auth handled manually below — SSE clients can't set headers in browser
    summary="SSE stream of new messages",
    tags=["stream"],
    response={200: None},
    include_in_schema=True,
)
def stream_messages(request, key: str = Query(..., description="Your API key.")):
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

    **⚠️ Railway note:** persistent connections require the Pro plan
    (configurable request timeout). On the Hobby plan, the connection will
    be closed after ~60 seconds. For Hobby plan deployments, use the
    polling endpoints (`/messages/latest` or `/messages?since=...`) instead.
    """
    # Manual auth for SSE — key comes from query param
    api_key = APIKey.authenticate(key)
    if api_key is None:
        from django.http import HttpResponse

        return HttpResponse("Unauthorized", status=401)

    response = StreamingHttpResponse(
        _stream_messages(),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"  # Disables Nginx response buffering
    return response


# Import here to avoid circular import
from .models import APIKey  # noqa: E402
