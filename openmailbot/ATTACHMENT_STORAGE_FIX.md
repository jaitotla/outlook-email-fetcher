# Attachment Storage Troubleshooting Guide

## Issues Fixed

### 1. ✅ Missing `sqlite3` Import
**Problem**: The code uses SQLite database operations but didn't import the module.
**Solution**: Added `import sqlite3` to imports.

### 2. ✅ Incomplete Metadata Reading in Draft Pipeline
**Problem**: The metadata JSON files were opened but not parsed.
**Solution**: Completed the JSON loading logic to properly extract attachment data.

### 3. ✅ Improved Error Handling
**Problem**: Attachment failures were not properly reported.
**Solution**: 
- Added detailed error messages for each attachment
- Better base64 validation with `validate=True`
- Separate error tracking in response
- Enhanced logging with ✅/❌ indicators

### 4. ✅ Directory Permission Issues
**Problem**: Directory creation might fail due to permission issues.
**Solution**: Explicitly set directory mode to `0o755` when creating directories.

## How to Test

### Run the Test Script
```bash
cd /home/ubuntu/openmailbot/openmailbot
python test_attachments.py
```

### Manual cURL Test
```bash
# Create a test file
echo "test content" > test.txt
BASE64_CONTENT=$(base64 -w 0 test.txt)

# Send to endpoint
curl -X POST http://localhost:8000/api/store-attachments \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test@example.com",
    "thread_id": "thread_123",
    "message_id": "msg_456",
    "attachments": [
      {
        "filename": "test.txt",
        "content": "'$BASE64_CONTENT'",
        "mime_type": "text/plain"
      }
    ]
  }'
```

## Expected Response

### Success (Status 200)
```json
{
  "success": true,
  "message": "Stored 1/1 attachments",
  "user_id": "test@example.com",
  "thread_id": "thread_123",
  "saved_files": [
    {
      "filename": "msg_456_test.txt",
      "filepath": "/home/ubuntu/openmailbot/openmailbot/data/test@example.com/store_attachments/thread_123/msg_456_test.txt",
      "size": 12,
      "mime_type": "text/plain"
    }
  ],
  "errors": [],
  "metadata_file": "/home/ubuntu/openmailbot/openmailbot/data/test@example.com/store_attachments/thread_123/msg_456_metadata.json"
}
```

## Common Issues & Solutions

### Issue: "No attachments provided"
**Cause**: Empty attachments array in request.
**Solution**: Ensure you're sending at least one attachment with valid base64 content.

```python
# ❌ Wrong
"attachments": []

# ✅ Correct
"attachments": [
  {
    "filename": "document.pdf",
    "content": "JVBERi0xLjAK...",  # base64 encoded
    "mime_type": "application/pdf"
  }
]
```

### Issue: "Failed to decode base64"
**Cause**: Content is not valid base64 or contains extra characters.
**Solution**: Ensure base64 encoding is correct.

```python
import base64

# ✅ Correct way to encode
content = b"file content here"
encoded = base64.b64encode(content).decode('utf-8')

# Then send encoded string in request
```

### Issue: "Failed to save: Permission denied"
**Cause**: Directory or file permissions issue.
**Solution**: Check directory permissions:

```bash
# Check permissions
ls -la data/

# Fix if needed
chmod 755 data/
chmod -R 755 data/
```

### Issue: Files stored but not accessible later
**Cause**: Metadata file not created properly.
**Solution**: Check if metadata JSON is created:

```bash
# Find all metadata files
find data/ -name "*_metadata.json" -type f

# View contents
cat data/user@example.com/store_attachments/thread_123/msg_456_metadata.json
```

## File Structure After Storage

```
data/
└── user@example.com/
    ├── log_emails/
    │   └── thread_123/
    │       └── thread_123.json
    ├── store_attachments/
    │   └── thread_123/
    │       ├── msg_456_metadata.json
    │       ├── msg_456_document.pdf
    │       ├── msg_456_image.jpg
    │       └── msg_456_data.csv
    ├── vector_db/
    └── sql_data/
```

## Debugging Steps

### 1. Check Server Logs
Watch the FastAPI server output for real-time logs:
```bash
# Terminal 1: Start server (if not running)
cd agent
python main.py

# Look for ✅/❌ indicators in output
```

### 2. Verify Directory Creation
```bash
# Check if data directory structure exists
find data/ -type d | sort

# Should see:
# data/test@example.com/
# data/test@example.com/log_emails
# data/test@example.com/store_attachments
# data/test@example.com/vector_db
# data/test@example.com/sql_data
```

### 3. Check Metadata Files
```bash
# List metadata files
find data/ -name "*_metadata.json"

# View metadata
cat data/test@example.com/store_attachments/thread_123/msg_456_metadata.json | python -m json.tool
```

### 4. Verify Attachment Content
```bash
# Check file sizes
ls -lh data/test@example.com/store_attachments/thread_123/

# Verify PDF files
file data/test@example.com/store_attachments/thread_123/*.pdf

# Check text files
cat data/test@example.com/store_attachments/thread_123/*.txt
```

## Key Improvements Made

| Issue | Before | After |
|-------|--------|-------|
| Error reporting | Silent failures | Detailed error list in response |
| Base64 validation | No validation | `validate=True` parameter |
| Directory handling | Basic `makedirs()` | Explicit mode `0o755` |
| Metadata parsing | Incomplete code | Full JSON load and parse |
| Response format | Success boolean only | Success flag + error list |
| Logging | Minimal output | Detailed ✅/❌ indicators |

## Next Steps

1. **Test with your data**:
   ```bash
   python test_attachments.py
   ```

2. **Monitor logs**:
   - Watch for ✅ (success) and ❌ (error) indicators
   - Check `/home/ubuntu/openmailbot/openmailbot/data/` directory

3. **Use returned metadata**:
   - The response includes `filepath` for each saved file
   - `metadata_file` points to the JSON metadata
   - `errors` array shows any issues

4. **Integrate with draft pipeline**:
   - The draft pipeline reads these stored attachments
   - Uses the metadata files for retrieval
   - Processes content for RAG queries
