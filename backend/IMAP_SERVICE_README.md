# IMAP Email Fetching - Backend Service

## Overview

The backend now includes an IMAP email fetching service that automatically retrieves emails from users' IMAP servers and sends them to the agent for processing.

## Architecture

```
backend/
├── main.py                          # Main FastAPI application
└── services/
    ├── __init__.py
    ├── imap_database.py             # SQLite database for user credentials
    └── imap_fetcher.py              # IMAP email fetching service
```

## Features

✅ **Multi-user support**: Fetch emails for multiple users simultaneously
✅ **Automatic triggering**: Enable IMAP when saving settings with `run_imap_server=true`
✅ **Secure storage**: User credentials stored in SQLite database
✅ **Background fetching**: Can run periodic email checks
✅ **Manual control**: API endpoints for manual triggering and status checking

## Database Schema

**Table: `imap_users`**
```sql
CREATE TABLE imap_users (
    user_id TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    app_password TEXT NOT NULL,
    imap_host TEXT DEFAULT 'imap.gmail.com',
    imap_port INTEGER DEFAULT 993,
    enabled BOOLEAN DEFAULT 1,
    last_check TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**Location**: `openmailbot/backend/imap_users.db`

## Usage

### 1. Enable IMAP via Settings

Send a POST request to `/api/settings` with IMAP credentials:

```json
{
  "user_id": "user@example.com",
  "settings": {
    "run_imap_server": true,
    "imap_email": "user@gmail.com",
    "imap_app_password": "xxxx xxxx xxxx xxxx",
    "imap_host": "imap.gmail.com",
    "imap_port": 993,
    ...other settings...
  }
}
```

**What happens:**
1. Settings are saved via `SettingsManager`
2. User credentials are stored in `imap_users.db`
3. IMAP fetcher immediately retrieves new emails
4. Emails are sent to agent's `/api/store-email` endpoint

### 2. Manual IMAP Fetch

**Fetch for specific user:**
```http
POST /api/imap/fetch?user_id=user@example.com
```

**Fetch for all enabled users:**
```http
POST /api/imap/fetch
```

**Response:**
```json
{
  "success": true,
  "total_users": 3,
  "total_emails": 15,
  "results": [
    {
      "user_id": "user1@example.com",
      "emails_fetched": 5,
      "success": true,
      "error": null
    },
    {
      "user_id": "user2@example.com",
      "emails_fetched": 10,
      "success": true,
      "error": null
    }
  ]
}
```

### 3. Check IMAP Status

**Get status for specific user:**
```http
GET /api/imap/status?user_id=user@example.com
```

**Get status for all users:**
```http
GET /api/imap/status
```

**Response:**
```json
{
  "success": true,
  "service_available": true,
  "users": [
    {
      "user_id": "user@example.com",
      "email": "user@gmail.com",
      "enabled": true,
      "last_check": "2026-05-05T10:30:00",
      "imap_host": "imap.gmail.com",
      "imap_port": 993,
      "app_password": "****"
    }
  ]
}
```

### 4. Disable IMAP for User

```http
DELETE /api/imap/user@example.com
```

**Response:**
```json
{
  "success": true,
  "user_id": "user@example.com",
  "message": "IMAP disabled for user"
}
```

## Multi-User Workflow

### Example: 3 Users Setup

**User 1:**
```bash
curl -X POST http://localhost:5051/api/settings \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "alice@example.com",
    "settings": {
      "run_imap_server": true,
      "imap_email": "alice@gmail.com",
      "imap_app_password": "aaaa bbbb cccc dddd"
    }
  }'
```

**User 2:**
```bash
curl -X POST http://localhost:5051/api/settings \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "bob@example.com",
    "settings": {
      "run_imap_server": true,
      "imap_email": "bob@gmail.com",
      "imap_app_password": "eeee ffff gggg hhhh"
    }
  }'
```

**User 3:**
```bash
curl -X POST http://localhost:5051/api/settings \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "charlie@example.com",
    "settings": {
      "run_imap_server": true,
      "imap_email": "charlie@gmail.com",
      "imap_app_password": "iiii jjjj kkkk llll"
    }
  }'
```

**Fetch emails for all 3 users:**
```bash
curl -X POST http://localhost:5051/api/imap/fetch
```

The service will:
1. Connect to each user's IMAP server
2. Fetch new emails since last check
3. Send emails to agent for processing
4. Update last_check timestamp

## Email Processing Flow

```
┌─────────────────┐
│  /api/settings  │  (run_imap_server=true)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ IMAP Database   │  Store credentials
│  (SQLite)       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ IMAP Fetcher    │  Connect to IMAP server
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Get Emails      │  Fetch new emails
│ (IMAP Protocol) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Send to Agent   │  POST /api/store-email
│ (HTTP Request)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Agent Pipeline  │  Process & store emails
└─────────────────┘
```

## Configuration

### Environment Variables

- `AGENT_URL`: Agent server URL (default: `http://localhost:5051`)
  - Used for sending emails to agent

### Settings Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `run_imap_server` | boolean | Yes | false | Enable IMAP fetching |
| `imap_email` | string | No | user_id | Email for IMAP login |
| `imap_app_password` | string | Yes* | - | IMAP app password |
| `imap_host` | string | No | `imap.gmail.com` | IMAP server hostname |
| `imap_port` | integer | No | 993 | IMAP SSL port |

*Required when `run_imap_server=true`

## Gmail App Password Setup

### For Gmail users:

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable 2-Step Verification (if not already enabled)
3. Go to [App Passwords](https://myaccount.google.com/apppasswords)
4. Select "Mail" and "Other" (custom name)
5. Click "Generate"
6. Copy the 16-character password (e.g., `xxxx xxxx xxxx xxxx`)
7. Use this password in `imap_app_password` field

## Background Monitoring (Future Enhancement)

The `IMAPFetcherService` supports background monitoring:

```python
# In main.py startup event
@app.on_event("startup")
async def startup_event():
    if _imap_fetcher:
        # Check every 60 seconds
        _imap_fetcher.start_background_monitoring(interval_seconds=60)

@app.on_event("shutdown")
async def shutdown_event():
    if _imap_fetcher:
        _imap_fetcher.stop_background_monitoring()
```

This will automatically fetch emails for all enabled users every 60 seconds.

## Troubleshooting

### IMAP Service Not Available

**Symptom**: API returns "IMAP service not available"

**Causes**:
1. Import error in backend services
2. Database initialization failed

**Check logs**:
```
⚠️  IMAP services not available: <error>
```

### Authentication Failed

**Symptom**: "Error fetching emails: authentication failed"

**Causes**:
1. Incorrect app password
2. 2-Step Verification not enabled
3. App password not generated

**Solution**:
- Regenerate app password from Google Account
- Verify app password has no spaces when stored

### No Emails Fetched

**Symptom**: `emails_fetched: 0` but you expect emails

**Causes**:
1. No new emails since last check
2. IMAP SINCE filter excludes emails (day-level granularity)
3. Emails older than last_check timestamp

**Solution**:
- Check `last_check` timestamp in database
- Manually reset last_check to fetch older emails:
  ```sql
  UPDATE imap_users SET last_check = NULL WHERE user_id = 'user@example.com';
  ```

### Connection Timeout

**Symptom**: "Failed to connect to IMAP server"

**Causes**:
1. Firewall blocking port 993
2. Incorrect IMAP host
3. Network issues

**Solution**:
- Verify IMAP settings for your email provider
- Test IMAP connection manually using `openssl`:
  ```bash
  openssl s_client -connect imap.gmail.com:993
  ```

## API Endpoints Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/settings` | POST | Save settings & enable IMAP |
| `/api/imap/fetch` | POST | Trigger IMAP fetch manually |
| `/api/imap/status` | GET | Get IMAP configuration status |
| `/api/imap/{user_id}` | DELETE | Disable IMAP for user |

## Security Considerations

1. **Credentials Storage**: App passwords stored in plaintext in SQLite
   - TODO: Add encryption for app_password field
   - Database file permissions should be restricted

2. **API Access**: No authentication on IMAP endpoints
   - TODO: Add JWT/API key authentication
   - Restrict access to admin users only

3. **Password Exposure**: Passwords masked in API responses
   - `/api/imap/status` returns `****` instead of actual password

## Future Enhancements

- [ ] Encrypt app_password in database
- [ ] Add authentication to IMAP endpoints
- [ ] Support for other IMAP providers (Outlook, Yahoo, etc.)
- [ ] Webhook support for real-time email notifications
- [ ] Email filtering rules (fetch only specific folders/labels)
- [ ] Retry logic for failed IMAP connections
- [ ] Metrics and monitoring (emails fetched, errors, etc.)
- [ ] Admin dashboard for managing IMAP users
