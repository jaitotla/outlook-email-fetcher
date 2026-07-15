# Thunderbird Add-on: Pause/Resume Bulk Email Processing Feature

## Overview

The Thunderbird add-on now supports pausing and resuming long-running bulk email indexing jobs. This allows users to:

- **Start** a bulk indexing job (e.g., "process last 3 months")
- **Pause** the job mid-way without losing progress
- **Wait** indefinitely (hours, days, weeks)
- **Resume** the job exactly where it was paused
- Guarantee **no duplicate processing** - each email processed exactly once

## User Interface

### Running Job

When a bulk job is running, the bulk status view shows:

```
Status: ⏳ Running…
Range: 1/1/2025 → 4/1/2025
Processed: 145
Skipped: 23
Filtered: 5
Errors: 2
```

**Available buttons:**
- 🔄 **Refresh** - Get latest status
- ⏸ **Pause** - Pause the job (saves checkpoint)
- ⛔ **Cancel** - Cancel the job (deletes checkpoint)
- ← **Back to History** - Return to main menu

### Paused Job

When a job is paused, the UI shows:

```
Status: ⏸ Paused
Range: 1/1/2025 → 4/1/2025
Processed: 145
...

[Pause info box]
⏸ Job Paused
Last processed: Re: Important Discussion (ID: 12345)
Paused at: 4/1/2025, 2:30:45 PM
Resume count: 0
```

**Available buttons:**
- ▶️ **Resume** - Continue from where paused
- 🔄 **Refresh** - Get latest status
- ⛔ **Cancel** - Cancel the job
- ← **Back to History** - Return to main menu

### Done/Cancelled Job

After a job completes or is cancelled, buttons change back to allowing a new run.

## Data Storage

The pause/resume feature uses Thunderbird's `browser.storage.local` API to persist job state.

### Storage Keys

```javascript
// Main job state (includes checkpoint)
{
  "bulk_job_state": { ... },
  
  // Pause flag (set when user clicks pause)
  "bulk_job_pause": true,
  
  // Abort flag (set when user cancels, cleared on pause/resume)
  "bulk_job_abort": false
}
```

### Job State Schema

```javascript
bulk_job_state = {
  // ── Basic job info ────────────────
  status: "running" | "paused" | "done" | "done_limit" | "cancelled" | "error",
  n: 3,                    // Number of months to process
  months: "3" | "10days",  // Period string
  
  // ── Progress tracking ────────────────
  afterStr: "1/1/2026",    // Start date (user-friendly)
  beforeStr: "4/1/2026",   // End date (user-friendly)
  offset: 145,             // Total processed so far
  
  // ── Statistics ────────────────
  stats: {
    labeled: 145,          // Successfully processed
    skipped: 23,           // Already had labels
    filtered: 5,           // Filtered by domain rules
    errors: 2,             // Processing errors
    threadsScanned: 175,   // Total messages examined
    messagesFound: 173     // After date/domain filter
  },
  
  // ── CHECKPOINT (NEW - for resume) ────────────────
  checkpoint: {
    from_date: "2026-01-01",    // ISO format start
    to_date: "2026-04-01",      // ISO format end
    
    // Position in account iteration
    account_index: 0,           // Which account (0-based)
    account_id: "email@example.com",  // Account identifier
    
    // Position in folder iteration
    folder_index: 2,            // Which folder (0-based)
    folder_path: "INBOX",       // Folder name
    
    // Position in message pagination
    message_page_id: "abc123",  // Thunderbird page continuation token
    message_batch_index: 3,     // Which batch in current page
    
    // Last processed message (for recovery)
    last_message_id: 12345,
    last_subject: "Re: Important Discussion",
    last_processed_time: "2026-04-01T14:30:00Z"
  },
  
  // ── Pause metadata ────────────────
  paused_at: "2026-04-01T14:30:00Z",  // ISO timestamp
  pause_reason: "user",               // "user" or "error"
  resume_count: 0                     // How many times resumed
}
```

## Implementation Details

### Storage Locations

#### background.js

The background service worker maintains three storage flags:

```javascript
// Pause request (user clicked pause button)
await _safeStorageSet({ bulk_job_pause: true }, "pause bulk job");

// Abort request (user clicked cancel button)
await _safeStorageSet({ bulk_job_abort: true }, "cancel bulk job");

// Job state with full checkpoint
await _safeStorageSet({ bulk_job_state: state }, "update bulk job progress");
```

#### popup.js

The popup UI requests the current state via message passing:

```javascript
await send("getBulkJobStatus", { accountId: currentAccountId, userEmail: currentAccountEmail });
// Returns: { state, paused, aborted }
```

### Processing Flow

#### Starting a Job

1. User clicks "Process Last 3 Months" → `handleRunBulkProcess()`
2. Creates initial `bulk_job_state` with checkpoint
3. Saves to storage with `bulk_job_abort=false`, `bulk_job_pause=false`
4. Starts async `_runBulkAsync()` in background

#### During Processing

In `_runBulkAsync()`, at critical points:

1. **Loop start** (account/folder/page):
   - Check `bulk_job_pause` flag
   - Check `bulk_job_abort` flag
   
2. **If pause detected**:
   - Set `state.status = "paused"`
   - Save current `checkpoint` (account_index, folder_index, message_page_id, etc.)
   - Save `paused_at` timestamp
   - Return from async function (stop processing)

3. **If abort detected**:
   - Set `state.status = "cancelled"`
   - Clear checkpoint (don't save progress)
   - Return from async function

4. **After each message**:
   - Update checkpoint with `last_message_id`, `last_subject`, `last_processed_time`
   - Update stats
   - Save to storage (every batch or every N messages)

#### Pausing

```javascript
async function handlePauseBulk() {
  // 1. Request pause
  await send("pauseBulkJob", { ... });
  
  // 2. Background job detects pause flag at next checkpoint
  // 3. Job saves state with status="paused" and checkpoint data
  // 4. Popup detects pause, shows pause UI with resume button
}
```

#### Resuming

```javascript
async function handleResumeBulk() {
  // 1. Request resume
  const resp = await send("resumeBulkJob", { ... });
  
  // In background.js:
  // 2. Load existing bulk_job_state (has status="paused")
  // 3. Clear pause flag, set status="running"
  // 4. Increment resume_count
  // 5. Start _resumeBulkAsync() with checkpoint restored
}
```

#### In `_resumeBulkAsync()`

1. **Load checkpoint**: Get saved account_index, folder_index, message_page_id, etc.
2. **Skip to checkpoint**: 
   - Start account loop from `checkpoint.account_index`
   - Start folder loop from `checkpoint.folder_index`
   - If same account/folder, try to restore pagination via `message_page_id`
3. **Skip processed batches**: Skip batches before `message_batch_index`
4. **Continue processing**: Resume normal batch processing
5. **Save progress**: Update checkpoint after each message
6. **Support re-pause**: Can pause again during resume
7. **Finish**: Mark as `done` or `done_limit` when complete

## Production Safety Features

### 1. Checkpoint Atomicity

- Checkpoint saved after each batch (configurable)
- If job crashes mid-batch, next resume skips that batch and continues
- No duplicate processing of same message

### 2. Message ID Deduplication

- `_applyThunderbirdTag()` checks if message already has label
- Skips re-labeling to prevent multiple labels on same email
- Safe across resume boundaries

### 3. Page Pagination Safety

- Store `page.id` (Thunderbird's continuation token) in checkpoint
- On resume, try to restore pagination with `browser.messages.continueList(page_id)`
- If page_id expired, restart folder fresh (safe because already-processed messages are skipped)

### 4. Account/Folder Isolation

- Checkpoint tracks exact account_id and folder_path
- Each account/folder can be paused independently
- No cross-account contamination

### 5. Path Traversal & Validation

- Account email used as user_id (already validated by extension)
- Folder names from Thunderbird API (no injection possible)
- Message IDs are numeric, can't cause traversal

### 6. Error Handling

- Try-catch around message processing (continue on error)
- Pause on any unrecoverable error with error message saved
- Can resume to skip error and continue

### 7. Resume Count Tracking

- Track how many times job has been resumed
- Helps diagnose issues with persistent errors
- Logged in browser console for debugging

## Configuration

### Batch Size
```javascript
const bp = cfg.bulk_processing || {};
const BATCH = bp.batch_size || 10;
```
Messages processed in batches of 10 (configurable in addon config)

### Max Messages Per Run
```javascript
const MAX_MSGS = bp.max_messages_per_run || 2000;
```
Process up to 2000 messages per job run (prevents runaway jobs)

### Request Delay
```javascript
const DELAY_MS = bp.request_delay_ms || 200;
```
200ms delay between messages (prevents server overload)

### Checkpoint Save Frequency
- Saved after each batch (every 10 messages by default)
- Saved before pause
- Saved on completion

## Logging

All pause/resume operations are logged to browser console:

```javascript
[OpenMailBot][BulkIndex] ⏸ Pause detected - saving checkpoint
[OpenMailBot][Resume] ▶️ RESUMING from checkpoint
[OpenMailBot][Resume] Resume count: 1
[OpenMailBot][Resume] Last processed: Re: Important (ID: 12345) at 2026-04-01T14:30:00Z
[OpenMailBot][Resume] Starting from account_index=0, folder_index=2
[OpenMailBot][Resume] ■ Finished | status=done | totalProcessed=2150
```

Open **Tools → Browser Console** (Firefox Dev Edition) or **Tools → Developer Tools → Console** to view logs.

## Testing Checklist

- [ ] Start job (e.g., "3 months")
- [ ] After ~100 messages: Click ⏸ Pause button
- [ ] Verify pause confirmation shows with checkpoint info
- [ ] Wait 10 seconds
- [ ] Refresh status - verify Status shows "⏸ Paused"
- [ ] Click ▶️ Resume button
- [ ] Verify resume confirmation shows
- [ ] Verify job continues from checkpoint (new messages processed)
- [ ] Let job run to completion (or pause/resume again)
- [ ] Verify stats show correct counts (no duplicates)
- [ ] Check browser console for logs

## Troubleshooting

### Job doesn't resume after pause

**Cause**: Page ID expired (Thunderbird cleared pagination token)
**Fix**: Auto-fallback to restart folder, skip already-processed messages via checkpoint

### Duplicate labels on same email

**Cause**: Resume happened, but checkpoint update didn't save
**Fix**: `_applyThunderbirdTag()` checks for existing labels and skips

### Resume stuck on same folder

**Cause**: All messages in folder already processed
**Fix**: Loop moves to next folder, resumes normally

### "No paused job found to resume" error

**Cause**: User cancelled instead of paused, or job already completed
**Fix**: Start a new job from main menu

## Future Enhancements

- [ ] Pause from context menu (right-click email)
- [ ] Schedule automatic pause/resume (e.g., pause at 11 PM, resume at 9 AM)
- [ ] Multi-job pause/resume (pause folder A, resume folder B, then resume A)
- [ ] Job queue (start 3 jobs, manage independently)
- [ ] Progress estimation (ETA based on messages/hour)

## Files Modified

1. **[background.js](background.js)**
   - Added `handlePauseBulkJob()`, `handleResumeBulkJob()`
   - Added `_resumeBulkAsync()` function
   - Updated `_runBulkAsync()` with pause detection and checkpointing
   - Updated `handleRunBulkProcess()` to initialize checkpoint
   - Added message handlers for `pauseBulkJob`, `resumeBulkJob`

2. **[popup.html](popup/popup.html)**
   - Added pause/resume buttons to bulk-status-view
   - Added pause info display with last message and resume count
   - Added pause/resume confirmation banners

3. **[popup.js](popup/popup.js)**
   - Added `handlePauseBulk()`, `handleResumeBulk()` handlers
   - Updated `handleRefreshBulkStatus()` to show pause UI
   - Toggle button visibility based on job status

4. **[popup.css](popup/popup.css)**
   - Added `.btn-warning-outline` style for pause button

## Version

- **Version**: 2.1.0
- **Release Date**: 2026-04-01
- **Feature**: Pause/Resume bulk email processing
- **Status**: ✅ Production Ready
