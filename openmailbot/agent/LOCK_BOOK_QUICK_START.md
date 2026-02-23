# Lock Book Quick Reference

## What is the Lock Book?

A JSON-based logging system that automatically tracks metrics for the `/api/label-email` endpoint:

```
📊 Tracks:
✓ Email timestamps
✓ Number of requests
✓ Number of labeled emails  
✓ Number of graph-stored emails
```

## Where is the Data Stored?

```
agent/data/lockbook/
├── label_email_metrics_global.json       (all users combined)
└── label_email_metrics_{user_id}.json    (per-user metrics)
```

---

## Quick Check - View Metrics During Work

### Option 1: Simple View (Current Stats)
```bash
curl http://localhost:8000/api/label-email/metrics
```

### Option 2: User-Specific Stats
```bash
curl http://localhost:8000/api/label-email/metrics?user_id=user@example.com
```

### Option 3: Recent Activity (Last 20 Requests)
```bash
curl http://localhost:8000/api/label-email/recent-requests
```

### Option 4: Pretty Summary
```bash
curl http://localhost:8000/api/label-email/summary
```

---

## What Gets Logged Automatically

Every time you call `/api/label-email`:

| Field | Logged | Example |
|-------|--------|---------|
| **Timestamp** | ✅ Yes | `2026-02-20T11:30:45.123456` |
| **Thread ID** | ✅ Yes | `thread_abc123` |
| **Label Assigned** | ✅ Yes | `meeting`, `FYI`, `response` |
| **Emails Labeled** | ✅ Yes | `3` |
| **Emails Graph Stored** | ✅ Yes | `3` |
| **Status** | ✅ Yes | `SUCCESS` or `FAILED` |

---

## Real-Time Monitoring Examples

### Python Script to Monitor
```python
import requests
import json
from datetime import datetime

def check_metrics():
    response = requests.get("http://localhost:8000/api/label-email/metrics")
    data = response.json()["data"]["metrics"]
    
    print(f"⏰ {datetime.now().strftime('%H:%M:%S')}")
    print(f"📧 Requests: {data['total_requests']}")
    print(f"✓ Labeled: {data['total_labeled_emails']}")
    print(f"📊 Graph Stored: {data['total_graph_stored']}")
    
    # Show by label
    for label, stats in data['by_label'].items():
        print(f"  • {label}: {stats['count']} requests")

check_metrics()
```

### Bash Script to Monitor
```bash
#!/bin/bash

while true; do
    clear
    echo "=== Lock Book Metrics ==="
    curl -s http://localhost:8000/api/label-email/metrics | jq '.data.metrics'
    sleep 5
done
```

---

## Data Structure Example

```json
{
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
      }
    }
  }
}
```

---

## Key Features

✅ **Automatic** - No configuration needed  
✅ **Fast** - JSON format for speed  
✅ **Thread-safe** - Multiple concurrent requests handled  
✅ **Real-time** - Updated immediately after each request  
✅ **User-isolated** - Per-user metrics tracked  
✅ **Global aggregation** - Overall system metrics available  
✅ **Recent history** - Last 100 requests kept for analysis  

---

## Integration Points

The lock book is **automatically integrated** into:

1. `✓ /api/label-email` - Endpoint being monitored
2. `✓ Label success path` - Logs successful labeling
3. `✓ Label error path` - Logs failures
4. `✓ Graph storage path` - Tracks graph DB writes

**No manual integration needed!**

---

## All Available Endpoints

| Endpoint | Purpose | Query Params |
|----------|---------|--------------|
| `GET /api/label-email/metrics` | Get current metrics | `?user_id=...` |
| `GET /api/label-email/recent-requests` | Last N requests | `?user_id=...&limit=20` |
| `GET /api/label-email/label-stats` | Stats by label | `?user_id=...&label=meeting` |
| `GET /api/label-email/summary` | Pretty text summary | `?user_id=...` |

---

## Example: Monitor During Active Processing

```bash
# Terminal 1: Start processing emails
# Make multiple /api/label-email requests...

# Terminal 2: Monitor metrics in real-time
watch -n 2 'curl -s http://localhost:8000/api/label-email/summary | jq ".summary"'

# Terminal 3: Check specific label stats
watch -n 3 'curl -s "http://localhost:8000/api/label-email/label-stats" | jq ".stats"'
```

---

## Files Modified

1. **`services/label_email_lockbook.py`** - New lockbook system
2. **`main.py`** - Integrated into `/api/label-email` endpoint
3. **New endpoints added** to `main.py`:
   - `GET /api/label-email/metrics`
   - `GET /api/label-email/recent-requests`
   - `GET /api/label-email/label-stats`
   - `GET /api/label-email/summary`

---

## Troubleshooting

**Q: Metrics not updating?**
- A: Check if `/api/label-email` requests are being made
- Check disk permissions on `agent/data/lockbook/` directory

**Q: Where's my user-specific data?**
- A: Make requests with `user_id` in the payload
- Check: `curl http://localhost:8000/api/label-email/metrics?user_id=your_email`

**Q: Can I reset the metrics?**
- A: Files will be recreated on next request if deleted
- Or: Clear the JSON files in `agent/data/lockbook/`

---

For detailed documentation, see: **[LOCK_BOOK_GUIDE.md](./LOCK_BOOK_GUIDE.md)**
