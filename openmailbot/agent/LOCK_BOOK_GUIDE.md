# Label-Email Lock Book Guide

## Overview

The Lock Book is a JSON-based logging system that tracks metrics for the `/api/label-email` endpoint. It records:

- **Email timestamps** - When each request was processed
- **Request count** - Total number of requests
- **Labeled emails count** - Total number of emails that were labeled
- **Graph stored emails count** - Total number of emails stored in the graph database

## Files Location

Lock book data is stored in:
```
agent/data/lockbook/
├── label_email_metrics_global.json    # Global metrics across all users
└── label_email_metrics_{user_id}.json # Per-user metrics
```

## JSON File Structure

```json
{
  "user_id": "user@example.com",
  "created_at": "2026-02-20T10:00:00.123456",
  "last_updated": "2026-02-20T11:30:45.123456",
  "metrics": {
    "total_requests": 150,
    "total_labeled_emails": 450,
    "total_graph_stored": 430,
    "by_label": {
      "meeting": {
        "count": 45,
        "emails_labeled": 135,
        "emails_graph_stored": 130
      },
      "FYI": {
        "count": 30,
        "emails_labeled": 90,
        "emails_graph_stored": 85
      },
      "response": {
        "count": 25,
        "emails_labeled": 75,
        "emails_graph_stored": 70
      },
      "error": {
        "count": 50,
        "emails_labeled": 0,
        "emails_graph_stored": 0
      }
    }
  },
  "recent_requests": [
    {
      "timestamp": "2026-02-20T11:30:45.123456",
      "thread_id": "thread_abc123",
      "label": "meeting",
      "emails_labeled": 3,
      "emails_graph_stored": 3,
      "status": "SUCCESS"
    },
    ...
  ]
}
```

## API Endpoints

### 1. Get Metrics
**Endpoint:** `GET /api/label-email/metrics`

**Query Parameters:**
- `user_id` (optional) - Get metrics for specific user. If not provided, returns global metrics.

**Example Requests:**
```bash
# Global metrics
curl http://localhost:8000/api/label-email/metrics

# User-specific metrics
curl http://localhost:8000/api/label-email/metrics?user_id=user@example.com
```

**Response:**
```json
{
  "success": true,
  "data": {
    "user_id": "user@example.com",
    "created_at": "2026-02-20T10:00:00.123456",
    "last_updated": "2026-02-20T11:30:45.123456",
    "metrics": { ... }
  },
  "lockbook_file": "data/lockbook/label_email_metrics_user@example.com.json"
}
```

### 2. Get Recent Requests
**Endpoint:** `GET /api/label-email/recent-requests`

**Query Parameters:**
- `user_id` (optional) - Get requests for specific user
- `limit` (optional) - Number of recent requests to return (default: 20, max: 100)

**Example Requests:**
```bash
# Get last 20 global requests
curl http://localhost:8000/api/label-email/recent-requests

# Get last 50 requests for specific user
curl http://localhost:8000/api/label-email/recent-requests?user_id=user@example.com&limit=50
```

**Response:**
```json
{
  "success": true,
  "count": 20,
  "recent_requests": [
    {
      "timestamp": "2026-02-20T11:30:45.123456",
      "thread_id": "thread_abc123",
      "label": "meeting",
      "emails_labeled": 3,
      "emails_graph_stored": 3,
      "status": "SUCCESS"
    },
    ...
  ]
}
```

### 3. Get Label Statistics
**Endpoint:** `GET /api/label-email/label-stats`

**Query Parameters:**
- `user_id` (optional) - Get stats for specific user
- `label` (optional) - Get stats for specific label (e.g., "meeting", "FYI", "response")

**Example Requests:**
```bash
# Get all label stats (global)
curl http://localhost:8000/api/label-email/label-stats

# Get meeting label stats for specific user
curl http://localhost:8000/api/label-email/label-stats?user_id=user@example.com&label=meeting

# Get all labels for specific user
curl http://localhost:8000/api/label-email/label-stats?user_id=user@example.com
```

**Response:**
```json
{
  "success": true,
  "label": "meeting",
  "stats": {
    "count": 45,
    "emails_labeled": 135,
    "emails_graph_stored": 130
  }
}
```

### 4. Get Summary
**Endpoint:** `GET /api/label-email/summary`

**Query Parameters:**
- `user_id` (optional) - Get summary for specific user

**Example Requests:**
```bash
# Get global summary
curl http://localhost:8000/api/label-email/summary

# Get user summary
curl http://localhost:8000/api/label-email/summary?user_id=user@example.com
```

**Response:**
```json
{
  "success": true,
  "summary": "╔════════════════════════════════════════╗\n║  LABEL-EMAIL LOCK BOOK SUMMARY ...\n"
}
```

## Usage Examples

### Python
```python
import requests

BASE_URL = "http://localhost:8000"

# Get global metrics
response = requests.get(f"{BASE_URL}/api/label-email/metrics")
print(response.json())

# Get user metrics
response = requests.get(
    f"{BASE_URL}/api/label-email/metrics",
    params={"user_id": "user@example.com"}
)
print(response.json())

# Get recent requests
response = requests.get(
    f"{BASE_URL}/api/label-email/recent-requests",
    params={"user_id": "user@example.com", "limit": 10}
)
print(response.json())

# Get label statistics
response = requests.get(
    f"{BASE_URL}/api/label-email/label-stats",
    params={"user_id": "user@example.com"}
)
print(response.json())
```

### cURL
```bash
# Get metrics
curl -s http://localhost:8000/api/label-email/metrics | jq .

# Get user-specific metrics
curl -s http://localhost:8000/api/label-email/metrics?user_id=user@example.com | jq .

# Get recent requests
curl -s http://localhost:8000/api/label-email/recent-requests?limit=10 | jq .

# Get label stats
curl -s http://localhost:8000/api/label-email/label-stats | jq .

# Get summary
curl -s http://localhost:8000/api/label-email/summary | jq .
```

## What Gets Logged

### On Successful Request
When `/api/label-email` successfully processes a request:
- ✅ Thread ID
- ✅ Assigned label (meeting, FYI, response, etc.)
- ✅ Number of emails labeled
- ✅ Number of emails stored in graph DB
- ✅ Timestamp of request
- ✅ Status: "SUCCESS"

### On Failed Request
When `/api/label-email` encounters an error:
- ❌ Thread ID
- ❌ Label: "error"
- ❌ Emails labeled: 0
- ❌ Emails graph stored: 0
- ❌ Timestamp of request
- ❌ Status: "FAILED"

## Monitoring

### Real-time Monitoring
Monitor the lock book during work:

```bash
# Watch global metrics in real-time
watch -n 5 'curl -s http://localhost:8000/api/label-email/summary | jq .summary'

# Watch user metrics
watch -n 5 'curl -s "http://localhost:8000/api/label-email/metrics?user_id=user@example.com" | jq .data.metrics'

# Monitor recent requests
watch -n 2 'curl -s "http://localhost:8000/api/label-email/recent-requests?limit=5" | jq .recent_requests'
```

### Direct File Inspection
You can also inspect the JSON files directly:

```bash
# View global lock book
cat agent/data/lockbook/label_email_metrics_global.json | jq .

# View user-specific lock book
cat agent/data/lockbook/label_email_metrics_{user_id}.json | jq .
```

## Performance

- **Storage**: JSON files (very fast for small datasets)
- **Thread-safe**: Uses Python threading locks for concurrent access
- **Data retention**: Recent 100 requests kept in memory per file
- **I/O**: One write per request (atomic file operations)

## Testing

### Test the Lock Book System
```bash
# 1. Start the server
python agent/main.py

# 2. Make a label request (in another terminal)
curl -X POST http://localhost:8000/api/label-email \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test@example.com",
    "thread_id": "thread_123",
    "messages": [
      {
        "message_id": "msg_1",
        "from_address": "sender@example.com",
        "to": ["recipient@example.com"],
        "subject": "Meeting tomorrow",
        "timestamp": "2026-02-20T10:00:00Z",
        "body": "Can we meet tomorrow at 10am?"
      }
    ]
  }'

# 3. Check the lock book
curl http://localhost:8000/api/label-email/metrics?user_id=test@example.com
```

## Troubleshooting

### Lock book file not found
- Check: `agent/data/lockbook/` directory exists
- First request will auto-create the file

### Permission denied
- Ensure user running the app has write permissions on `agent/data/lockbook/`
- Fix: `chmod 755 agent/data/lockbook/`

### High I/O usage
- Each request writes to JSON file
- For high-volume systems, consider buffering writes
- Recent requests are kept in memory (100 per file)

## Future Enhancements

- [ ] SQLite backend for better performance
- [ ] Automatic daily/weekly log rotation
- [ ] Database export functionality
- [ ] Analytics dashboard
- [ ] Alerts on threshold violations
