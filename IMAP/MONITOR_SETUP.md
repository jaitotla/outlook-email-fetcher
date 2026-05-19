# 📧 Automated Email Labeling Monitor - Setup Guide

## Overview

This automated email labeling system runs every 1 minute to fetch, classify, and label Gmail emails using AI.

### What This Does

✅ **Continuous Monitoring**: Runs every 1 minute in the background  
✅ **Timestamp Tracking**: Persistent tracking of last run time (starts from -1 minute on first run)  
✅ **AI Classification**: Sends emails to label endpoint for intelligent categorization  
✅ **Automatic Labeling**: Applies labels via IMAP automatically  
✅ **Colored Labels**: Labels are created with colors via Gmail Add-on installation

---

## Quick Start Guide

### Step 1: Configure Credentials

Edit `get_emails.py` (lines 44-46) and set your credentials:

```python
USER_ID = 'patilswapnil1606@gmail.com'    # ← Change to your Gmail
APP_PASSWORD = 'vcjx frxi nwqr kwvu'       # ← Change to your App Password
AGENT_URL = 'http://localhost:5051'        # ← Agent server URL
```

### Step 2: Get Gmail App Password

1. Go to https://myaccount.google.com/security
2. Enable "2-Step Verification" (if not already)
3. Click "App passwords"
4. Select "Mail" → Generate
5. Copy the 16-character password (format: `xxxx xxxx xxxx xxxx`)

### Step 3: Start Agent Server

```bash
cd openmailbot/agent
python main.py
```

Verify it's running: http://localhost:5051

### Step 4: Run Monitor

**Continuous monitoring (recommended):**
```bash
cd "openmailbot/IMAP experiment"
python get_emails.py monitor
```

**Single run (for testing):**
```bash
python get_emails.py
```

---

## How It Works

### Monitoring Cycle (Every 1 Minute)

```
┌─────────────────────────────────────────────┐
│  1. Load Last Run Timestamp                 │
│     File: last_run_timestamp.txt            │
│     First run: -1 minute from now           │
└────────────────┬────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────┐
│  2. Fetch Emails (IMAP)                     │
│     • Query: SINCE {last_run_date}          │
│     • Post-filter: exact timestamp          │
│     • Extract: UID, subject, body, etc.     │
└────────────────┬────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────┐
│  3. Call Label API                          │
│     POST /api/label-email                   │
│     • Payload: user_id, messages            │
│     • Response: label + metadata            │
└────────────────┬────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────┐
│  4. Apply Label (IMAP)                      │
│     • Use X-GM-LABELS extension             │
│     • Label must exist (from Code.gs)       │
└────────────────┬────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────┐
│  5. Save Timestamp                          │
│     Write current time to file              │
└────────────────┬────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────┐
│  6. Wait                                    │
│     Sleep for remaining time (0-60 seconds) │
└────────────────┬────────────────────────────┘
                 │
                 └──► Loop back to step 1
```

### Files Created

- **`last_run_timestamp.txt`**: Stores last run time in ISO format
  ```
  2026-05-04T12:34:56+00:00
  ```

---

## Label Configuration

### Labels Created by Gmail Add-on

When the Gmail Add-on is installed, `Code.gs` creates these labels automatically:

| Label        | Color         | When Applied                          |
|--------------|---------------|---------------------------------------|
| Response     | 🔵 Blue      | Answers to questions                  |
| Fyi          | 🟢 Green     | Info updates (no action needed)       |
| Notification | ⚪ Gray      | Automated system messages             |
| Meeting      | 🟣 Purple    | Meeting invites/schedules             |
| Escalation   | 🔴 Red       | Urgent issues                         |
| Hotels       | 🟠 Orange    | Hotel bookings                        |
| Airline      | 🟤 Brown     | Flight bookings                       |
| Travel       | 🟢 Green     | Travel itineraries                    |
| Restaurant   | 🟠 Orange    | Restaurant reservations               |
| Booking      | 🔵 Blue      | General bookings                      |
| Bank         | 🔵 Teal      | Banking alerts                        |
| Recruitment  | 🟣 Purple    | Job applications                      |

### Label Creation Code

Location: `openmailbot/addon/Code.gs` → `createOpenMailBotLabels()`

This function runs on add-on installation (`onInstall` hook) and creates all labels with colors via Gmail API.

---

## Configuration Options

### Change Monitoring Interval

Default: 1 minute (60 seconds)

Edit `get_emails.py` line 53:
```python
CHECK_INTERVAL_SECONDS = 60  # Change to desired seconds (min: 30)
```

**Warning**: Intervals < 30 seconds may trigger Gmail rate limiting.

### Change Agent URL

Edit `get_emails.py` line 46:
```python
AGENT_URL = 'https://your-agent-server.com'  # Use HTTPS in production
```

---

## Output Examples

### Successful Run

```
================================================================================
🔄 Monitor Cycle Started: 2026-05-04 12:34:56 UTC
================================================================================

📅 Last run: 2026-05-04 12:33:56 UTC
Fetching emails since: 2026-05-04 12:33:56 UTC

Found 2 email(s)

📬 Processing 2 new email(s)...

--- Email 1/2 ---
From: sender@example.com
Subject: Meeting tomorrow
Date: 2026-05-04 12:34:12
🔍 Sending 1 email(s) to label API...
   Thread ID: CAF...@mail.gmail.com
   Endpoint: http://localhost:5051/api/label-email
✅ Label received: meeting (method: rule-based)
🏷️  Applying label 'meeting' to email UID 12345...
✓ Applied label 'meeting' to email UID 12345
✅ Label applied successfully!

--- Email 2/2 ---
From: airline@example.com
Subject: Your flight confirmation
Date: 2026-05-04 12:34:45
🔍 Sending 1 email(s) to label API...
✅ Label received: airlines (method: rule-based)
🏷️  Applying label 'airlines' to email UID 12346...
✓ Applied label 'airlines' to email UID 12346
✅ Label applied successfully!

✅ Processed 2 email(s)
💾 Saved timestamp: 2026-05-04 12:34:56 UTC

================================================================================
✅ Cycle Complete
   Duration: 3.2s
   Next run in: 57s
================================================================================

💤 Sleeping for 57 seconds...
```

### No New Emails

```
================================================================================
🔄 Monitor Cycle Started: 2026-05-04 12:35:56 UTC
================================================================================

📅 Last run: 2026-05-04 12:34:56 UTC
Fetching emails since: 2026-05-04 12:34:56 UTC
No messages found!

Found 0 email(s)

ℹ️  No new emails found
💾 Saved timestamp: 2026-05-04 12:35:56 UTC

================================================================================
✅ Cycle Complete
   Duration: 0.8s
   Next run in: 59s
================================================================================
```

---

## Troubleshooting

### Problem: Monitor won't start

**Error:**
```
ModuleNotFoundError: No module named 'requests'
```

**Solution:**
```bash
pip install requests
```

---

### Problem: IMAP authentication failed

**Error:**
```
imaplib.IMAP4.error: [AUTHENTICATIONFAILED] Invalid credentials
```

**Solutions:**
1. Verify email address is correct
2. Use **App Password**, not your regular Gmail password
3. Enable 2-Step Verification in Google Account
4. Generate a fresh App Password

---

### Problem: No emails fetched

**Symptoms:**
```
Fetching emails since: 2026-05-04 12:00:00 UTC
No messages found!
```

**Possible Causes:**
1. No new emails in inbox since last run
2. Timestamp file has future date (clock skew)
3. Emails are in different folder (not INBOX)

**Solutions:**
1. Send yourself a test email
2. Delete `last_run_timestamp.txt` and restart
3. Check `last_run_timestamp.txt` contents

---

### Problem: Label API returns error

**Error:**
```
❌ Label API error: HTTP 500
   Response: Internal server error
```

**Solutions:**
1. Check agent server is running: `curl http://localhost:5051/health`
2. Verify user settings are configured in agent
3. Check agent logs: `tail -f openmailbot/agent/logs/agent.log`
4. Test endpoint manually:
   ```bash
   curl -X POST http://localhost:5051/api/label-email \
     -H "Content-Type: application/json" \
     -d '{"user_id": "test@example.com", "thread_id": "test", "messages": [...]}'
   ```

---

### Problem: Labels not appearing in Gmail

**Symptoms:**
- Monitor applies labels successfully
- Labels don't show in Gmail sidebar

**Solutions:**
1. **Install Gmail Add-on** to create labels with colors
2. Manually create missing labels:
   - Gmail Settings → Labels → Create new label
3. Verify label names match exactly (case-sensitive)
4. Check Gmail "Labels" section in sidebar (may need to scroll)

---

### Problem: Monitor stops unexpectedly

**Symptoms:**
```
🛑 Monitoring stopped by user (Ctrl+C)
```
(but you didn't press Ctrl+C)

**Solutions:**
1. Check terminal for errors before the stop message
2. Review last few lines of output
3. Test single run: `python get_emails.py`
4. Check network connectivity
5. Restart monitor with logging:
   ```bash
   python get_emails.py monitor 2>&1 | tee monitor.log
   ```

---

## Advanced Topics

### Running as Background Service

**Linux/Mac (systemd):**

Create `/etc/systemd/system/email-monitor.service`:
```ini
[Unit]
Description=OpenMailBot Email Monitor
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/openmailbot/IMAP experiment
ExecStart=/usr/bin/python3 get_emails.py monitor
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable email-monitor
sudo systemctl start email-monitor
sudo systemctl status email-monitor
```

**Windows (nssm):**
```powershell
nssm install EmailMonitor "C:\Python312\python.exe" "C:\path\to\get_emails.py monitor"
nssm start EmailMonitor
```

---

### Multi-User Support

To monitor multiple Gmail accounts:

1. Create separate copies of `get_emails.py` with different credentials
2. Run each in separate terminal/process
3. Each maintains its own timestamp file

Example directory structure:
```
IMAP experiment/
├── get_emails_user1.py        # USER_ID = 'user1@gmail.com'
├── get_emails_user2.py        # USER_ID = 'user2@gmail.com'
├── last_run_timestamp_user1.txt
├── last_run_timestamp_user2.txt
```

Or use environment variables:
```bash
# Terminal 1
export USER_ID="user1@gmail.com"
export APP_PASSWORD="xxxx xxxx xxxx xxxx"
python get_emails.py monitor

# Terminal 2
export USER_ID="user2@gmail.com"
export APP_PASSWORD="yyyy yyyy yyyy yyyy"
python get_emails.py monitor
```

---

## Known Issues

### ⚠️ Label Mismatch

**Issue**: Some labels defined in `Code.gs` are not in the classification pipeline

**Labels Returned by Classification**:
- response, FYI, Notification, meeting, Escalation
- hotels, airlines, travel, restaurant, booking, bank
- Insurance, Other

**Labels NOT Returned** (created by Code.gs but never used):
- ❌ **Awaiting Reply**
- ❌ **Recruitment**

**Impact**: 
- Recruitment emails may be labeled as "response" or "Other"
- No emails will receive "Awaiting Reply" label

**Workaround**: 
Manually apply these labels in Gmail if needed, or add them to the classification pipeline.

---

### 🔧 IMAP Color Limitation

**Issue**: IMAP can apply labels but cannot set colors

**Why**: IMAP protocol has no concept of label colors

**Solution**: 
- Labels MUST be created via Gmail API first (done by `Code.gs`)
- Colors are set during label creation
- IMAP only associates existing labels with emails

---

## Performance Notes

### Resource Usage (per monitor process)
- **Memory**: ~50-100 MB
- **CPU**: <1% idle, ~5-10% during fetch
- **Network**: ~50 KB per email fetched
- **Disk**: 1 small text file (timestamp)

### Scaling Limits
- **<1,000 emails/day**: ✅ Single monitor works great
- **1,000-5,000 emails/day**: ⚠️ Consider batching by thread
- **>5,000 emails/day**: ⛔ Use Gmail Push Notifications instead

---

## Security Best Practices

1. **Never commit credentials** to Git
   ```bash
   # Add to .gitignore:
   get_emails.py  # After configuring
   last_run_timestamp.txt
   ```

2. **Use App Passwords** (not main password)
   - Revocable without changing main password
   - Limited scope

3. **Secure file permissions**
   ```bash
   chmod 600 last_run_timestamp.txt
   ```

4. **Use HTTPS in production**
   ```python
   AGENT_URL = 'https://your-agent.com'  # Not http://
   ```

---

## Testing Checklist

Before deploying to production:

- [ ] Test single run: `python get_emails.py`
- [ ] Verify agent is reachable
- [ ] Send test email and confirm it's labeled
- [ ] Check Gmail sidebar shows colored labels
- [ ] Test monitor mode for 5 minutes
- [ ] Verify timestamp file is updated
- [ ] Test error handling (disconnect agent, observe recovery)
- [ ] Review logs for warnings/errors

---

## Support & Documentation

- **Agent API Docs**: `../docs/API.md`
- **Gmail Add-on Setup**: `../addon/README.md`
- **Label Pipeline**: `../agent/services/label_pipeline.py`

---

## Changelog

### v1.0.0 (2026-05-04)
- ✅ Initial release
- ✅ 1-minute continuous monitoring
- ✅ Timestamp persistence
- ✅ IMAP fetching + labeling
- ✅ Label API integration
- ✅ Comprehensive error handling

---

**Made with ❤️ by OpenMailBot Team**
