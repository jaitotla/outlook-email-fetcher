# Debugging Attachment Storage Issue

## Problem Statement
- Test script (`test_attachments.py`) stores attachments successfully ✅
- Main application is NOT storing attachments ❌
- Empty folder: `agent/data/patilswapnil5090@gmail.com/store_attachments/`

## Likely Root Causes

### 1. **Request Not Reaching Endpoint**
The Gmail add-on might not be sending the request at all, or it's going to the wrong URL.

**Check:**
```bash
# Monitor server logs for incoming requests
# Look for: "store-attachments endpoint called for user:"
```

### 2. **Incorrect Request Format**
The Gmail add-on sends data, but the format might not match expectations.

**Expected format from Gmail add-on:**
```javascript
{
  "user_id": "patilswapnil5090@gmail.com",        // Session.getEffectiveUser().getEmail()
  "thread_id": "thread_123",                       // Gmail thread ID
  "message_id": "msg_456",                         // Gmail message ID
  "attachments": [
    {
      "filename": "document.pdf",
      "content": "base64_encoded_bytes",           // Utilities.base64Encode(bytes)
      "mime_type": "application/pdf"
    }
  ]
}
```

### 3. **No Attachments Found**
The Gmail add-on might not be finding any attachments to send.

**Check in gmail_summariser.gs:**
- Line 1115-1180: `storeMessageAttachments()` function
- Only processes: `.pdf, .csv, .pptx, .ppt`
- Other formats are filtered out

### 4. **Base64 Encoding Issue**
The Gmail add-on encodes with `Utilities.base64Encode()` - make sure it's valid.

### 5. **FLASK_SERVER_URL Not Configured**
The Gmail add-on requires `FLASK_SERVER_URL` property:
```javascript
var flaskUrl = PropertiesService.getScriptProperties().getProperty("FLASK_SERVER_URL");
```

If missing, it throws error: "FLASK_SERVER_URL not configured."

## How to Debug

### Step 1: Check Server Logs
Add enhanced logging to see if endpoint is called:

```bash
# Terminal 1: Start agent server with visible logging
cd /home/ubuntu/openmailbot/openmailbot/agent
python main.py
```

### Step 2: Run Debug Script
```bash
# Terminal 2: Run the debug script
cd /home/ubuntu/openmailbot/openmailbot
python debug_attachments.py
```

**Expected output:**
```
===============================================================================
SENDING DEBUG REQUEST TO STORE-ATTACHMENTS
===============================================================================

Payload:
{
  "user_id": "patilswapnil5090@gmail.com",
  "thread_id": "test_thread_debug_001",
  "message_id": "msg_debug_001",
  "attachments": [...]
}

📤 Sending POST request to http://localhost:8000/api/store-attachments
Waiting for response...

Response Status: 200

Response Body:
{
  "success": true,
  "message": "Stored 1/1 attachments",
  "saved_files": [
    {
      "filename": "msg_debug_001_debug_test.txt",
      "filepath": "/home/ubuntu/openmailbot/openmailbot/agent/data/patilswapnil5090@gmail.com/store_attachments/test_thread_debug_001/msg_debug_001_debug_test.txt",
      "size": 38,
      "mime_type": "text/plain"
    }
  ],
  "errors": [],
  "metadata_file": "/home/ubuntu/openmailbot/openmailbot/agent/data/patilswapnil5090@gmail.com/store_attachments/test_thread_debug_001/msg_debug_001_metadata.json"
}
```

### Step 3: Check Gmail Add-on Configuration

In the Gmail add-on settings (or script properties):

1. **Verify `FLASK_SERVER_URL` is set**
   ```
   FLASK_SERVER_URL = "http://YOUR_AGENT_SERVER_ADDRESS/api"
   // or
   FLASK_SERVER_URL = "http://localhost:8000/api"
   ```

2. **Verify `BACKEND_API_URL` is set**
   ```
   BACKEND_API_URL = "http://YOUR_BACKEND_ADDRESS"
   ```

### Step 4: Test from Gmail Add-on
In the Gmail add-on:

1. Open an email with attachments (.pdf, .csv, .pptx, etc.)
2. Check browser console for errors
3. Check server logs for incoming request

## Server Log Output Format

When an attachment request arrives, you should see:

```
============================================================
📥 STORE-ATTACHMENTS ENDPOINT CALLED
============================================================
User: patilswapnil5090@gmail.com
Thread: thread_123
Message: msg_456
Attachments count: 1
  [0] document.pdf (12345 bytes of base64)
============================================================

✅ Request validation passed
   Attachments: 1

📂 Getting user data directories...
✅ Attachment dir: /home/ubuntu/openmailbot/openmailbot/agent/data/patilswapnil5090@gmail.com/store_attachments
✅ Thread dir: /home/ubuntu/openmailbot/openmailbot/agent/data/patilswapnil5090@gmail.com/store_attachments/thread_123
✅ Directory created/exists

🔄 Processing 1 attachments...

  [Attachment 1/1]
    Original filename: document.pdf
    Content size: 12345 bytes
    MIME type: application/pdf
    Sanitized filename: document.pdf
    Final filepath: /home/ubuntu/openmailbot/openmailbot/agent/data/patilswapnil5090@gmail.com/store_attachments/thread_123/msg_456_document.pdf
✅ Saved attachment: msg_456_document.pdf (12345 bytes)
✅ Metadata saved to /home/ubuntu/.../msg_456_metadata.json
✅ Stored 1/1 attachments for user patilswapnil5090@gmail.com
```

## Next Steps

1. **Add detailed logging** (already done in updated code)
2. **Run debug script** to verify endpoint works
3. **Check Gmail add-on logs** to see if it's sending requests
4. **Verify FLASK_SERVER_URL** is properly configured
5. **Check email attachments** have allowed extensions (.pdf, .csv, .pptx, .ppt)

## Files Modified

- [main.py](main.py#L816-L860) - Enhanced endpoint logging
- [debug_attachments.py](debug_attachments.py) - New debug script
