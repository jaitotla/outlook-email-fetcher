# Data Storage Pipeline Structure

## Overview
The data storage pipeline implements user-isolated folder structures for storing emails, attachments, vector databases, and SQL databases within the OpenMailBot Agent.

## Directory Structure

```
agent/
└── data/
    └── {user_id}/                          # Isolated per user
        ├── log_emails/                     # Email message logs
        │   └── {thread_id}/
        │       └── {thread_id}.json        # Thread messages with metadata
        ├── store_attachments/              # Email attachments
        │   └── {thread_id}/
        │       ├── {message_id}_*.{ext}    # Attachment files
        │       └── {message_id}_metadata.json
        ├── vector_db/                      # Vector database storage
        │   ├── chroma.sqlite3              # ChromaDB files
        │   └── ...                         # Other vector DB files (Pinecone, Weaviate)
        └── sql_data/                       # SQLite databases
            ├── chat_thread_processing.db   # Chat interactions & thread processing
            └── draft_processing.db         # Draft generation & processing
```

## API Endpoints

### 1. Log Email Data
**POST** `/api/log-email`

Stores email thread messages with automatic deduplication and cleaning.

**Request:**
```json
{
    "user_id": "user@example.com",
    "thread_id": "thread_123",
    "messages": [
        {
            "message_id": "msg_456",
            "from_address": "sender@example.com",
            "to": ["recipient@example.com"],
            "subject": "Email Subject",
            "timestamp": "2026-01-22T10:42:00Z",
            "body": "Email content..."
        }
    ]
}
```

**Response:**
```json
{
    "success": true,
    "message": "Saved 5 messages (cleaned from 5 original)",
    "user_id": "user@example.com",
    "thread_id": "thread_123",
    "filepath": "/path/to/agent/data/user@example.com/log_emails/thread_123/thread_123.json",
    "original_count": 5,
    "clean_count": 5
}
```

**Features:**
- Automatically removes quoted/nested email content
- Strips HTML tags, URLs, and email disclaimers
- Removes signatures and excessive whitespace
- Stores cleaned messages in JSON format with metadata

### 2. Store Attachments
**POST** `/api/store-attachments`

Stores email attachments in user-isolated directories.

**Request:**
```json
{
    "user_id": "user@example.com",
    "thread_id": "thread_123",
    "message_id": "msg_456",
    "attachments": [
        {
            "filename": "document.pdf",
            "content": "base64_encoded_content...",
            "mime_type": "application/pdf"
        }
    ]
}
```

**Response:**
```json
{
    "success": true,
    "message": "Stored 2 attachments",
    "user_id": "user@example.com",
    "thread_id": "thread_123",
    "saved_files": [
        {
            "filename": "msg_456_document.pdf",
            "filepath": "/path/to/agent/data/user@example.com/store_attachments/thread_123/msg_456_document.pdf",
            "size": 125000,
            "mime_type": "application/pdf"
        }
    ],
    "metadata_file": "/path/to/agent/data/user@example.com/store_attachments/thread_123/msg_456_metadata.json"
}
```

**Features:**
- Stores attachments with message_id prefix to prevent conflicts
- Creates metadata JSON file with attachment information
- Base64 decoding and file validation
- Sanitizes filenames for filesystem compatibility

## Data Cleaning Functions

### `clean_email_body(body: str) -> str`
Cleans email content by removing:
- HTML tags and code
- Scripts and styles
- URLs (http://, https://, www., mailto:)
- Email disclaimers and notices
- Email signatures
- Excessive whitespace

### `extract_new_content(body: str) -> str`
Removes quoted/nested email content, extracting only new message content

### `deduplicate_messages(messages: List[Dict]) -> List[Dict]`
Processes all messages in a thread to extract only new content and clean them

## Directory Helper Functions

### `get_user_data_dir(user_id: str) -> Dict[str, str]`
Returns dictionary of all user data directory paths and creates them if needed:
```python
{
    "user_base": "/path/to/data/{user_id}",
    "log_emails": "/path/to/data/{user_id}/log_emails",
    "attachments": "/path/to/data/{user_id}/store_attachments",
    "vector_db": "/path/to/data/{user_id}/vector_db",
    "sql_data": "/path/to/data/{user_id}/sql_data",
}
```

### `get_sql_db_paths(user_id: str) -> Dict[str, str]`
Returns paths to SQLite database files:
```python
{
    "chat_thread_db": "/path/to/data/{user_id}/sql_data/chat_thread_processing.db",
    "draft_db": "/path/to/data/{user_id}/sql_data/draft_processing.db",
}
```

## Email Cleaning Example

**Before:**
```
On Thu, Jan 22, 2026 at 10:34 AM John Doe <john@company.com> wrote:
> Previous message content
> > Even older content

Thank you for your email.

---
Best regards,
Jane Smith
Software Engineer
Acme Corp
jane@company.com
(555) 123-4567

Confidentiality Notice: This email and its contents are...
```

**After:**
```
Thank you for your email.
```

## Storage Guarantees

- ✅ **User Isolation**: Each user's data is completely isolated in their own directory
- ✅ **Thread Organization**: All messages and attachments for a thread are grouped together
- ✅ **Deduplication**: Nested/quoted email content is automatically removed
- ✅ **Metadata Tracking**: Attachment metadata and statistics are preserved
- ✅ **Data Integrity**: Base64 validation ensures attachment integrity
- ✅ **Filename Safety**: Filenames are sanitized to prevent filesystem issues

## Integration with Other Components

### Vector Database (`vector_db/`)
- Store vector embeddings for RAG queries
- Compatible with ChromaDB, Pinecone, or Weaviate
- Each user has isolated embeddings

### SQL Databases (`sql_data/`)

#### `chat_thread_processing.db`
- Stores chat interactions
- Thread processing history
- Conversation context

#### `draft_processing.db`
- Stores draft generation requests
- Draft processing history
- User preferences and settings

## Usage Example

```python
from main import get_user_data_dir, get_sql_db_paths

# Get user data directories
user_dirs = get_user_data_dir("user@example.com")
print(user_dirs["log_emails"])  # /path/to/data/user@example.com/log_emails

# Get SQLite DB paths
sql_paths = get_sql_db_paths("user@example.com")
db_path = sql_paths["chat_thread_db"]  # /path/to/data/user@example.com/sql_data/chat_thread_processing.db
```

## Data Retention

- Email logs: Indefinite (consider cleanup policies)
- Attachments: Indefinite (consider archival strategies)
- Vector DB: Maintained for RAG operations
- SQL Databases: Maintained for interaction history

---

Last Updated: January 29, 2026
