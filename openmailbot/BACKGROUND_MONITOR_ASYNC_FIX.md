# Background Monitor - Async Labeling Fix

## Problem: Labels Not Showing

**Issue**: Backend is working and receiving data, but labels are not being applied to emails.

**Root Cause**: The background monitor's `sendEmailToServer()` function wasn't handling **asynchronous responses** from the backend. If the backend returns a `job_id` for async processing instead of an immediate label, the script was ignoring it.

---

## What Changed

### 1. **Updated `sendEmailToServer()` Function**

**Before** ❌:
```javascript
// Expected immediate response with label
var resp = UrlFetchApp.fetch(endpoint, options);
if (responseCode !== 200) throw Error;
var label = responseData.label;  // ← Would be undefined if backend was async!
```

**After** ✅:
```javascript
// Handles BOTH immediate and async responses
if (responseCode !== 200 && responseCode !== 202) throw Error;

if (responseData.job_id) {
  // Backend returned async job_id - poll for result
  var label = _pollLabelingJob(responseData.job_id, baseUrl);
  applyLabelToThread(threadId, label);
} else {
  // Immediate response with label
  var label = responseData.label;
  applyLabelToThread(threadId, label);
}
```

### 2. **Updated `_runBulkJob()` Function**

The bulk email processing also now:
- Accepts 202 (Accepted) responses in addition to 200
- Detects `job_id` in responses
- Polls for the label if async
- Tracks labeled emails correctly

**Before** ❌:
```javascript
if (resp.getResponseCode() !== 200) {
  console.log("Server error");
  state.stats.errors++;
}
var label = JSON.parse(resp.getContentText()).label;  // ← Empty if async!
```

**After** ✅:
```javascript
if (resp.getResponseCode() !== 200 && resp.getResponseCode() !== 202) {
  console.log("Server error");
  state.stats.errors++;
}
var label = null;
if (respData.job_id) {
  label = _pollLabelingJob(respData.job_id, baseUrl);  // Async path
} else {
  label = respData.label;  // Immediate path
}
```

### 3. **New `_pollLabelingJob()` Function**

Handles polling for asynchronous label results:

```javascript
function _pollLabelingJob(jobId, baseUrl) {
  var statusEndpoint = baseUrl + '/api/job-status/' + jobId;
  var maxWaitMs = 30000;  // 30 second timeout
  var pollInterval = 2000; // Poll every 2 seconds
  
  while (waited < maxWaitMs) {
    var data = fetch(statusEndpoint);
    if (data.status === "done") {
      return data.result.label;  // ← Label found!
    }
    sleep(pollInterval);
  }
}
```

---

## How It Works Now

### Scenario 1: Immediate Response (Synchronous)
```
1. Script sends email data
2. Backend returns: {"label": "Response"}
3. Script immediately applies label ✅
```

### Scenario 2: Async Response (Job-based)
```
1. Script sends email data
2. Backend returns: {"job_id": "xyz123"} with 202 status
3. Script polls /api/job-status/xyz123 every 2 seconds
4. After processing, backend returns: {"status": "done", "result": {"label": "Response"}}
5. Script applies label ✅
6. Moves to next email
```

---

## Backend Requirements

Your backend needs to support:

### Option A: Synchronous (Immediate)
```json
{
  "status": 200,
  "body": {"label": "Response"}
}
```

### Option B: Asynchronous (Job-based)
```json
{
  "status": 202,
  "body": {"job_id": "abc123xyz"}
}

// Later, when polled:
GET /api/job-status/abc123xyz
{
  "status": "done",
  "result": {"label": "Response"}
}
```

### Both Approaches Work ✅
The script now handles both immediately!

---

## Testing the Fix

### 1. Add a test email
```bash
# Send yourself an email from a monitored domain
```

### 2. Check the logs
```
Extensions > Apps Script > Executions
Look for these log patterns:
```

**If Synchronous**:
```
📤 Sending email to server for labeling...
📬 Response code: 200
📌 Label from immediate response: Response
✓ Applied label 'Response' to thread
```

**If Asynchronous**:
```
📤 Sending email to server for labeling...
📬 Response code: 202
🔄 Got job_id (async processing): abc123
🔍 Polling job status: abc123
📊 Job status: processing
⏳ Still polling... (2.0s/30s)
📊 Job status: done
✅ Job completed - label: Response
✓ Applied label 'Response' to thread
```

### 3. Check Gmail
Labels should now appear on emails after 1-2 minutes (next monitor run).

---

## Logging Added

New detailed logs help debug:

```
📤 Sending email to server        ← API call initiated
📬 Response code: 202             ← Status from server
🔄 Got job_id: abc123xyz         ← Async job detected
🔍 Polling job status: abc123    ← Starting poll loop
📊 Job status: processing        ← Job still running
⏳ Still polling... (2.0s/30s)   ← Progress update
✅ Job completed                  ← Job done
```

---

## Performance

### Background Monitor (runs every 1 minute)
- **Per email**: Wait max 30 seconds for label
- **Gap between calls**: 2 seconds (configurable with CALL_GAP_MS)
- **Total impact**: Manageable since it's background

### Main Script (User-interactive)
- Use the fixes from `ASYNC_POLLING_FIXES.md`
- Faster polling intervals (2-3 seconds)
- Better UI feedback

---

## Configuration

If you want to customize polling behavior, edit these variables in `BackgroundEmailMonitor.gs`:

```javascript
// In _pollLabelingJob() function
var maxWaitMs = 30000;      // Max wait time (currently 30s)
var pollInterval = 2000;    // Poll frequency (currently 2s)
var maxRetries = 3;         // Retry failed polls (currently 3x)

// In _runBulkJob() function
var CALL_GAP_MS = 2000;     // Gap between API calls (currently 2s)
```

---

## Troubleshooting

### Issue: Still no labels after 2-3 runs

**Check 1**: Backend is returning the label
```bash
# Test your backend
curl -X POST http://your-backend/api/label-email \
  -H "Content-Type: application/json" \
  -d '{ "user_id": "test@email.com", "thread_id": "xyz" }'

# Should return either:
# {"label": "Response"}  OR
# {"job_id": "abc123"}
```

**Check 2**: Server URL is configured
```
Extensions > Apps Script > Project Settings > Script Properties
Verify: FLASK_SERVER_URL is set correctly
```

**Check 3**: Monitor is active
```
Run: getMonitorStatus()
Look for: "✅ MONITOR IS ACTIVE"
```

### Issue: Polling times out often

**Cause**: Backend job taking too long
**Solution**: Increase maxWaitMs in `_pollLabelingJob()` from 30000 to 60000

### Issue: "Too many server errors" message

**Cause**: Backend `/api/job-status` endpoint is failing
**Solution**: 
1. Check backend logs
2. Verify job records are being created
3. Test: `curl http://your-backend/api/job-status/test_id`

---

## Files Changed

- `addon/BackgroundEmailMonitor.gs`
  - ✅ `sendEmailToServer()` - handles async
  - ✅ `_runBulkJob()` - handles async
  - ✅ `_pollLabelingJob()` - NEW polling function

---

## Next Steps

1. **Deploy these changes**
2. **Restart the background monitor**:
   ```
   Run: setupEmailMonitor()
   ```
3. **Send a test email** to verify
4. **Check logs** in 2-3 minutes
5. **Confirm labels appear** in Gmail

---

## Summary

| Component | Before | After |
|-----------|--------|-------|
| Async handling | ❌ None | ✅ Full support |
| Label retrieval | ❌ Fails | ✅ Polls until ready |
| Error recovery | ❌ Minimal | ✅ With backoff |
| Response codes | ❌ Only 200 | ✅ 200 + 202 |
| Timeout handling | ❌ No | ✅ 30s max |
| Logging | ⚠️ Basic | ✅ Detailed |

**Result**: Labels should now appear consistently on all emails! 🎉
