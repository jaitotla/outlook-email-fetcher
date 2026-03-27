# Testing Checklist - Async/Polling Fixes

## Quick Verification Steps

### 1. Check Gmail Add-on Logs
```
Extensions > Apps Script > Executions
```

**What to Look For**:
- ✅ All functions should complete without timeout errors
- ✅ You should see emoji-based logging (🔍, 📤, 📬, ✅, ❌)
- ✅ Job IDs should be visible in logs
- ✅ Polling messages like "⏳ Still polling..." should appear

### 2. Draft Generation Test
1. Open any email thread
2. Click "📎 Draft with Attachments"
3. Check for:
   - ✅ Draft preview shows up (with labels if available)
   - ✅ Processing summary displays attachment counts
   - ✅ No timeout errors
   - ✅ Draft appears in your drafts folder

**Expected Logs**:
```
📨 draftWithAttachments starting for thread: ...
📎 Pre-uploaded X attachments
🚀 Calling pipeline API...
📤 Calling pipeline API: .../api/draft-with-attachments [request-id-uuid]
📥 Response code: 202
🔄 Got job_id: ..., starting job polling...
🔍 Polling job: ...
📊 Job status: processing
⏳ Still polling... (2s / 120s)
📊 Job status: done
✅ Job completed successfully!
🎉 Draft created successfully!
```

### 3. Chat Test
1. Open an email thread
2. Click "💬 Chat with Thread"
3. Ask a question
4. Check for:
   - ✅ Processing info shows up (metadata about emails/attachments processed)
   - ✅ Chat response appears
   - ✅ No errors in execution
   - ✅ Labels visible

**Expected Logs**:
```
📤 Calling chat API: .../api/chat-with-thread
📬 Response code: 202
🔍 Checking for job_id: <jobId>
🔄 Got job_id, starting polling...
✅ Chat completed successfully!
```

### 4. Backend Coordination

**Verify Backend Is Doing**:
- ✅ Accepting both 200 and 202 response codes from frontend ✓ (frontend now sends 202 with job_id)
- ✅ Creating jobs with unique IDs
- ✅ `/api/job-status/{jobId}` returning proper status
- ✅ Returning `processing_info` with labels in final response

**Test Backend Endpoint**:
```bash
# 1. Check pipeline endpoint exists
curl -X POST http://your-backend/api/draft-with-attachments \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test@email.com",
    "thread_id": "test_123",
    "message_id": "msg_123"
  }'

# Should return either:
# {"result": {...}} for immediate, or
# {"job_id": "...", "status": "accepted"} for async

# 2. Check job status endpoint
curl http://your-backend/api/job-status/job_123

# Should return:
# {"status": "processing"} or
# {"status": "done", "result": {...}}
```

### 5. Monitor for Issues

**Red Flags**:
- ❌ Same request_id appearing multiple times (duplicate requests)
- ❌ Job IDs not being recognized on second poll
- ❌ Labels missing in response
- ❌ Timeout messages in logs
- ❌ HTML error pages being returned instead of JSON

**If You See Issues**:
1. Check backend server is running
2. Verify `/api/job-status` endpoint is working
3. Look for jobs getting stuck in "processing" state
4. Check database connections on backend

---

## Metrics to Track

### Performance (Should Improve)
| Metric | Before | After | Goal |
|--------|--------|-------|------|
| Poll interval | 3000ms | 2000ms | Faster response |
| API calls per draft | 3 | 1 | Reduced load |
| Duplicate requests | High | 0 (with request_id) | Prevention |
| Timeout errors | Frequent | Rare | Better reliability |

### Error Handling
- Old: Block until timeout
- New: Retry up to 3 times with backoff, then fail clearly
- Result: Better error messages, faster failure detection

---

## Common Issues & Solutions

### Issue: "Labels not showing"
**Causes**:
- [ ] Backend not returning `processing_info`
- [ ] Labels in wrong format
- [ ] Frontend parsing error (check logs)

**Fix**:
```javascript
// Backend should return:
{
  "result": {
    "draft_content": "...",
    "processing_info": {
      "attachments_found": 3,
      "attachments_processed": 2,
      "attachments_skipped": 1
    }
  }
}

// Frontend looks for this structure
var processingInfo = result.processing_info || {};
```

### Issue: "Job not found" errors
**Causes**:
- [ ] Job ID expired - frontend waiting > backend retention time
- [ ] Backend database issue
- [ ] Job ID typo

**Fix**:
- Increase job timeout in frontend (currently 120s)
- Implement job persistence on backend (store in DB)
- Check `/api/job-status/{jobId}` endpoint for 404 errors

### Issue: "Continuous API calls"
**Status**: ✅ FIXED by removing duplicate calls
- Old: logEmailMessages + storeMessageAttachments + callPipelineAPI = 3 calls
- New: Just callPipelineAPI with attachment pre-upload = 1-2 coordinated calls

### Issue: "Script freezes"
**Status**: ✅ FIXED by adding timeouts
- Old: No timeout = blocks forever
- New: 10-15 second timeouts on all requests

---

## Next Steps if Issues Persist

1. **Enable Backend Debug Logging**
   - Log every API call with timestamp
   - Log job creation and status changes
   - Log response data being sent

2. **Use Network Developer Tools**
   - View exact requests/responses
   - Check response headers
   - Verify content-type is application/json

3. **Check Request IDs**
   - Verify each request has a unique UUID in logs
   - Backend should reject duplicates with same ID
   - Backend should log request_id for tracing

4. **Database Health**
   - Check if job records are being created
   - Verify job status table is updating
   - Check for orphaned jobs (stuck in processing)

---

## Deployment Checklist

Before considering the fixes complete:
- [ ] Gmail add-on loads without errors
- [ ] Draft generation completes successfully
- [ ] Labels display in UI
- [ ] Chat functionality works
- [ ] Attachment processing shows correct counts
- [ ] No duplicate API calls in logs
- [ ] No "Timeout waiting for job" errors
- [ ] Backend not receiving multiple identical requests

---

## Performance Monitoring

**Metrics to Track** (after deployment):
- Average API response time (target: < 5 seconds)
- Poll attempts per job (target: 5-10 polls max)
- Error rate (target: < 1%)
- User completion rate (target: > 95%)

**Check Command**:
```bash
# Count polls per job in logs
grep "Polling job" logs.txt | wc -l

# Check for errors
grep "❌\|Error\|Timeout" logs.txt | wc -l

# Check average response time
grep "Response code" logs.txt | tail -20
```

---

## Success Indicators ✅

You'll know the fixes are working when:
1. Draft generation completes in 3-10 seconds
2. Labels appear consistently in UI
3. No timeout errors in execution logs
4. Chat functionality responsive (< 5 second response)
5. Attachment counts display correctly
6. No duplicate API calls in backend logs
7. Users report smooth experience without freezes
