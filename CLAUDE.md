# Breaking News — Claude Context

## What this is
Django ASGI broadcast management system. Editors compose messages and dispatch them simultaneously to Discord (webhooks) and Slack (Bot Token API). Includes a read-only REST API + SSE stream consumed by the sister reader app.

Production: https://www.breakingnewsguys.com
Sister repo: `../breaking-news-reader/` (public GitHub, static web app — separate because it's a public repo)

## Stack
- Django 4.2, Django Ninja (REST API + OpenAPI), uvicorn (ASGI)
- PostgreSQL (Railway), Cloudinary (image/PDF storage), WhiteNoise (static files)
- No Celery — all async work uses Django's async view support

## Django apps
| App | Purpose |
|-----|---------|
| `core` | Custom User model, UserPreferences, SiteSettings (inactivity timeout) |
| `messaging` | Message model, compose/send/edit/delete views, DeliveryReceipt |
| `connections` | ConnectionDiscord, ConnectionSlack — dispatch and edit/delete logic in `services.py` |
| `api` | Read-only REST API, SSE stream, APIKey model (SHA-256 hashed), usage logging |

## Code formatting — mandatory after every edit

After editing **any** file, run the appropriate formatter before finishing:

| File type | Command |
|-----------|---------|
| Python (`.py`) | `source .venv/bin/activate && black <file>` |
| CSS / HTML | `npx prettier --write <file>` |

Run formatters even for single-line changes. The IDE auto-formats on save; if the file is not already formatted, a one-line diff becomes hundreds of lines. The console and IDE may use slightly different formatter versions — that risk is acceptable and far smaller than not formatting at all.

## Dev setup
```bash
source .venv/bin/activate
python manage.py migrate
python manage.py seed_groups          # creates visitor/editor/admin groups
python manage.py create_superuser_quick --password yourpass
python manage.py runserver
```

## Key commands
```bash
python manage.py test --verbosity=1
python manage.py list_connections
python manage.py test_connections     # sends test pings to all enabled connections
python manage.py list_messages [--sent|--unsent]
python manage.py resend_message <id>
```

## Deployment (Railway)
Start command (from `railway.json`):
```
python manage.py migrate && python manage.py seed_groups &&
python manage.py collectstatic --no-input &&
ASGI_THREADS=20 uvicorn breaking_news.asgi:application --host 0.0.0.0 --port $PORT
```

## Key environment variables
| Variable | Notes |
|----------|-------|
| `SECRET_KEY` | Required |
| `DEBUG` | False in production |
| `ALLOWED_HOSTS` | Comma-separated |
| `DATABASE_URL` | Set automatically by Railway |
| `CLOUDINARY_URL` | Falls back to local disk if unset |
| `CORS_ALLOWED_ORIGINS` | Defaults to reader domain + localhost:8080 |
| `ASGI_THREADS` | 20 in production (set in railway.json) |

## Architecture notes

**DB connections:** `conn_max_age=0` — persistent connections disabled. This was deliberately chosen after repeated pool exhaustion under SSE load (see git history around commits 72a4b99, 2d79e2f). Do not change without testing under SSE load.

**Sessions:** `cached_db` backend — reduces per-request DB hits.

**SSE stream** (`api/api.py`): Async generator polls DB every 5s, heartbeat every 30s, closes DB connections between polls. Auth via query param `?key=` (EventSource can't set headers).

**Cloudinary storage** (`breaking_news/storage.py`): Uses `raw` resource type for PDFs, `image` for everything else. Downloads via `private_download_url()`.

**Polling suppression** (`breaking_news/log_filters.py`): `SuppressPollFilter` prevents `/messages/poll/` from flooding logs.

**CORS:** `reader.breakingnewsguys.com` and `*.up.railway.app` are whitelisted for staging deployments of the reader.

**DNS note:** Always use `www.breakingnewsguys.com` for API calls — the apex domain goes through Squarespace which strips query params.

## API endpoints (read-only, Django Ninja)
- `GET /api/v1/health` — no auth required
- `GET /api/v1/messages` — paginated, supports `?since=<iso8601>`
- `GET /api/v1/messages/latest`
- `GET /api/v1/messages/{id}`
- `GET /api/v1/stream?key=<api_key>` — SSE stream
- Swagger UI: `/api/v1/docs`
