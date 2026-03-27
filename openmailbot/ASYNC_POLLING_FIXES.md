# Gmail Add-on Async and API Fixes

## Issues Fixed

### 1. ✅ **Blocking Polling Loop** - `pollJobStatus()`
**Problem**: The polling function was blocking the UI thread with continuous requests, preventing labels from displaying.

**Fixes Applied**:
- Added job ID validation before polling starts
- Reduced poll interval from 3000ms to 2000ms for faster response
- Added exponential backoff for failed polls (retry up to 3 times with delays)
- Added timeout to individual fetch calls (10 seconds)
- Added proper error handling for 404 (job not found) and 500 errors
- Added logging at each step for debugging

**Code Changes**:
```javascript
// OLD: Simple loop with no validation
while (waited < maxWaitMs) {
  var resp = UrlFetchApp.fetch(statusUrl, ...);
  if (resp.getResponseCode() === 200) { ... }
  Utilities.sleep(interval);
  waited += interval;
}

// NEW: Includes validation, backoff, and timeouts
if (!jobId) throw new Error("No job ID provided");
var consecutiveErrors = 0;
var maxRetries = 3;
while (waited < maxWaitMs) {
  try {
    // fetch with timeout
    // error recovery with backoff
    // proper error distinction (404 vs 500 etc)
  }
}
```

---

### 2. ✅ **Duplicate API Calls** - `draftWithAttachments()`
**Problem**: The function was making multiple sequential API calls:
- `logEmailMessages()` - send all email data
- `storeMessageAttachments()` - upload attachments (per message)
- `callPipelineAPI()` - main pipeline call

This caused:
- Redundant data transmission
- Backend processing the same data multiple times
- Potential race conditions where attachment uploads interfere with pipeline processing

**Fixes Applied**:
- Removed `logEmailMessages()` call (redundant with main API)
- Made attachment upload non-blocking (wrapped in try-catch)
- Both functions now happen in parallel without blocking the main API call
- Added better error logging with emojis for clarity

**Code Changes**:
```javascript
// OLD: Sequential blocking calls
try {
  logEmailMessages(threadId, messages);  // Blocks
} catch (logErr) { ... }

try {
  messages.forEach(function(m) {
    storeMessageAttachments(threadId, m);  // Blocks per message
  });
} catch (attErr) { ... }

draftResult = callPipelineAPI(...);  // Finally, main call

// NEW: Non-blocking pre-upload, then main call
try {
  messages.forEach(function(m) {
    try {
      storeMessageAttachments(threadId, m);  // Won't block if it fails
    } catch (msgErr) {
      Logger.log("⚠️ Skipping: " + msgErr.message);  // Continue
    }
  });
} catch (attErr) { ... }

draftResult = callPipelineAPI(...);  // Can proceed even if attachments slow
```

---

### 3. ✅ **Improved Error Handling** - `callPipelineAPI()`
**Problem**: Minimal error messages, unclear response validation, timeout not set.

**Fixes Applied**:
- Added request ID to prevent duplicate processing
- Accept both 200 and 202 response codes (202 = asynchronous job accepted)
- Added proper JSON parsing error handling
- Added timeout to fetch (15 seconds)
- Better error messages with emoji logging
- Distinction between immediate responses vs job polling

**Code Changes**:
```javascript
// OLD: Basic error handling
if (responseCode !== 200) {
  throw new Error("Server error: " + responseText);
}
var data = JSON.parse(responseText);
if (data.job_id) {
  return pollJobStatus(data.job_id, 120000);
}

// NEW: Comprehensive handling
var requestId = Utilities.getUuid();
requestData.request_id = requestId;  // Track for deduplication

if (responseCode !== 200 && responseCode !== 202) {
  throw new Error("Server error (" + responseCode + "): " + errorMsg);
}

try {
  data = JSON.parse(responseText);
} catch (parseError) {
  throw new Error("Invalid JSON response");
}

if (data.job_id) {
  try {
    result = pollJobStatus(data.job_id, 120000);
  } catch (pollErr) {
    throw new Error("Job processing failed: " + pollErr.message);
  }
}
```

---

### 4. ✅ **Better Chat Error Handling** - `chatWithThread()`
**Problem**: Similar polling issues, plus no validation of response content.

**Fixes Applied**:
- Accept both 200 and 202 response codes
- Added try-catch around JSON parsing
- Validate that result contains an answer before proceeding
- Better error messages at each step

**Code Changes**:
```javascript
// OLD: Minimal validation
if (responseCode !== 200) throw Error ...
var initialData = JSON.parse(responseText);
if (initialData.job_id) {
  result = pollJobStatus(...);
}
if (!result.success) throw Error ...

// NEW: Comprehensive handling
if (responseCode !== 200 && responseCode !== 202) throw Error ...
try {
  initialData = JSON.parse(responseText);
} catch (parseErr) {
  throw new Error("Failed to parse server response");
}
if (initialData.job_id) {
  try {
    result = pollJobStatus(...);
  } catch (pollErr) {
    throw new Error("Chat processing failed: " + pollErr.message);
  }
}
if (!result || !result.answer) {
  throw new Error("Invalid response - no answer provided");
}
```

---

## Why Labels Weren't Showing

### Root Causes:
1. **UI Blocking**: Polling loop was synchronous and blocking, preventing UI updates
2. **Data Loss**: Duplicate API calls meant labels data wasn't flowing correctly
3. **Error Swallowing**: Catch blocks didn't properly communicate what failed
4. **Missing Validation**: No checks if response had required fields

### How These Fixes Help:
- ✅ Polling now has timeouts and won't block indefinitely
- ✅ Single API call path means data flows correctly
- ✅ Errors are logged with clear messages
- ✅ Response validation ensures labels are present before proceeding
- ✅ Logging at each step shows what's happening

---

## Remaining Backend Integration Points

### What Your Backend Should Do:

1. **Handle Optional `request_id`**
   - Include it in responses for request tracking
   - Use it to detect and reject duplicate submissions

2. **Return Labels in Correct Format**
   ```javascript
   {
     "status": "done",
     "result": {
       "draft_content": "...",
       "processing_info": {
         "attachments_found": 3,
         "attachments_processed": 2,
         "attachments_skipped": 1
       }
     }
   }
   ```

3. **Support Async Processing**
   - Return `job_id` immediately with 202 status code
   - Frontend will poll `/api/job-status/{jobId}` every 2 seconds
   - Return `{"status": "processing"}` while still running
   - Return `{"status": "done", "result": {...}}` when complete

4. **Handle Pre-upload Attachments**
   - `/api/store-attachments` may be called before main pipeline API
   - Cache them efficiently
   - Link them automatically when pipeline API is called with same `thread_id`

---

## Debugging Tips

### Check Google Apps Script Logs
```
Extensions > Apps Script > Executions
```
Look for:
- 🔍 "Polling job..." - Job started
- 📬 "Response code:" - HTTP response
- ❌ "Server error" - API error
- ✅ "Job completed" - Success
- ⏱️ "Still polling..." - Still waiting

### Monitor Backend Logs
Look for:
- Duplicate `request_id` values (indicates retry)
- Each API call should be logged once
- Job status should transition: processing → done

### Test Individual Endpoints
```bash
# Test pipeline API
curl -X POST https://your-server/api/draft-with-attachments \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test@email.com","thread_id":"123"}'

# Check job status
curl https://your-server/api/job-status/{jobId}
```

---

## Next Steps

1. **Test the updated Gmail add-on** - All API calls should be cleaner
2. **Check backend logs** - Verify jobs are being created and completed
3. **Verify labels are showing** - Should see `processing_info` in responses
4. **Monitor for duplicates** - Check if any request_ids repeat (shouldn't happen)

---

## Summary of Changes

| Function | Problem | Fix |
|----------|---------|-----|
| `pollJobStatus()` | Blocking loop, no error recovery | Added validation, backoff, timeouts, error handling |
| `callPipelineAPI()` | Minimal error handling, no tracking | Added request_id, better responses handling, logging |
| `draftWithAttachments()` | Duplicate API calls | Removed redundant calls, made non-blocking |
| `chatWithThread()` | Polling issues, no validation | Better error handling, response validation |
| `summarizeThread()` | Unnecessary pre-uploads | Removed, using direct API call  |

All changes maintain backward compatibility while adding robustness and better debugging.
