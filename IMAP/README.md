# OpenMailBot IMAP Monitor - Setup Guide

## Overview

The IMAP monitor bot enables automatic email labeling for up to 100 Gmail users by:

1. **Monitoring Gmail inboxes** via IMAP (checks every minute)
2. **Fetching new emails** and formatting them for the label pipeline
3. **Calling the agent** `/api/label-email-async` endpoint
4. **Processing concurrently** using ThreadPoolExecutor (10 workers by default)

## Architecture

```
┌─────────────────────┐
│  Gmail IMAP Server  │
│  (imap.gmail.com)   │
└──────────┬──────────┘
           │
           │ IMAP Connection (per user)
           │
┌──────────▼──────────────────────────────────────┐
│  IMAP Monitor Bot (app.py)                      │
│  • Connects to 100 users via IMAP               │
│  • Fetches UNSEEN emails from last 2 minutes    │
│  • Formats emails for label pipeline            │
│  • ThreadPoolExecutor (10 concurrent workers)   │
└──────────┬──────────────────────────────────────┘
           │
           │ HTTP POST /api/label-email-async
           │ {user_id, thread_id, messages, access_token}
           │
┌──────────▼──────────────────────────────────────┐
│  OpenMailBot Agent (main.py)                    │
│  • Email Preprocessing Pipeline                 │
│  • Label Pipeline (LLM-based classification)    │
│  • Gmail REST API (applies label)               │
└─────────────────────────────────────────────────┘
           │
           │ Gmail REST API
           │ POST /gmail/v1/users/me/threads/{id}/modify
           │
┌──────────▼──────────────────────────────────────┐
│  Gmail (User's Mailbox)                         │
│  • Label applied automatically                  │
│  • Colored label visible in sidebar             │
└─────────────────────────────────────────────────┘
```

## Files Created/Modified

### 1. `openmailbot/openmailbot/IMAP experiment/app.py`
**NEW** - IMAP monitoring bot that processes 100 users concurrently

### 2. `openmailbot/openmailbot/addon/Code.gs`
**MODIFIED** - Added `createOpenMailBotLabels()` function to create labels on installation

## Setup Instructions

### Step 1: Configure IMAP Bot (app.py)

1. **Edit user configuration:**

```python
USERS = [
    {
        "email": "user1@gmail.com",
        "imap_password": "xxxx xxxx xxxx xxxx",  # Gmail app-specific password
        "access_token": "ya29.xxx",  # OAuth token from Apps Script
    },
    {
        "email": "user2@gmail.com",
        "imap_password": "yyyy yyyy yyyy yyyy",
        "access_token": "ya29.yyy",
    },
    # Add up to 100 users...
]
```

2. **Set agent URL:**

```python
AGENT_URL = "http://localhost:5051"  # Or your public agent URL
```

3. **Adjust performance settings (optional):**

```python
MAX_WORKERS = 10  # Concurrent user processing (increase for faster processing)
CHECK_INTERVAL_SECONDS = 60  # Check every 1 minute
NEW_EMAIL_WINDOW_MINUTES = 2  # Only process emails from last 2 minutes
```

### Step 2: Get Gmail App-Specific Passwords

For each user:

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable **2-Step Verification** (required)
3. Go to **App passwords**
4. Select app: **Mail**
5. Select device: **Other** (enter "OpenMailBot")
6. Click **Generate**
7. Copy the 16-character password (format: `xxxx xxxx xxxx xxxx`)
8. Use this as `imap_password` in app.py

### Step 3: Get OAuth Access Tokens

#### Option A: From Gmail Add-on (Recommended)

Users install the Gmail Add-on, which handles OAuth automatically. The bot can then use:

```javascript
// In Apps Script (Code.gs)
var accessToken = ScriptApp.getOAuthToken();
```

The add-on would need to send this token to your backend/database where app.py can read it.

#### Option B: Manual OAuth2 Flow

For standalone deployment without the add-on:

1. Create OAuth2 credentials in [Google Cloud Console](https://console.cloud.google.com/)
2. Use `google-auth` library to get tokens
3. Store tokens in database/config file

**Example using google-auth-oauthlib:**

```python
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
creds = flow.run_local_server(port=0)
access_token = creds.token
```

### Step 4: Enable Gmail Advanced Service (for Add-on)

The label creation function requires Gmail Advanced Service:

1. Open your Apps Script project
2. Click **Resources** → **Advanced Google Services**
3. Find **Gmail API** and toggle it **ON**
4. Click **Google Cloud Platform project** link
5. Enable **Gmail API** in Cloud Console

### Step 5: Install Requirements

```bash
cd "openmailbot/openmailbot/IMAP experiment"
pip install requests
```

IMAP library is built into Python, so no additional installation needed.

### Step 6: Run the Bot

```bash
python app.py
```

**Expected output:**

```
🚀 OpenMailBot IMAP Monitor Starting...
📊 Configuration:
   Users:          2
   Max Workers:    10
   Check Interval: 60s
   Email Window:   2 min
   Agent URL:      http://localhost:5051

🔍 Testing agent connectivity...
✅ Agent is reachable

🔄 Starting monitoring loop...

╔════════════════════════════════════════════════════════════════╗
║         IMAP MONITORING CYCLE START                            ║
╚════════════════════════════════════════════════════════════════╝
Users: 2 | Max Workers: 10
Window: 2 min | Agent: http://localhost:5051

📬 Found 3 new email(s) for user1@gmail.com
📤 Calling label pipeline for user1@gmail.com | Thread: 18d4a5b2c9f1e3a7...
✅ Job queued: 550e8400-e29b-41d4-a716-446655440000 | User: user1@gmail.com
✅ Completed user1@gmail.com: 3/3 jobs queued

╔════════════════════════════════════════════════════════════════╗
║         IMAP MONITORING CYCLE COMPLETE                         ║
╚════════════════════════════════════════════════════════════════╝
Duration:         4.23s
Emails Processed: 3
Jobs Queued:      3
Errors:           0

😴 Sleeping for 55.77s until next cycle...
   Next cycle: #2 at 14:31:00
```

## Gmail Add-on Label Creation

### How It Works

When a user **installs** the Gmail Add-on:

1. `onInstall()` is triggered automatically
2. `createOpenMailBotLabels()` is called
3. All 14 labels are created with colors:
   - Response (blue)
   - FYI (green)
   - Notification (gray)
   - Meeting (purple)
   - Awaiting Reply (yellow)
   - Escalation (red)
   - Hotels (orange)
   - Airline/Airlines (brown)
   - Travel (green)
   - Restaurant (light orange)
   - Booking (blue)
   - Bank (teal)
   - Recruitment (purple)

4. Labels appear in Gmail sidebar immediately
5. The IMAP bot can now apply these labels via the agent

### Testing Label Creation

Test the label creation manually:

1. Open Apps Script editor
2. Run `createOpenMailBotLabels()` function
3. Check **Execution log** for results
4. Open Gmail and verify labels appear in sidebar with correct colors

## Deployment Options

### Option 1: Local Development

Run app.py on your local machine:
- Best for testing with 1-5 users
- Agent must be accessible (use ngrok/pagekite if agent is remote)

### Option 2: Server Deployment

Run on a VPS/server:

```bash
# Install as systemd service (Linux)
sudo nano /etc/systemd/system/openmailbot-imap.service
```

**Service file:**

```ini
[Unit]
Description=OpenMailBot IMAP Monitor
After=network.target

[Service]
Type=simple
User=openmailbot
WorkingDirectory=/opt/openmailbot/IMAP experiment
ExecStart=/usr/bin/python3 app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable openmailbot-imap
sudo systemctl start openmailbot-imap
sudo systemctl status openmailbot-imap
```

### Option 3: Docker Deployment

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY app.py .
RUN pip install requests

CMD ["python", "app.py"]
```

```bash
docker build -t openmailbot-imap .
docker run -d --name imap-monitor openmailbot-imap
```

## Monitoring & Logging

### View Logs

```bash
# Tail logs in real-time
python app.py 2>&1 | tee openmailbot-imap.log

# Or with systemd
sudo journalctl -u openmailbot-imap -f
```

### Adjust Log Level

Edit app.py:

```python
logging.basicConfig(
    level=logging.DEBUG,  # Change to DEBUG for verbose output
    format='%(asctime)s - %(levelname)s - [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
```

## Performance Tuning

### For 100 Users

**Recommended settings:**

```python
MAX_WORKERS = 20  # Process 20 users concurrently
CHECK_INTERVAL_SECONDS = 60  # Check every 1 minute
NEW_EMAIL_WINDOW_MINUTES = 2  # 2-minute window reduces API calls
```

**Expected cycle time:** 5-10 seconds for 100 users

### For Faster Processing

```python
MAX_WORKERS = 50  # WARNING: High API usage!
CHECK_INTERVAL_SECONDS = 30  # Check every 30 seconds
```

**Trade-offs:**
- ✅ Faster email processing (15-30 second latency)
- ❌ Higher IMAP connection load
- ❌ Higher agent load

## Troubleshooting

### Common Issues

#### 1. "Login failed" / "Authentication failed"

**Cause:** Invalid app-specific password or IMAP not enabled

**Fix:**
1. Verify IMAP is enabled: Gmail Settings → Forwarding and POP/IMAP → Enable IMAP
2. Generate a new app-specific password
3. Check for typos in the password (no spaces)

#### 2. "No access_token provided"

**Cause:** OAuth token missing in USERS configuration

**Fix:**
- Ensure each user has a valid `access_token`
- Tokens expire after 1 hour, implement token refresh

#### 3. "❌ Label pipeline failed [401]"

**Cause:** Expired OAuth access token

**Fix:**
- Implement OAuth token refresh logic
- Use refresh tokens to get new access tokens

#### 4. Gmail API quota exceeded

**Cause:** Too many API calls (>25,000/day per user)

**Fix:**
- Increase `CHECK_INTERVAL_SECONDS` to 120 (2 minutes)
- Increase `NEW_EMAIL_WINDOW_MINUTES` to 5
- Reduce `MAX_WORKERS`

#### 5. "Gmail API not enabled" (Add-on)

**Cause:** Gmail Advanced Service not enabled

**Fix:**
1. Apps Script → Resources → Advanced Google Services
2. Enable Gmail API
3. Also enable in Google Cloud Console

## Advanced Features

### Dynamic User Loading

Replace hardcoded USERS list with database/API:

```python
import sqlite3

def load_users_from_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.execute('SELECT email, imap_password, access_token FROM users WHERE active = 1')
    return [{"email": row[0], "imap_password": row[1], "access_token": row[2]} for row in cursor]

USERS = load_users_from_db()
```

### Token Refresh

Implement automatic OAuth token refresh:

```python
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

def refresh_access_token(refresh_token):
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri='https://oauth2.googleapis.com/token',
        client_id='YOUR_CLIENT_ID',
        client_secret='YOUR_CLIENT_SECRET'
    )
    creds.refresh(Request())
    return creds.token
```

### Webhook Integration

Replace polling with Gmail Push Notifications:

1. Set up Cloud Pub/Sub topic
2. Enable Gmail push notifications
3. Receive webhooks instead of polling IMAP

## Security Recommendations

1. **Never commit credentials** to git
   ```bash
   # Add to .gitignore
   echo "app.py" >> .gitignore  # If it contains credentials
   echo "credentials.json" >> .gitignore
   echo "token.json" >> .gitignore
   ```

2. **Use environment variables**
   ```python
   import os
   AGENT_URL = os.getenv('OPENMAILBOT_AGENT_URL', 'http://localhost:5051')
   ```

3. **Encrypt stored tokens**
   - Use Fernet encryption (same as agent's SettingsManager)
   - Store encrypted tokens in database

4. **Restrict IMAP access**
   - Use app-specific passwords (NOT user passwords)
   - Rotate passwords regularly

## Cost Analysis

### Gmail API Quotas (Free Tier)

- **Read requests:** 1 billion/day (shared across all users)
- **Per-user quota:** 25,000/day
- **IMAP connections:** Unlimited (reasonable use)

### Scaling to 1000 Users

**Resources needed:**
- **IMAP connections:** 1000 concurrent (peak load)
- **API calls:** ~1,440/day per user (60 checks/hour × 24 hours)
- **Total:** ~1.4M API calls/day (well within quota)

**Recommended:**
- Use dedicated server (4 CPU, 8GB RAM)
- Increase MAX_WORKERS to 50-100
- Consider sharding (multiple instances)

## Next Steps

1. **Test with 1 user first**
   ```python
   USERS = [{"email": "test@gmail.com", ...}]
   ```

2. **Verify labels are created** in Gmail Add-on

3. **Monitor logs** for errors

4. **Scale up gradually** to 100 users

5. **Set up monitoring** (healthchecks.io, Prometheus, etc.)

6. **Implement token refresh** for production

## Support

For issues or questions:
- Check logs: `python app.py`
- Review agent logs: `/api/job-status/{job_id}`
- Test endpoint: `curl http://localhost:5051/health`
- Verify IMAP: `openssl s_client -connect imap.gmail.com:993`
