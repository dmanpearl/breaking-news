# Breaking News

A Django-based broadcast management system. Compose messages with a headline, body, and image attachment, then dispatch them to all registered destinations simultaneously. Initially supports multiple Discord accounts via webhooks.

---

## Features

- **Multi-destination broadcasting** — send one message to every enabled connection
- **Discord support** — webhook-based delivery; optional bot-token message editing
- **Connection management** — enable/disable, status monitoring, per-connection health
- **Role-based access** — three groups: `visitor` (view-only), `editor` (create/send), `admin` (everything)
- **Inactivity auto-logout** — configurable warning countdown dialog
- **Full message history** — headline list + delivery receipts per destination

---

## Development Setup (Python venv + SQLite)

### Prerequisites

- Python 3.11+
- Git

### 1 — Clone and create virtualenv

```bash
git clone <repo-url> breaking-news
cd breaking-news
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2 — Configure environment

One-time generate SECRET_KEY:
```bash
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

```bash
cp .env.example .env
# Edit .env and set SECRET_KEY
```

### 3 — Database + initial data

```bash
python manage.py migrate
python manage.py seed_groups
python manage.py create_superuser_quick --password yourpassword
```

`seed_groups` creates the **visitor**, **editor**, and **admin** permission groups.

### 4 — Create static dirs and run

```bash
mkdir -p static staticfiles media
python manage.py runserver
```

Visit **http://127.0.0.1:8000/** and log in with `admin` / `yourpassword`.

---

## Django Admin

The admin panel at `/admin/` is the primary place to:

- Add/edit **Discord Connections** (`ConnectionDiscord` model)
  - Paste a Discord Webhook URL
  - Optionally add a Bot Token + Channel ID to enable message editing
  - Toggle **Enabled** and **Can Edit Sent**
- Manage **Users** and assign them to groups
- Adjust **Site Settings** (inactivity timeout)

---

## Management Commands

| Command | Description |
|---|---|
| `seed_groups` | Create visitor / editor / admin permission groups |
| `create_superuser_quick --password X` | Non-interactive superuser creation |
| `list_connections` | Print all connections and their status |
| `test_connections` | Send a test ping to all enabled connections |
| `list_messages [--sent\|--unsent]` | List messages with send status |
| `resend_message <id>` | Resend a specific message by PK |
| `purge_drafts --confirm` | Delete all unsent draft messages |

---

## Deploying to Railway (PostgreSQL)

### Prerequisites

- [Railway CLI](https://docs.railway.app/develop/cli) installed
- Railway account

### 1 — Create a Railway project

```bash
railway login
railway init      # creates a new project
```

### 2 — Add a PostgreSQL database

In the Railway dashboard, click **New** → **Database** → **PostgreSQL**.
Railway will inject `DATABASE_URL` into your service automatically.

### 3 — Set environment variables

In the Railway dashboard → your service → **Variables**, add:

```
SECRET_KEY=<generate a 50+ char random string>
DEBUG=False
ALLOWED_HOSTS=<your-railway-domain>.up.railway.app
```

Leave `DATABASE_URL` managed by Railway (it's set automatically).

### 4 — Deploy

```bash
railway up
```

Railway will run the `startCommand` from `railway.json`:

```
python manage.py migrate && python manage.py collectstatic --no-input && gunicorn breaking_news.wsgi --log-file -
```

### 5 — Seed data on Railway

```bash
railway run python manage.py seed_groups
railway run python manage.py create_superuser_quick --password yourpassword
```

### Switching from SQLite to PostgreSQL locally

Add `dj-database-url` to requirements and set `DATABASE_URL` in your `.env`:

```bash
pip install dj-database-url
echo "DATABASE_URL=postgres://user:pass@localhost:5432/breaking_news" >> .env
```

---

## Project Structure

```
breaking_news/
├── breaking_news/        # Django project config
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── core/                 # User model, SiteSettings, auth
│   ├── models.py
│   ├── context_processors.py
│   └── management/commands/
│       ├── seed_groups.py
│       └── create_superuser_quick.py
├── connections/          # Base Connection + ConnectionDiscord
│   ├── models.py
│   ├── services.py       # Discord dispatch logic
│   └── management/commands/
│       ├── list_connections.py
│       └── test_connections.py
├── messaging/            # Message, DeliveryReceipt, views
│   ├── models.py
│   ├── views.py
│   └── management/commands/
│       ├── list_messages.py
│       ├── resend_message.py
│       └── purge_drafts.py
├── templates/
│   ├── base.html
│   ├── core/
│   └── messaging/
│       ├── layout.html          # Main app shell
│       ├── history_list.html    # Sidebar history partial
│       ├── index.html           # Landing / empty state
│       └── message_view.html    # View / Create / Edit modes
├── static/
│   ├── css/app.css
│   └── js/app.js
├── Procfile
├── railway.json
├── requirements.txt
└── README.md
```

---

## Adding New Connection Types

1. Create a new model subclassing `Connection` (e.g., `ConnectionSlack`)
2. Add a new value to `ConnectionType` choices
3. Implement a `send_to_<platform>` function in `connections/services.py`
4. Register the condition in `dispatch_message()` and `_edit_messages()`
5. Register the model in `connections/admin.py`
