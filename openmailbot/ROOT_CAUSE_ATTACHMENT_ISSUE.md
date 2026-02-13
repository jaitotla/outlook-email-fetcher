# 🔴 ROOT CAUSE FOUND: Why Gmail Add-on Doesn't Store Attachments

##THE ISSUE

**The Gmail add-on filters attachments to ONLY 4 file types:**
- `.pdf`
- `.csv`
- `.pptx`
- `.ppt`

**If an email has attachments with OTHER extensions** (like `.txt`, `.doc`, `.docx`, `.xlsx`, `.jpg`, etc.), the add-on **silently returns `null` WITHOUT sending ANY request to the server**.

### Location in Code
**File:** [addon/gmail_summariser.gs](addon/gmail_summariser.gs#L1140-L1157)

```javascript
// Define allowed file extensions
var allowedExtensions = ['.pdf', '.csv', '.pptx', '.ppt'];

// Filter attachments by allowed extensions  
var filteredBlobs = blobs.filter(function(b) {
  var filename = b.getName ? b.getName() : "";
  var lowerFilename = filename.toLowerCase();
  return allowedExtensions.some(function(ext) {
    return lowerFilename.endsWith(ext);
  });
});

// If no valid attachments after filtering, return null
if (filteredBlobs.length === 0) {
  return null;  // <-- SILENTLY EXITS WITHOUT SENDING TO SERVER!
}
```

## SOLUTION

### Option 1: Expand Allowed File Types (RECOMMENDED)
Add more file extensions to the allowed list:

```javascript
var allowedExtensions = [
  '.pdf',     // PDF documents
  '.csv',     // CSV data files
  '.xlsx',    // Excel spreadsheets (NEW)
  '.xls',     // Excel 97-2003 (NEW)
  '.pptx',    // PowerPoint
  '.ppt',     // PowerPoint 97-2003
  '.docx',    // Word documents (NEW)
  '.doc',     // Word 97-2003 (NEW)
  '.txt',     // Text files (NEW)
  '.json',    // JSON data (NEW)
  '.xml',     // XML data (NEW)
  '.sql'      // SQL scripts (NEW)
];
```

### Option 2: Accept ALL Attachments
Remove the filter entirely:

```javascript
// Send all attachments without filtering
var filteredBlobs = blobs;  // Use all attachments
```

### Option 3: Allow User Configuration
Let users configure which file types to accept in settings.

## HOW TO FIX

### Step 1: Update gmail_summariser.gs
Replace line 1139 with expanded extensions:

```javascript
  // Define allowed file extensions
  var allowedExtensions = ['.pdf', '.csv', '.xlsx', '.xls', '.pptx', '.ppt', '.docx', '.doc', '.txt', '.json', '.xml'];
```

### Step 2: Deploy to Google Apps Script
1. Open Google Apps Script editor
2. Paste the updated code
3. Click "Deploy" → "New Deployment" → "Test Deployments"
4. Confirm the changes

### Step 3: Test
1. Send an email with various attachment types (.txt, .docx, .xlsx, etc.)
2. Run the "Draft with Attachments" button
3. Check server logs for incoming requests
4. Verify files appear in: `agent/data/{user}/store_attachments/{thread}/`

## VERIFICATION

After fixing, you should see files in:
```
agent/data/patilswapnil5090@gmail.com/store_attachments/
├── thread_123/
│   ├── msg_456_document.pdf        ✅ (already worked)
│   ├── msg_456_data.xlsx           ✅ (NOW WORKS after fix)
│   ├── msg_456_notes.txt           ✅ (NOW WORKS after fix)
│   ├── msg_456_report.docx         ✅ (NOW WORKS after fix)
│   └── msg_456_metadata.json
```

## WHY THIS HAPPENED

The Gmail add-on was designed with conservative security - only allowing "safe" document formats:
- PDF (read-only documents)
- CSV (data files)
- PowerPoint & Word (office documents)

But this missed common formats like:
- `.xlsx` - Excel spreadsheets (financial data)
- `.txt` - Text files
- `.json` / `.xml` - Data interchange formats

## NEXT STEP

**Add your needed file extensions to the allowed list and redeploy the add-on.**

The endpoint itself (`/api/store-attachments`) works perfectly - it's the Gmail add-on's filter that's preventing files from being sent!
