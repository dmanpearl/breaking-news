# Breaking News API

Read-only REST API for pulling Breaking News messages into your own systems.
Built with [Django Ninja](https://django-ninja.dev/) — OpenAPI 3.0 compliant,
with a built-in interactive testing UI.

---

## Base URLs

| Environment | Base URL |
|---|---|
| Local dev | `http://127.0.0.1:8000/api/v1` |
| Production | `https://www.breakingnewsguys.com/api/v1` |

---

## Interactive Docs (Swagger UI)

Django Ninja provides a full Swagger/OpenAPI testing interface out of the box.
No extra setup required.

| Environment | Docs URL |
|---|---|
| Local dev | http://127.0.0.1:8000/api/v1/docs |
| Production | https://www.breakingnewsguys.com/api/v1/docs |

Open the docs URL in your browser. You will see every endpoint with:
- Parameter descriptions and types
- A **Try it out** button to execute live requests
- Request/response schema documentation

To authenticate in the Swagger UI:
1. Click the **Authorize** button (top right, lock icon)
2. In the **HTTPBearer** field enter your API key — just the key itself, no `Bearer` prefix
3. Click **Authorize** then **Close**
4. All subsequent requests from the UI will include your key automatically

---

## Authentication

All endpoints except `/health` require a Bearer token in the
`Authorization` header:

```
Authorization: Bearer YOUR_API_KEY
```

### Obtaining a Key

API keys are managed by a Breaking News administrator:

1. Log into the Breaking News admin panel (`/admin/`)
2. Navigate to **API → API Keys → Add API Key**
3. Enter a label (e.g. `Acme Corp integration`) and optionally link an owner
4. Click **Save**
5. **Copy the key immediately** — it is shown exactly once and cannot be recovered

To revoke a key: find it in the API Keys list and uncheck **Is active**.

---

## Endpoints

### `GET /health`
Health check. No authentication required. Useful for uptime monitors.

```bash
curl https://www.breakingnewsguys.com/api/v1/health
```

Response:
```json
{"status": "ok", "version": "1.0"}
```

---

### `GET /messages/latest`
Returns the most recently sent message.

```bash
curl https://www.breakingnewsguys.com/api/v1/messages/latest \
  -H "Authorization: Bearer YOUR_API_KEY"
```

Response:
```json
{
  "id": 42,
  "headline": "Market opens sharply higher",
  "body": "The S&P 500 gained 1.4% at the open...",
  "image_url": "https://res.cloudinary.com/your-cloud/...",
  "sent": true,
  "created_at": "2025-03-05T14:32:00Z",
  "updated_at": "2025-03-05T14:32:00Z",
  "sender": "David P."
}
```

---

### `GET /messages`
Returns a paginated list of sent messages, newest first.

**Query parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `since` | ISO 8601 string | — | Only return messages updated after this timestamp |
| `limit` | integer (1–200) | 50 | Max results to return |
| `offset` | integer | 0 | Pagination offset |

**Example — all messages:**
```bash
curl "https://www.breakingnewsguys.com/api/v1/messages" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

**Example — incremental sync (poll for new messages):**
```bash
# Pass the updated_at of the last message you received
curl "https://www.breakingnewsguys.com/api/v1/messages?since=2025-03-05T14:32:00Z" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

Response:
```json
{
  "count": 2,
  "results": [
    { "id": 43, "headline": "...", ... },
    { "id": 42, "headline": "...", ... }
  ]
}
```

---

### `GET /messages/{id}`
Returns a single sent message by its numeric ID.

```bash
curl https://www.breakingnewsguys.com/api/v1/messages/42 \
  -H "Authorization: Bearer YOUR_API_KEY"
```

Returns 404 if the message does not exist or was not sent.

---

### `GET /stream` — Server-Sent Events
Establishes a persistent connection. New sent messages are pushed to
the client in real time as they are broadcast.

Because browser `EventSource` cannot set custom headers, this endpoint
authenticates via a `?key=` query parameter instead of the
`Authorization` header.

**JavaScript example:**
```javascript
const es = new EventSource(
  'https://www.breakingnewsguys.com/api/v1/stream?key=YOUR_API_KEY'
);

es.addEventListener('connected', e => {
  console.log('Stream ready:', JSON.parse(e.data).message);
});

es.addEventListener('message', e => {
  const msg = JSON.parse(e.data);
  console.log(`New message: ${msg.headline}`);
  // msg has: id, headline, body, image_url, sent, created_at, updated_at, sender
});

es.addEventListener('heartbeat', e => {
  // Sent every 30 seconds to keep the connection alive
  console.log('Heartbeat', JSON.parse(e.data).ts);
});

es.onerror = err => {
  console.error('Stream error — will auto-reconnect', err);
  // EventSource reconnects automatically after ~3 seconds
};
```

**curl example (local dev):**
```bash
curl -N "http://127.0.0.1:8000/api/v1/stream?key=YOUR_API_KEY"
```

**Event types:**

| Event | When | Payload |
|---|---|---|
| `connected` | Immediately on connection | `{"message": "Connected to Breaking News stream."}` |
| `message` | Each new sent message | Full message object (same schema as REST endpoints) |
| `heartbeat` | Every 30 seconds | `{"ts": 1234567890.0}` |

**⚠️ Railway / production note:**
The SSE stream requires a persistent HTTP connection. Railway's Hobby plan
closes connections after ~60 seconds. For production SSE, upgrade to
Railway Pro where the request timeout is configurable.

For Hobby plan or environments that close long-lived connections,
use the polling pattern with `/messages?since=<timestamp>` instead.

---

## Polling Pattern (recommended for most integrations)

For simple integrations, polling `/messages/latest` or
`/messages?since=...` every 30–60 seconds is reliable, stateless, and
works everywhere:

```python
import time
import requests

API_BASE = "https://www.breakingnewsguys.com/api/v1"
HEADERS = {"Authorization": "Bearer YOUR_API_KEY"}

last_updated = None

while True:
    if last_updated:
        r = requests.get(
            f"{API_BASE}/messages",
            params={"since": last_updated, "limit": 10},
            headers=HEADERS,
        )
        data = r.json()
        for msg in data["results"]:
            print(f"[NEW] {msg['headline']}")
            last_updated = msg["updated_at"]
    else:
        r = requests.get(f"{API_BASE}/messages/latest", headers=HEADERS)
        if r.status_code == 200:
            msg = r.json()
            print(f"[LATEST] {msg['headline']}")
            last_updated = msg["updated_at"]

    time.sleep(30)
```

---

## Errors

| Status | Meaning |
|---|---|
| `401` | Missing or invalid API key |
| `404` | Message not found or not yet sent |
| `400` | Invalid query parameter (e.g. malformed `since` timestamp) |

Error response body:
```json
{"detail": "Human-readable error message"}
```
