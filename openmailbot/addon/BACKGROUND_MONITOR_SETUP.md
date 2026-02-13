# Background Email Monitor - Setup & Usage Guide

## Overview

The **Background Email Monitor** automatically captures incoming emails and attachments in real-time without manual intervention. It runs continuously in the background using Google Apps Script triggers.

### What It Does
- ✅ Monitors incoming emails 24/7
- ✅ Automatically stores all emails and threads
- ✅ Extracts and uploads all attachments
- ✅ Logs messages to the backend server
- ✅ Retries failed uploads automatically
- ✅ Tracks processing statistics
- ✅ Handles errors gracefully

---

## Setup Instructions

### Step 1: Create a Separate Apps Script Project

Unlike the Gmail Add-on (which is manual), the background monitor needs its own Apps Script project:

1. Go to [script.google.com](https://script.google.com)
2. Click **"New Project"**
3. Name it: `"Email Background Monitor"`
4. Copy the entire content from `BackgroundEmailMonitor.gs` into the editor
5. Save the project

### Step 2: Configure Script Properties

The background monitor needs your Flask server URL:

1. In Apps Script editor: **Project Settings** (gear icon)
2. Under **Script Properties**, click **Add property**
3. Set:
   - **Key**: `FLASK_SERVER_URL`
   - **Value**: Your Flask server URL (e.g., `http://43.204.98.38:8000`)
4. Save

### Step 3: Set Up Permissions

The script needs Gmail access. When you run it the first time:

1. In the editor, select `setupTriggers` function
2. Click **Run** ▶️
3. Grant permissions when prompted:
   - Access to Gmail
   - Access to Script Properties
   - Authorization as your email account

### Step 4: Enable Background Triggers

Run this **one time** to activate background monitoring:

```javascript
setupTriggers()
```

This will:
- ✅ Create automatic triggers to run every 5 minutes
- ✅ Enable the monitoring flag
- ✅ Start checking for new emails

You should see in the logs:
```
✅ Background email monitor setup complete!
   Monitoring will check for new emails every 5 minutes
```

---

## Daily Usage

### Monitor is Now Active

Once set up, monitoring runs automatically:
- Checks for new unread emails every **5 minutes**
- Processes up to **50 emails** per check
- Stores all attachments automatically
- Retries failed uploads up to 3 times

### View Monitor Status

```javascript
getMonitorStats()
```

Returns:
```javascript
{
  enabled: true,
  lastRun: {
    threadsProcessed: 5,
    emailsLogged: 12,
    attachmentsStored: 8,
    duration: "2.35s"
  },
  totalRuns: 45
}
```

### View Recent Logs

```javascript
viewMonitorLogs()
```

Shows:
- Last 5 runs with statistics
- Total threads processed
- Any recent errors

---

## Configuration Options

Edit these at the top of `BackgroundEmailMonitor.gs` to customize behavior:

```javascript
const CONFIG = {
  BATCH_SIZE: 50,              // Max emails per check (default: 50)
  CHECK_INTERVAL_MINUTES: 5,   // How often to check (default: 5 min)
  LOOKBACK_HOURS: 24,          // Initial lookback period (default: 24 hrs)
  MAX_RETRIES: 3,              // Retry failed uploads (default: 3)
  RETRY_DELAY_MS: 2000         // Delay between retries (default: 2000 ms)
};
```

---

## Manual Test (Before Full Activation)

Test the monitor before setting up triggers:

```javascript
testBackgroundMonitor()
```

This will:
1. ✅ Verify Flask server URL is configured
2. ✅ Run one monitor iteration
3. ✅ Show what would be processed
4. ✅ Display any errors

Check the execution log for results.

---

## Management Functions

### Stop Monitoring

```javascript
stopMonitor()
```

Disables all triggers and stops background processing.

### Restart Monitoring

```javascript
restartMonitor()
```

Stops and restarts the monitor (useful if it gets stuck).

### Clear All Data

```javascript
clearMonitorData()
```

**WARNING:** Resets all statistics and reprocesses threads.

---

## Troubleshooting

### Issue: "FLASK_SERVER_URL not configured"

**Solution:**
1. Go to Project Settings
2. Add `FLASK_SERVER_URL` property with your server URL
3. Run `testBackgroundMonitor()` to verify

### Issue: Triggers not running

**Solution:**
1. Check that triggers were created:
   - Go to **Triggers** (clock icon) in left sidebar
   - You should see `backgroundEmailMonitor` trigger
2. If missing, run `setupTriggers()` again
3. Check execution logs for errors

### Issue: Attachments not uploading

**Solution:**
1. Run `testBackgroundMonitor()` to diagnose
2. Check that Flask server is running at the configured URL
3. Verify network connectivity
4. Check Flask server logs for API errors

### Issue: Monitoring appears stuck

**Solution:**
```javascript
restartMonitor()
```

This stops and cleanly restarts the monitor.

---

## How It Works Behind the Scenes

### Flow Diagram

```
┌─────────────────────────────────────┐
│ Every 5 minutes (time-based trigger)│
└────────────┬────────────────────────┘
             │
             ▼
    ┌──────────────────────┐
    │ backgroundEmailMonitor│
    └──────────┬───────────┘
             │
    ┌────────┴────────┐
    │                 │
    ▼                 ▼
Get new         Search for
unread          unread emails
emails          after last check
    │                 │
    └────────┬────────┘
             │
             ▼
    ┌──────────────────────┐
    │ For each thread:      │
    ├──────────────────────┤
    │ 1. Get all messages   │
    │ 2. Log to server      │
    │ 3. Extract attachments│
    │ 4. Upload to server   │
    │ 5. Mark as processed  │
    └──────────┬───────────┘
             │
             ▼
    ┌──────────────────────┐
    │ Save statistics      │
    │ Retry failed uploads │
    │ Report errors        │
    └──────────────────────┘
```

### Processing Details

**Per Check (every 5 minutes):**
1. Search Gmail for unread emails after last check time
2. Filter out already-processed threads
3. For each thread (max 50):
   - Extract all messages with full details
   - Send messages array to `/api/log-email`
   - For each message with attachments:
     - Filter out inline attachments
     - Encode attachments as base64
     - Send to `/api/store-attachments`
   - Mark thread as processed
4. Save stats and update last check time

**Retry Logic:**
- If upload fails, retry up to 3 times
- Wait 2 seconds between retries (configurable)
- Log each attempt

---

## Integration with Gmail Add-on

The background monitor **works alongside** the Gmail Add-on:

| Feature | Background Monitor | Manual Add-on |
|---------|-------------------|--------------|
| Runs constantly | ✅ Yes (every 5 min) | ❌ Manual only |
| Requires user action | ❌ No | ✅ Yes |
| Auto-captures emails | ✅ Yes | ❌ Manual |
| On-demand actions | ❌ No | ✅ Summarize, Draft, Chat |
| Good for automation | ✅ Yes | ❌ Interactive only |

**Best Practice:** Use both:
- **Background Monitor** for automatic capture of all emails
- **Gmail Add-on** for on-demand analysis and drafting

---

## API Endpoints Used

The monitor calls these backend endpoints:

### 1. Log Email Messages
```
POST /api/log-email
{
  "user_id": "user@gmail.com",
  "thread_id": "thread_123",
  "messages": [
    {
      "message_id": "msg_1",
      "from_address": "sender@example.com",
      "to": ["recipient@example.com"],
      "subject": "Email Subject",
      "timestamp": "2026-02-05T10:30:00Z",
      "body": "Email content..."
    }
  ]
}
```

### 2. Store Attachments
```
POST /api/store-attachments
{
  "user_id": "user@gmail.com",
  "thread_id": "thread_123",
  "message_id": "msg_1",
  "attachments": [
    {
      "filename": "document.pdf",
      "content": "base64_encoded_content...",
      "mime_type": "application/pdf"
    }
  ]
}
```

---

## Monitoring & Alerts

### View Execution Logs

In Apps Script: **Executions** (play icon) tab

Shows:
- Each execution time
- Status (success/error)
- Duration
- Any logged messages

### Statistics Saved

The monitor saves statistics for last 100 runs:
- Threads processed
- Emails logged
- Attachments stored
- Processing duration
- Any errors

### Manual Check

```javascript
const stats = getMonitorStats();
Logger.log("Last run: " + JSON.stringify(stats.lastRun, null, 2));
```

---

## Performance Notes

### Processing Time

- Typical check: 2-5 seconds
- Per email: ~0.05 seconds
- Per attachment: ~0.1-0.5 seconds

### Limits

- Max 50 emails per check (configurable)
- Max 25 attachments per message
- Email body limited to ~1 MB

### Optimizations

- Only processes unread emails (faster)
- Skips already-processed threads
- Runs every 5 minutes (reasonable balance)
- Batch uploads attachments

---

## Deployment

### Development Testing

```javascript
// 1. Test configuration
testBackgroundMonitor()

// 2. Check status
getMonitorStats()

// 3. View logs
viewMonitorLogs()
```

### Production Activation

```javascript
// Enable triggers (one-time)
setupTriggers()

// Monitor will now run automatically every 5 minutes
```

### Maintenance

```javascript
// Check status weekly
getMonitorStats()

// Restart if needed
restartMonitor()

// View detailed logs
viewMonitorLogs()
```

---

## Summary

| Aspect | Details |
|--------|---------|
| **Setup Time** | ~5 minutes |
| **Manual Steps** | 4 (create project, configure URL, grant permissions, run setupTriggers) |
| **Check Frequency** | Every 5 minutes (configurable) |
| **Uptime** | 24/7 (automatic) |
| **Processing** | ~2-5 seconds per check |
| **Reliability** | 3-retry logic with automatic retries |
| **Monitoring** | Full statistics and error tracking |

---

## Next Steps

1. ✅ Create the Apps Script project
2. ✅ Configure Flask server URL in Script Properties
3. ✅ Grant permissions on first run
4. ✅ Run `setupTriggers()` to activate
5. ✅ Check `getMonitorStats()` to verify it's working
6. ✅ Monitor runs automatically every 5 minutes!

**Happy monitoring!** 📧✨
