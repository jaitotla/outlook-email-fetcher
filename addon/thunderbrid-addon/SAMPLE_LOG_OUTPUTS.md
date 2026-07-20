# 📋 Sample Console Logs - Real Examples

## ✅ PERFECT RUN - 3.6 seconds (FAST FOLDER + FAST LLM)

```
[POPUP] ▶️  SUMMARIZE BUTTON CLICKED at 14:32:15.723
  messageId: 25714 | accountId: imap://test@gmail.com | userEmail: test@gmail.com
[POPUP] 📤 Sending 'summarizeThread' message to background...

[POPUP-send] 📤 Message sent: "summarizeThread"

[BG-listener] 📨 Message received at 14:32:15.851 | action: "summarizeThread"
[BG] ▶️  handleSummarizeThread RECEIVED at 14:32:15.851
  messageId: 25714 | accountId: imap://test@gmail.com | userEmail: test@gmail.com
[BG] ⚙️  Starting parallel init (userId, backendUrl, getThreadMessages)...
  [1/3] Using provided userEmail: test@gmail.com
  [2/3] Fetching backend URL from storage...
    → Backend URL: http://omb.manotr.com
  [3/3] Fetching thread messages...

[getThreadMessages] ▶️  Fetching messages for ID: 25714
  ✓ Got initial message | threadId: 8c71fa1b-b2fb-4b5c-a6df-7ebc8891a0f2 | subject: "Project Status Update"
[getThreadMessages] 🚀 Fast path: Using threadId query (Thunderbird 121+)
  Query returned: 4 messages in 178ms
  Sorted & sliced to 4 messages
  getFull() on 4 msgs took 342ms
[getThreadMessages] ✅ Fast path complete: 4 msgs in 520ms

    → Got 4 messages
[BG] ✅ Parallel init completed in 892ms (total: 892ms)
[BG] ⚡ Init complete — user=test@gmail.com | backend=http://omb.manotr.com

[BG] 📤 Step 1: Logging 4 emails to server for thread 8c71fa1b-b2fb-4b5c-a6df-7ebc8891a0f2...
[_logEmailsToServer] ▶️  POSTing 4 messages to http://omb.manotr.com/api/log-email
  Response received: HTTP 200 in 156ms
[_logEmailsToServer] ✅ Complete in 156ms

[BG] ✅ Logged emails in 156ms (total: 1048ms)
[BG] 📤 Step 2: Firing summarization request (total: 1048ms)...
[BG] 🔄 Background: Starting attachment storage (non-blocking)...

[BG] 📡 Step 3: Calling /api/summarize-thread (http://omb.manotr.com/api/summarize-thread)...
  Response status: 200 OK (1234ms)
  Response has job_id: false | direct summary: true
[BG] ✅ RAG summary received: 1847 chars in 2282ms

[BG] 🏁 handleSummarizeThread COMPLETE in 2282ms | summary: 1847 chars
[BG-listener] ✅ Handler "summarizeThread" completed in 2282ms, sending response

[POPUP-send] ✅ Response received in 2283ms
[POPUP] ✅ Response received in 2283ms
[POPUP] Summary length: 1847 chars | threadId: 8c71fa1b-b2fb-4b5c-a6df-7ebc8891a0f2
[POPUP] ⏱️  TOTAL TIME (popup to display): 2611ms
```

### Analysis:
- ✅ **Fast path** (178ms to query)
- ✅ **Quick log** (156ms)
- ✅ **Quick LLM** (1234ms response)
- ✅ **Total: 2.6 seconds** - Excellent!

---

## ⚠️ SLOW RUN #1 - 7.2 seconds (SLOW FOLDER + FAST LLM)

```
[POPUP] ▶️  SUMMARIZE BUTTON CLICKED at 14:35:42.103
  messageId: 38562 | accountId: imap://work@outlook.com | userEmail: work@outlook.com
[POPUP] 📤 Sending 'summarizeThread' message to background...

[POPUP-send] 📤 Message sent: "summarizeThread"

[BG-listener] 📨 Message received at 14:35:42.234 | action: "summarizeThread"
[BG] ▶️  handleSummarizeThread RECEIVED at 14:35:42.235
  messageId: 38562 | accountId: imap://work@outlook.com | userEmail: work@outlook.com
[BG] ⚙️  Starting parallel init (userId, backendUrl, getThreadMessages)...
  [1/3] Using provided userEmail: work@outlook.com
  [2/3] Fetching backend URL from storage...
    → Backend URL: http://omb.manotr.com
  [3/3] Fetching thread messages...

[getThreadMessages] ▶️  Fetching messages for ID: 38562
  ✓ Got initial message | threadId: null | subject: "Meeting Follow-up"
[getThreadMessages] 🐢 No threadId or query not available, using slow path

[getThreadMessages] 🐢 Slow path: Scanning folder and matching by subject...
  Page 1: 250 messages (total so far: 250)
  Page 2: 250 messages (total so far: 500)
  Page 3: 250 messages (total so far: 750)
  Page 4: 250 messages (total so far: 1000)
  Page 5: 250 messages (total so far: 1250)
  Page 6: 200 messages (total so far: 1450)
  Folder scan completed: 1450 total messages in 3874ms
  Matching by subject: "meeting follow-up"
  Found 3 matching messages in 28ms
  getFull() on 3 msgs took 567ms
[getThreadMessages] ✅ Slow path complete: 3 msgs in 4469ms

    → Got 3 messages
[BG] ✅ Parallel init completed in 4469ms (total: 4469ms)
[BG] ⚡ Init complete — user=work@outlook.com | backend=http://omb.manotr.com

[BG] 📤 Step 1: Logging 3 emails to server for thread work_meeting_followup_001...
[_logEmailsToServer] ▶️  POSTing 3 messages to http://omb.manotr.com/api/log-email
  Response received: HTTP 200 in 203ms
[_logEmailsToServer] ✅ Complete in 203ms

[BG] ✅ Logged emails in 203ms (total: 4672ms)
[BG] 📤 Step 2: Firing summarization request (total: 4672ms)...
[BG] 🔄 Background: Starting attachment storage (non-blocking)...

[BG] 📡 Step 3: Calling /api/summarize-thread (http://omb.manotr.com/api/summarize-thread)...
  Response status: 200 OK (1567ms)
  Response has job_id: false | direct summary: true
[BG] ✅ RAG summary received: 956 chars in 2239ms

[BG] 🏁 handleSummarizeThread COMPLETE in 2239ms | summary: 956 chars
[BG-listener] ✅ Handler "summarizeThread" completed in 6908ms, sending response

[POPUP-send] ✅ Response received in 6909ms
[POPUP] ✅ Response received in 6909ms
[POPUP] Summary length: 956 chars | threadId: work_meeting_followup_001
[POPUP] ⏱️  TOTAL TIME (popup to display): 7137ms
```

### Analysis:
- 🐢 **SLOW FOLDER SCAN** - 3874ms just to list 1450 emails!
- ✅ Quick LLM (1567ms)
- ⚠️ **Total: 7.1 seconds** - Most delay from folder scan
- **Recommendation:** Archive old emails or check Thunderbird performance

---

## 🔴 SLOW RUN #2 - 15.8 seconds (SLOW FOLDER + JOB POLLING)

```
[POPUP] ▶️  SUMMARIZE BUTTON CLICKED at 14:38:21.456
  messageId: 52103 | accountId: imap://archive@company.com | userEmail: archive@company.com
[POPUP] 📤 Sending 'summarizeThread' message to background...

[POPUP-send] 📤 Message sent: "summarizeThread"

[BG-listener] 📨 Message received at 14:38:21.589 | action: "summarizeThread"
[BG] ▶️  handleSummarizeThread RECEIVED at 14:38:21.590
[BG] ⚙️  Starting parallel init...

[getThreadMessages] ▶️  Fetching messages for ID: 52103
[getThreadMessages] 🐢 Slow path: Scanning folder and matching by subject...
  Page 1: 250 messages (total so far: 250)
  Page 2: 250 messages (total so far: 500)
  Page 3: 250 messages (total so far: 750)
  Page 4: 250 messages (total so far: 1000)
  Page 5: 250 messages (total so far: 1250)
  Page 6: 250 messages (total so far: 1500)
  Page 7: 250 messages (total so far: 1750)
  Page 8: 250 messages (total so far: 2000)
  Folder scan completed: 2000 total messages in 5623ms
  Matching by subject: "quarterly results"
  Found 6 matching messages in 42ms
  getFull() on 6 msgs took 834ms
[getThreadMessages] ✅ Slow path complete: 6 msgs in 6499ms

[BG] ✅ Parallel init completed in 6499ms (total: 6499ms)
[BG] 📤 Step 1: Logging 6 emails to server...
[_logEmailsToServer] ✅ Complete in 267ms

[BG] 📡 Step 3: Calling /api/summarize-thread...
  Response status: 200 OK (523ms)
  Response has job_id: true | direct summary: false
[_pollJobStatus] ▶️  Polling job: job_5f8c2d1a9b3e4c2f (max 120000ms)
[_pollJobStatus] Poll #1 at 3000ms...
  Status response: HTTP 200 in 89ms
  Job status: processing
[_pollJobStatus] Poll #2 at 6000ms...
  Status response: HTTP 200 in 102ms
  Job status: processing
[_pollJobStatus] Poll #3 at 9000ms...
  Status response: HTTP 200 in 95ms
  Job status: done
[_pollJobStatus] ✅ Job complete in 9123ms after 3 polls

[BG] ✅ RAG summary received: 2134 chars in 9646ms

[BG] 🏁 handleSummarizeThread COMPLETE in 16145ms | summary: 2134 chars
[BG-listener] ✅ Handler "summarizeThread" completed in 16145ms, sending response

[POPUP-send] ✅ Response received in 16146ms
[POPUP] ⏱️  TOTAL TIME (popup to display): 16474ms
```

### Analysis:
- 🐢 **VERY LARGE FOLDER** - 2000 emails, 5623ms scan
- 📡 **Job queuing** - Backend queued the request (job_id returned)
- 🔄 **Multiple polls** - Had to wait 3 seconds × 3 polls = 9 seconds
- 🔴 **Total: 16.5 seconds** - SLOW!
- **Causes:** 
  - Large archive folder (need cleanup)
  - Backend is busy (check backend load)
  - May need more backend workers

---

## ❌ ERROR RUN - Connection Failed

```
[POPUP] ▶️  SUMMARIZE BUTTON CLICKED at 14:40:15.123
[POPUP] 📤 Sending 'summarizeThread' message to background...

[BG-listener] 📨 Message received at 14:40:15.234 | action: "summarizeThread"
[BG] ⚙️  Starting parallel init...

[getThreadMessages] 🚀 Fast path: Using threadId query...
[getThreadMessages] ✅ Fast path complete: 4 msgs in 523ms

[BG] ✅ Parallel init completed in 678ms

[BG] 📤 Step 1: Logging 4 emails to server...
[_logEmailsToServer] ▶️  POSTing 4 messages to http://omb.manotr.com/api/log-email
[_logEmailsToServer] ❌ Error after 2156ms: Failed to fetch
  At log-email: server 0: TypeError: Failed to fetch

[BG] ⚠️  Log emails failed after 2156ms: TypeError: Failed to fetch

[BG] 📡 Step 3: Calling /api/summarize-thread...
[BG] ⚠️  /api/summarize-thread failed after 1234ms: TypeError: Failed to fetch, falling back to /chat...

[BG] 📡 Step 4: Using fallback /chat API...
[callFlaskAPI] ▶️  SUMMARIZE request to http://omb.manotr.com/chat
[callFlaskAPI] ❌ summarize failed after 3456ms: TypeError: Failed to fetch

[BG] ❌ Exception: TypeError: Failed to fetch
[BG-listener] ❌ Handler "summarizeThread" failed after 6789ms: TypeError: Failed to fetch

[POPUP-send] ❌ Exception after 6790ms: TypeError: Failed to fetch
[POPUP] ❌ SUMMARY FAILED after 6790ms: TypeError: Failed to fetch
```

### Analysis:
- ❌ **Network error** - Can't reach backend
- 🔴 **Possible causes:**
  - Backend server is down
  - Internet connection lost
  - Firewall blocking connection
  - URL is wrong (check settings)
- **Solution:** Check backend is running, check URL in settings

---

## 🔍 Comparing Runs

| Metric | Perfect | Slow #1 | Slow #2 | Error |
|--------|---------|---------|---------|-------|
| getThreadMessages | 520ms | 4469ms | 6499ms | 523ms |
| Log emails | 156ms | 203ms | 267ms | ❌ |
| API/Job | 2282ms | 2239ms | 9646ms | ❌ |
| **Total** | **2.6s** | **7.1s** | **16.5s** | **Failed** |

---

## What to Report

1. **Include the "⏱️ TOTAL TIME" line**
2. **Include slowest component:**
   - `[getThreadMessages] ✅ ... in Xms`
   - `[_logEmailsToServer] ✅ ... in Xms`
   - `[callFlaskAPI] ✅ ... in Xms`
   - `[_pollJobStatus] ✅ ... in Xms`
3. **Include any ❌ errors**
4. **Include full console output if possible**

---
