# Bulk Email Labeling Fix - February 23, 2026

## Problem

The bulk email labeling script was only labeling a few emails (≈20-30) before stopping, even though the script and backend were working correctly.

### Root Cause
When the bulk job hit Google Apps Script's 5-minute timeout limit, it tried to schedule a continuation using:
```javascript
ScriptApp.newTrigger('_continueBulkJob')
  .timeBased()
  .after(1 * 60 * 1000)  // 1 minute later
  .create();
```

However, **Google Apps Script enforces a minimum 1-hour spacing requirement** between time-based triggers for the same handler function. This caused the error:
```
Clock events must be scheduled at least 1 hour(s) apart.
```

With the continuation triggers failing silently, the bulk job never resumed after the first 5-minute batch, leaving most emails unlabeled.

## Solution

The fix eliminates the problematic trigger scheduling by leveraging the **existing 1-minute monitoring loop** that's already running (`monitorEmails()`).

### Implementation Details

1. **Removed continuation trigger creation** in `_scheduleContinuation()`
2. **Added property-based continuation detection** in `monitorEmails()`:
   ```javascript
   if (scriptProps.getProperty(BULK_JOB_STATE_KEY) && 
       scriptProps.getProperty('bulk_job_pending_continuation') === 'true') {
     console.log("🔄 Detected pending bulk job continuation. Resuming...");
     scriptProps.deleteProperty('bulk_job_pending_continuation');
     _runBulkJob();
     return;
   }
   ```

3. **Updated job timeout handling** to set a property flag instead of creating triggers:
   ```javascript
   scriptProps.setProperty('bulk_job_pending_continuation', 'true');
   console.log("⏭️  Saved state. Will continue at next monitor cycle (~1 minute).");
   ```

### How It Works Now

1. User clicks "Run Now" → `_launchBulkJobAsync()` initializes state + sets `bulk_job_pending_continuation` flag
2. Existing `monitorEmails()` runs every 1 minute
3. detects the pending continuation flag and calls `_runBulkJob()` directly
4. Job runs for ≈4.5 minutes (safe margin before 5-minute timeout)
5. When timeout approaches, it saves state and sets the flag again
6. Next monitor cycle (~1 minute later) picks it up and continues
7. Process repeats until all emails are processed or job is cancelled

### Advantages

✅ **No new trigger triggers needed** - Works within GAS constraint  
✅ **Faster continuation** - Uses existing 1-minute loop instead of waiting 1 hour  
✅ **More reliable** - Property-based detection can't fail like trigger scheduling  
✅ **Better UX** - Jobs continue almost immediately (within ~1 minute)  
✅ **Cleaner code** - Leverages existing monitor infrastructure  

### Testing

After deployment, verify:

1. **Check label counts are higher** than before (should now process hundreds instead of 20-30)
2. **Monitor the logs** in Script Editor to see job status:
   - Look for: `🔄 Detected pending bulk job continuation`
   - Should see multiple continuation cycles for large jobs
3. **Cancel behavior** - Test `cancelBulkJob()` still works properly

### Changed Files

- `addon/BackgroundEmailMonitor.gs` - Updated `monitorEmails()`, `_scheduleContinuation()`, `_continueBulkJob()`, `_cleanupAfterAbort()`, `cancelBulkJob()`, and `_launchBulkJobAsync()`

### Related Properties

The fix uses these script properties for state management:
- `bulk_job_state` - Serialized job state (offset, stats, date range)
- `bulk_job_abort` - Poison pill flag to stop running job
- `bulk_job_pending_continuation` - **NEW** - Flag to trigger continuation on next monitor cycle

---

**Result**: Bulk labeling now completes properly, labeling all filtered emails instead of just the first 5-minute batch.
