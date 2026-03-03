# Slack Connection Setup

Breaking News sends messages to Slack using the **Slack Web API** with a
**Bot User OAuth Token**. Each `ConnectionSlack` record holds a bot token and
a target channel ID.

Slack's simpler "Incoming Webhooks" are intentionally **not used** here
because they are one-way only — they cannot edit or delete messages. The Bot
Token approach gives us full send, edit, and delete capability.

---

## How the Slack Bot Token Approach Works

A Slack app with a **Bot User OAuth Token** (`xoxb-...`) can call Web API
methods on behalf of the bot. Breaking News uses three methods:

| Method | Used for |
|---|---|
| `chat.postMessage` | Sending a new message |
| `chat.update` | Editing a previously sent message |
| `chat.delete` | Deleting a previously sent message |

The `ts` (timestamp) returned by `chat.postMessage` is stored in the
Breaking News database as the message identifier. It is needed for all
subsequent edit and delete operations.

**Required OAuth scope:** `chat:write`

**Time limits:** There are no time limits. A bot can edit or delete any
message it originally posted, indefinitely, as long as the message still
exists in the channel and the token has not been revoked.

**Attachment note:** Slack's file upload API changed in May 2024 and now
requires a multi-step async flow. In this version, file attachments (images,
PDFs) are not uploaded to Slack. If a message has an attachment, a note is
appended to the Slack message body indicating the filename and directing
recipients to view it in Breaking News. Full Slack file upload support may
be added in a future version.

---

## Step-by-Step: Create a Slack App and Get a Bot Token

### 1 — Go to the Slack API Dashboard

Open [https://api.slack.com/apps](https://api.slack.com/apps) and log in with
your Slack account (must be a workspace member).

### 2 — Create a New App

Click **Create New App** → **From scratch**.

- **App Name:** `Breaking News` (or whatever you prefer)
- **Workspace:** Select your workspace (e.g. `Manpearl`)

Click **Create App**.

### 3 — Add the Required Bot Scope

In the left sidebar, go to **OAuth & Permissions**.

Scroll down to **Scopes → Bot Token Scopes** and click **Add an OAuth Scope**.

Add: **`chat:write`**

That single scope is all that is required to send, edit, and delete messages.

### 4 — Install the App to Your Workspace

Still on the **OAuth & Permissions** page, scroll up to **OAuth Tokens for
Your Workspace** and click **Install to Workspace**.

Review the permissions and click **Allow**.

### 5 — Copy the Bot User OAuth Token

After installation, you will see a **Bot User OAuth Token** on the same page:

```
Example: `xoxb-...xxx`
```

Copy this token. Store it securely — treat it like a password. Anyone with
this token can post messages to your workspace as the bot.

### 6 — Get the Channel ID

You need the **channel ID**, not the channel name. Channel names can change;
IDs are permanent.

**In Slack (desktop app or browser):**
1. Right-click the channel name in the sidebar (e.g. `#breaking-news`)
2. Click **View channel details**
3. Scroll to the bottom of the **About** tab
4. Copy the **Channel ID** (looks like `C08ABCDEF12`)

Alternatively, open the channel in your browser — the channel ID is the last
segment of the URL:
```
https://app.slack.com/client/T01XXXXXXX/C08ABCDEF12
                                          ^^^^^^^^^^^^ this part
```

### 7 — Invite the Bot to the Channel

The bot must be a member of the channel before it can post. In Slack, open
the target channel and type:

```
/invite @Breaking News
```

(Replace `Breaking News` with whatever you named your app in step 2.)

You only need to do this once per channel.

### 8 — Add the Connection in Breaking News Admin

1. Log in at `/admin/`
2. Go to **Connections → Slack Connections → Add Slack Connection**
3. Fill in:
   - **Name** — a label for this destination (e.g. "Manpearl #breaking-news")
   - **Bot token** — paste the `xoxb-...` token from step 5
   - **Channel ID** — paste the channel ID from step 6
   - **Enabled** — checked
   - **Can edit sent** — check this if you want edits in Breaking News to
     update the Slack message in-place
4. Click **Save**

### 9 — Test the Connection

```bash
python manage.py test_connections
```

You should see the test message appear in your Slack channel.

---

## Multiple Workspaces / Channels

Each workspace requires its own Slack app installation and bot token. Each
channel in the same workspace can use the same bot token, but requires its
own `ConnectionSlack` record with a different `channel_id`. The bot must be
invited to each channel separately (step 7).

---

## Revoking or Rotating a Token

If a bot token is compromised:
1. Go to [https://api.slack.com/apps](https://api.slack.com/apps) → your app
2. Go to **OAuth & Permissions** → **Revoke All OAuth Tokens**
3. Reinstall the app to generate a new token
4. Update the `ConnectionSlack` record in the Breaking News admin immediately

---

## Troubleshooting

| Symptom | Likely Cause |
|---|---|
| `not_in_channel` error | Bot has not been invited to the channel — run `/invite @YourBotName` in Slack |
| `channel_not_found` error | Channel ID is wrong or the bot token is for a different workspace |
| `invalid_auth` error | Bot token is invalid, revoked, or has been typed incorrectly |
| `missing_scope` error | The `chat:write` scope was not added — re-check step 3 |
| Message sends but edit fails | `Can edit sent` is disabled, or the `ts` was not stored |
| Attachment not visible in Slack | Expected — file upload to Slack is not yet supported; a note appears in the message body instead |
