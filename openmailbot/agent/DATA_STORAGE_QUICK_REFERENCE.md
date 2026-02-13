# Data Storage Pipeline - Quick Reference

## ✅ Implementation Summary

The data storage pipeline has been successfully added to `agent/main.py` with the following components:

### 1. **Imports Added**
```python
import os
import json
import base64
import re
import html
```

### 2. **Configuration**
- `BASE_DATA_DIR`: Automatically points to `agent/data/` folder
- User-isolated directory structure created automatically

### 3. **Helper Functions**

#### Directory Management
- `get_user_data_dir(user_id)` - Returns all user data directory paths
- `get_sql_db_paths(user_id)` - Returns SQLite database file paths

#### Data Cleaning
- `clean_email_body(body)` - Removes HTML, URLs, disclaimers, signatures
- `extract_new_content(body)` - Extracts only new message content
- `deduplicate_messages(messages)` - Processes all messages in thread

### 4. **Data Models**
```
EmailMessage
├── message_id
├── from_address
├── to
├── subject
├── timestamp
└── body

LogEmailRequest
├── user_id
├── thread_id
└── messages[]

AttachmentData
├── filename
├── content (base64)
└── mime_type

StoreAttachmentsRequest
├── user_id
├── thread_id
├── message_id
└── attachments[]
```

### 5. **API Endpoints**

#### POST `/api/log-email`
- Stores email threads with automatic cleaning
- Removes nested/quoted content
- Strips HTML, URLs, disclaimers
- Path: `agent/data/{user_id}/log_emails/{thread_id}/{thread_id}.json`

#### POST `/api/store-attachments`
- Stores base64-encoded attachments
- Creates metadata files
- Path: `agent/data/{user_id}/store_attachments/{thread_id}/{message_id}_*`

## 📁 Folder Structure

```
agent/data/
└── user@example.com/
    ├── log_emails/
    │   └── thread_123/
    │       └── thread_123.json
    ├── store_attachments/
    │   └── thread_123/
    │       ├── msg_456_document.pdf
    │       └── msg_456_metadata.json
    ├── vector_db/
    │   └── (chroma/pinecone files)
    └── sql_data/
        ├── chat_thread_processing.db
        └── draft_processing.db
```

## 🚀 Usage Examples

### Logging Email Thread

```python
import requests

payload = {
    "user_id": "user@example.com",
    "thread_id": "thread_123",
    "messages": [
        {
            "message_id": "msg_456",
            "from_address": "sender@example.com",
            "to": ["recipient@example.com"],
            "subject": "Subject",
            "timestamp": "2026-01-22T10:42:00Z",
            "body": "Email content..."
        }
    ]
}

response = requests.post("http://localhost:8000/api/log-email", json=payload)
print(response.json())
```

### Storing Attachments

```python
import requests
import base64

with open("document.pdf", "rb") as f:
    b64_content = base64.b64encode(f.read()).decode()

payload = {
    "user_id": "user@example.com",
    "thread_id": "thread_123",
    "message_id": "msg_456",
    "attachments": [
        {
            "filename": "document.pdf",
            "content": b64_content,
            "mime_type": "application/pdf"
        }
    ]
}

response = requests.post("http://localhost:8000/api/store-attachments", json=payload)
print(response.json())
```

### Using Directory Helpers

```python
from main import get_user_data_dir, get_sql_db_paths

# Get all user directories
dirs = get_user_data_dir("user@example.com")
print(dirs["log_emails"])      # /path/to/agent/data/user@example.com/log_emails
print(dirs["attachments"])     # /path/to/agent/data/user@example.com/store_attachments
print(dirs["vector_db"])       # /path/to/agent/data/user@example.com/vector_db
print(dirs["sql_data"])        # /path/to/agent/data/user@example.com/sql_data

# Get SQLite database paths
db_paths = get_sql_db_paths("user@example.com")
chat_db = db_paths["chat_thread_db"]    # Chat processing database
draft_db = db_paths["draft_db"]         # Draft processing database
```

## 🔍 Email Cleaning Features

### What Gets Removed
- ✅ HTML tags and scripts
- ✅ All URLs (http://, https://, www., mailto:)
- ✅ Email disclaimers
- ✅ Signatures and separator lines
- ✅ Quoted/nested email content
- ✅ Excessive whitespace

### What's Preserved
- ✅ Actual message content
- ✅ Core information
- ✅ User intent and meaning

## 📊 Data Isolation

Each user's data is completely isolated:
- No cross-user data sharing
- Separate vector databases
- Separate SQL databases
- Separate email and attachment storage

## 🔗 Integration Points

### With Services
- `ChatWithThreadPipeline` - Can access cleaned email data
- `DraftWithAttachmentsPipeline` - Can access attachments and logs
- `EmbeddingService` - Stores vectors in `vector_db/`
- `RAGService` - Queries cleaned email content

### With Databases
- **chat_thread_processing.db** - For chat/thread interactions
- **draft_processing.db** - For draft generation tracking

---

**Location**: `/home/ubuntu/openmailbot/openmailbot/agent/main.py`
**Lines**: 1-918 (updated)
**Documentation**: See `DATA_STORAGE_STRUCTURE.md` for detailed reference
