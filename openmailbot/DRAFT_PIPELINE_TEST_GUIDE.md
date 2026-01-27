# Draft Pipeline - Quick Test Guide

## 5-Minute Test Setup

### Prerequisites
- All services running (Agent, Backend, Ollama, Flask Embeddings)
- Test email logs and attachments created
- Authentication token available

## Test Data Setup

### 1. Create Test Email Logs

```powershell
# Create directory
New-Item -ItemType Directory -Path "d:\manotr\openmailbot\openmailbot\email_logs\test-draft-1" -Force

# Create test thread JSON
$threadJson = @{
    messages = @(
        @{
            message_id = "msg1"
            from = "sender@example.com"
            to = @("recipient@example.com")
            subject = "Q1 Budget Review"
            timestamp = "2024-01-27T10:00:00Z"
            body = "Hi, can you review the attached Q1 budget forecast?"
        },
        @{
            message_id = "msg2"
            from = "recipient@example.com"
            to = @("sender@example.com")
            subject = "Re: Q1 Budget Review"
            timestamp = "2024-01-27T11:00:00Z"
            body = "Sure, I'll review the numbers. What timeline are you looking at?"
        },
        @{
            message_id = "msg3"
            from = "sender@example.com"
            to = @("recipient@example.com")
            subject = "Re: Q1 Budget Review"
            timestamp = "2024-01-27T14:00:00Z"
            body = "We need approval by end of week. Can you send your feedback by Wednesday?"
        }
    )
} | ConvertTo-Json -Depth 10

$threadJson | Out-File -Path "d:\manotr\openmailbot\openmailbot\email_logs\test-draft-1\test-draft-1.json" -Encoding UTF8
```

### 2. Create Test Attachments

```powershell
# Create attachment directory
New-Item -ItemType Directory -Path "d:\manotr\openmailbot\openmailbot\email_attachments\test-draft-1" -Force

# Create simple test file (PDF simulation - just text)
@"
Q1 BUDGET FORECAST 2024

Department: Operations
Requested Budget: $250,000
Current Allocation: $200,000
Increase Justification: Staff expansion and new tools

Key Line Items:
- Salaries: $180,000
- Software licenses: $40,000
- Hardware: $20,000
- Training: $10,000

Expected ROI: 25% improvement in efficiency
Timeline: Implementation by March 31, 2024
"@ | Out-File -Path "d:\manotr\openmailbot\openmailbot\email_attachments\test-draft-1\budget_forecast.txt" -Encoding UTF8

# Create metadata
$metadata = @{
    message_id = "msg1"
    attachments = @(
        @{
            filename = "budget_forecast.txt"
            filepath = "d:\manotr\openmailbot\openmailbot\email_attachments\test-draft-1\budget_forecast.txt"
        }
    )
} | ConvertTo-Json

$metadata | Out-File -Path "d:\manotr\openmailbot\openmailbot\email_attachments\test-draft-1\msg1_metadata.json" -Encoding UTF8
```

## Test API Calls

### 1. Health Check

```powershell
# Check draft service is healthy
Invoke-RestMethod -Uri "http://localhost:3000/api/draft/health" -Method GET | ConvertTo-Json
```

**Expected Response:**
```json
{
  "success": true,
  "status": "healthy",
  "agent_status": "ok",
  "agent_url": "http://localhost:8000"
}
```

### 2. Generate Draft (No Auth)

For testing without authentication:

```powershell
# Generate draft directly via Python agent
$body = @{
    user_id = "test@example.com"
    thread_id = "test-draft-1"
    user_preferences = @{
        name = "John Doe"
        position = "Operations Manager"
        tone = "professional and concise"
        custom_instructions = "Include specific numbers and timeline"
    }
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/draft-with-attachments" `
    -Method POST `
    -Body $body `
    -ContentType "application/json" | ConvertTo-Json
```

### 3. Generate Draft (With Auth - Node Backend)

```powershell
# Get your JWT token from login endpoint first, then:
$token = "your_jwt_token_here"

$body = @{
    user_id = "test@example.com"
    thread_id = "test-draft-1"
    user_preferences = @{
        name = "John Doe"
        position = "Operations Manager"
        tone = "professional and concise"
        custom_instructions = "Include specific numbers and timeline"
    }
} | ConvertTo-Json

$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
}

Invoke-RestMethod -Uri "http://localhost:3000/api/draft/with-attachments" `
    -Method POST `
    -Body $body `
    -Headers $headers | ConvertTo-Json
```

**Expected Response:**
```json
{
  "success": true,
  "response": "Generated draft email text...",
  "processing_info": {
    "attachments_found": 1,
    "attachments_processed": 1,
    "attachments_skipped": 0,
    "errors": []
  },
  "thread_id": "test-draft-1",
  "user_id": "test@example.com"
}
```

### 4. Get User Preferences

```powershell
$token = "your_jwt_token_here"
$headers = @{
    "Authorization" = "Bearer $token"
}

Invoke-RestMethod -Uri "http://localhost:3000/api/draft/preferences?userId=test@example.com" `
    -Method GET `
    -Headers $headers | ConvertTo-Json
```

### 5. Save User Preferences

```powershell
$token = "your_jwt_token_here"

$body = @{
    userId = "test@example.com"
    preferences = @{
        name = "John Doe"
        position = "Senior Manager"
        tone = "friendly and professional"
        custom_instructions = "Keep it under 200 words, use bullet points"
    }
} | ConvertTo-Json

$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
}

Invoke-RestMethod -Uri "http://localhost:3000/api/draft/preferences" `
    -Method POST `
    -Body $body `
    -Headers $headers | ConvertTo-Json
```

## Verification Checklist

After running tests, verify:

- [ ] Health check returns success
- [ ] Draft response contains generated draft text
- [ ] `processing_info` shows attachment counts
- [ ] Database entry created in `draft_processing.db`
- [ ] ChromaDB folder created in `data_pipeline/draft_cdb_{user_id}/`
- [ ] No errors in logs
- [ ] Draft quality is acceptable

## Database Verification

```powershell
# Check draft processing records
sqlite3.exe .\data_pipeline\draft_processing.db "SELECT user_id, thread_id, attachment_id, processed_status FROM draft_processing LIMIT 10;"

# List user ChromaDB instances
Get-ChildItem .\data_pipeline\ | Where-Object {$_.Name -like "draft_cdb_*"}
```

## Log Monitoring

### Terminal 1 (Ollama)
Should show: "listening on 127.0.0.1:11434"

### Terminal 2 (Python Agent)
Should show:
```
🚀 Starting draft pipeline for user: test@example.com, thread: test-draft-1
📝 Starting hybrid draft generation...
🤖 OpenAI tool decision response: ...
🛠 Tool calls detected: ...
📞 Executing tool: ...
🦙 Calling Ollama for draft generation...
✅ Draft generated successfully
```

### Terminal 3 (Node Backend)
Should show:
```
📝 Draft request - User: test@example.com, Thread: test-draft-1
✅ Draft generated successfully for thread: test-draft-1
```

## Troubleshooting Quick Fixes

| Issue | Solution |
|-------|----------|
| 404 on /api/draft/* | Ensure server.js imported and registered draft routes |
| 503 - Agent unavailable | Check Python agent running on port 8000 |
| "Thread JSON not found" | Verify email_logs path and JSON file exists |
| "No attachments found" | Check email_attachments path and metadata.json |
| Embedding API error | Verify Flask service on port 5050 |
| Ollama error | Run `ollama serve` in separate terminal |
| "Timeout" | Increase timeout or ensure all services responsive |

## Performance Testing

### Test 1: Small Thread (1 message, 1 attachment)
- Expected: 5-10 seconds
- Metrics: Check response time

### Test 2: Large Thread (10 messages, 3 attachments)
- Expected: 10-20 seconds
- Metrics: Check attachment processing count

### Test 3: Cached Attachments (rerun same thread)
- Expected: 2-5 seconds
- Metrics: Should skip already processed attachments

## Example Response Analysis

```json
{
  "success": true,
  "response": "Dear [Recipient],\n\nThank you for your email regarding the Q1 budget review. I have reviewed the attached forecast and find the proposal reasonable.\n\nRegarding the timeline, I can provide my detailed feedback by Wednesday as requested. The 25% efficiency improvement projection looks promising.\n\nLet's schedule a brief call Thursday morning to discuss any remaining questions before final approval.\n\nBest regards,\nJohn Doe",
  
  "processing_info": {
    "attachments_found": 1,
    "attachments_processed": 1,
    "attachments_skipped": 0,
    "errors": []
  }
}
```

**Analysis:**
- ✅ Draft is contextual and references attachment content
- ✅ Follows user tone preferences
- ✅ Addresses all points from thread
- ✅ Ready to send without editing
- ✅ Attachments were processed successfully

## Next Steps

After successful testing:

1. ✅ Create test user accounts
2. ✅ Test with real email data
3. ✅ Collect feedback on draft quality
4. ✅ Fine-tune prompts if needed
5. ✅ Integrate into frontend
6. ✅ Deploy to staging
7. ✅ Deploy to production

---

Need help? Check [DRAFT_PIPELINE_GUIDE.md](DRAFT_PIPELINE_GUIDE.md) for detailed documentation.
