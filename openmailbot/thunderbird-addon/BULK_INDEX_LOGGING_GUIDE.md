# Thunderbird Addon: Bulk Index Email - Logging Guide

## What's Being Logged

When you click the **"Index Email"** button in Advanced Settings, the addon now logs:

### 1. **Button Click Detection**
```
🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴
🔴 BULK INDEX EMAIL BUTTON CLICKED!
🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴
```

### 2. **Configuration Details**
- Processing period (months)
- Date range being scanned
- Backend URL being used
- User ID
- Config loaded from addon_config.json

### 3. **For Each Email Being Indexed**

#### Store Attachments Call:
```
[OpenMailBot][BulkIndex] POST http://YOUR_SERVER:5050/api/store-attachments | thread_id=... | msg_id=... | attachments=2 [invoice.pdf, report.xlsx]
```

#### Label Email Call (Most Important):
```
[OpenMailBot][BulkIndex] ╔╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
[OpenMailBot][BulkIndex] ║ CALLING: POST http://YOUR_SERVER:5050/api/label-email
[OpenMailBot][BulkIndex] ║ thread_id: <thread_123>
[OpenMailBot][BulkIndex] ║ msg_id: 456
[OpenMailBot][BulkIndex] ║ subject: "Important Meeting Notes"
[OpenMailBot][BulkIndex] ║ from: "john@example.com"
[OpenMailBot][BulkIndex] ║ payload: { "user_id": "user@example.com", "thread_id": "...", "messages": [...] }
[OpenMailBot][BulkIndex] ╚╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
```

#### API Request Details:
```
[OpenMailBot][API] 📤 REQUEST
[OpenMailBot][API] URL: http://YOUR_SERVER:5050/api/label-email
[OpenMailBot][API] Method: POST
[OpenMailBot][API] Content-Type: application/json
[OpenMailBot][API] Payload size: 1254 bytes
[OpenMailBot][API] Full payload: { complete JSON payload }
```

#### API Response Details:
```
[OpenMailBot][API] 📥 RESPONSE
[OpenMailBot][API] Status: 200 OK
[OpenMailBot][API] OK: true
[OpenMailBot][API] Body size: 256 bytes
[OpenMailBot][API] Body: { complete response JSON }
[OpenMailBot][API] ✅ Parsed JSON: { label: "Finance", ... }
```

### 4. **Summary After Completion**
```
[OpenMailBot][BulkIndex] ■ Finished | status=done | totalProcessed=45 | labeled=44 | errors=1 | filtered=0
```

---

## How to View the Logs

### **Option 1: Browser Console (Recommended)**

1. Open Thunderbird
2. Press **Ctrl+Shift+I** (or **Cmd+Option+I** on Mac) to open Developer Tools
3. Click on the **Console** tab
4. Click **"Index Email"** button
5. Watch the logs appear in the console in real-time

### **Option 2: Terminal (If running Thunderbird from terminal)**

```bash
# Linux
thunderbird -console 2>&1 | tee thunderbird-logs.txt

# Mac
/Applications/Thunderbird.app/Contents/MacOS/thunderbird -console 2>&1 | tee thunderbird-logs.txt
```

---

## What to Look For If It's Not Working

### ❌ **Issue: No logs appearing**
- Make sure Developer Tools Console is open
- Click the button again with console visible
- Check if the button is even firing (look for the red box emoji)

### ❌ **Issue: URL shows `undefined`**
- Backend URL not set in settings
- Check: Settings → General → Backend URL
- Should be something like: `http://43.204.98.38:5050`

### ❌ **Issue: 404 or 500 Error**
- Check the Response Status in logs
- Server might not have `/api/label-email` endpoint
- Verify backend is running

### ❌ **Issue: Connection refused / Network error**
- Backend URL is incorrect or server is down
- Check you can reach it: `curl http://YOUR_SERVER:5050/api/ping`

---

## Key Log Patterns to Search For

| What | Search Pattern |
|------|-----------------|
| When button clicked | `🔴 BULK INDEX EMAIL BUTTON CLICKED!` |
| API URL called | `[OpenMailBot][API] URL:` |
| Request payload | `[OpenMailBot][API] Payload size:` |
| Response status | `[OpenMailBot][API] Status:` |
| Fetch errors | `[OpenMailBot][API] ❌ FETCH ERROR:` |
| Bulk process errors | `[OpenMailBot] ❌ BULK PROCESS ERROR:` |

---

## Example: Successfully Indexed Email

```
🔴 BULK INDEX EMAIL BUTTON CLICKED!

[OpenMailBot][BulkStart] Processing last 3 months
[OpenMailBot][BulkStart] Backend URL: http://43.204.98.38:5050
[OpenMailBot][BulkIndex] Processing batch 1 (10 messages)

[OpenMailBot][BulkIndex] ╔╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
[OpenMailBot][BulkIndex] ║ CALLING: POST http://43.204.98.38:5050/api/label-email
[OpenMailBot][BulkIndex] ║ thread_id: abc123
[OpenMailBot][BulkIndex] ║ subject: "Project Update"
[OpenMailBot][BulkIndex] ╚╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌

[OpenMailBot][API] 📤 REQUEST
[OpenMailBot][API] URL: http://43.204.98.38:5050/api/label-email
[OpenMailBot][API] Status: 200 OK
[OpenMailBot][API] ✅ Parsed JSON: {"label": "Projects"}

[OpenMailBot][BulkIndex] ✓ label-email OK | thread_id=abc123
```

---

## Example: Error Case

```
🔴 BULK INDEX EMAIL BUTTON CLICKED!

[OpenMailBot][BulkIndex] ║ CALLING: POST http://43.204.98.38:5050/api/label-email
[OpenMailBot][API] 📤 REQUEST
[OpenMailBot][API] Status: 500 Internal Server Error
[OpenMailBot][API] Body: {"error": "Database connection failed"}
[OpenMailBot][API] ❌ FETCH ERROR: label-email: server 500: {"error": "Database connection..."}
[OpenMailBot] ❌ BULK PROCESS ERROR: label-email: server 500: {"error": "Database connection..."}
```

---

## Now You Have Full Visibility! 

Every single API call is now logged with:
- ✅ Exact URL
- ✅ HTTP method
- ✅ Request payload
- ✅ Response status
- ✅ Response body
- ✅ Any errors

Use this to debug and identify exactly where the issue is occurring.
