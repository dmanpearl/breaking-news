# Discord Connection Setup

Breaking News sends messages to Discord using **Incoming Webhooks**. Each
`ConnectionDiscord` record maps to one webhook URL, which targets a specific
channel in a specific server (Discord calls servers "guilds").

---

## How Discord Webhooks Work

A Discord webhook is a URL that lets an external application POST messages
directly into a channel. The URL itself encodes the webhook's identity and
secret — no bot token or OAuth flow is required.

**Capabilities via webhook:**
- ✅ Send messages (text, embeds, images, GIFs, PDFs)
- ✅ Edit previously sent messages (PATCH same URL + message ID)
- ✅ Delete previously sent messages (DELETE same URL + message ID)
- ❌ Read messages or channel history
- ❌ React to messages

**Time limits:** There are no time limits on editing or deleting a webhook
message. A webhook can update or remove any message it originally sent,
indefinitely, as long as:
1. The message still exists in the channel
2. The webhook itself has not been deleted or revoked
3. The Breaking News database still holds the `remote_message_id` for that delivery

**Edit/delete requires "Can edit sent":** In the admin panel, each
`ConnectionDiscord` has a **Can edit sent** toggle. When disabled (default),
the Update action saves changes locally only — Discord is not touched. Enable
it to allow in-place Discord edits and deletions.

---

## Step-by-Step: Create a Webhook in Discord

### 1 — Open Server Settings

In Discord, right-click your server name in the left sidebar → **Server
Settings**.

### 2 — Go to Integrations → Webhooks

In the left menu under **Apps**, click **Integrations**, then **Webhooks**.

### 3 — Create New Webhook

Click **New Webhook**. Give it a name (e.g. "Breaking News") and select the
channel it should post to (e.g. `#breaking-news`). You can optionally upload
an avatar icon.

### 4 — Copy the Webhook URL

Click **Copy Webhook URL**. The URL looks like:

```
https://discord.com/api/webhooks/1234567890123456789/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Keep this URL private — anyone with it can post to your channel.

### 5 — Add the Connection in Breaking News Admin

1. Log in at `/admin/`
2. Go to **Connections → Discord Connections → Add Discord Connection**
3. Fill in:
   - **Name** — a label for this destination (e.g. "Manpearl #breaking-news")
   - **Webhook URL** — paste the URL from step 4
   - **Enabled** — checked
   - **Can edit sent** — check this if you want edits in Breaking News to
     update the Discord message in-place
4. Click **Save**

### 6 — Test the Connection

```bash
python manage.py test_connections
```

You should see the test message appear in your Discord channel.

---

## Multiple Servers / Channels

Create one `ConnectionDiscord` per channel. Each has its own webhook URL.
Breaking News dispatches every sent message to all enabled connections.

---

## Regenerating or Revoking a Webhook

If a webhook URL is compromised, go back to **Server Settings → Integrations
→ Webhooks**, select the webhook, and click **Delete Webhook** or regenerate
via the URL copy button. Update the `ConnectionDiscord` record in the admin
immediately.

---

## Troubleshooting

| Symptom | Likely Cause |
|---|---|
| `HTTP 404` on send | Webhook was deleted in Discord |
| `HTTP 401` on send | Webhook URL is malformed or truncated |
| Message sends but edit fails | `Can edit sent` is disabled, or `remote_message_id` was not stored (message may have been sent before this feature was added) |
| GIF appears as static image | GIF is being embedded instead of attached — this is a known Discord limitation; Breaking News works around it automatically |
