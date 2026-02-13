# Data Storage Pipeline - Architecture Diagram

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         OpenMailBot Agent API                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
            ┌────────────────┐ ┌─────────────┐ ┌──────────────┐
            │ POST /api/     │ │   Other     │ │ Other Routes │
            │ log-email      │ │  Routes     │ │              │
            └────────────────┘ └─────────────┘ └──────────────┘
                    │
         ┌──────────┴──────────┐
         │                     │
         ▼                     ▼
    ┌─────────────────┐  ┌───────────────────┐
    │ deduplicate_    │  │ clean_email_body()│
    │ messages()      │  │                   │
    └─────────────────┘  └───────────────────┘
         │                     │
         └──────────┬──────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │ extract_new_content() │
        └───────────────────────┘
                    │
                    ▼
        ┌─────────────────────────────┐
        │ get_user_data_dir()         │
        │ (Creates isolated dirs)     │
        └─────────────────────────────┘
                    │
         ┌──────────┴──────────┐
         │                     │
         ▼                     ▼
    ┌────────────────┐   ┌──────────────────┐
    │ log_emails/    │   │ vector_db/       │
    │ thread_id/     │   │ (for RAG)        │
    │ thread.json    │   │                  │
    └────────────────┘   └──────────────────┘


POST /api/store-attachments
         │
         ▼
┌──────────────────────────┐
│ Base64 Decode            │
└──────────────────────────┘
         │
         ▼
┌──────────────────────────┐
│ Sanitize Filename        │
└──────────────────────────┘
         │
         ▼
┌──────────────────────────┐
│ Add Message ID Prefix    │
└──────────────────────────┘
         │
         ▼
┌──────────────────────────┐
│ Write to Disk            │
└──────────────────────────┘
         │
         ▼
┌──────────────────────────┐
│ Create Metadata JSON     │
└──────────────────────────┘
         │
         ▼
┌──────────────────────────┐
│ store_attachments/       │
│ thread_id/               │
│ ├── msg_id_file.ext      │
│ └── msg_id_metadata.json │
└──────────────────────────┘
```

## Request Flow Diagram

```
CLIENT REQUEST
     │
     ▼
┌──────────────────────────────────────┐
│ POST /api/log-email                  │
│ {user_id, thread_id, messages}       │
└──────────────────────────────────────┘
     │
     ├─ Validate request ✓
     │
     ├─ Check messages exist ✓
     │
     ├─ get_user_data_dir(user_id)
     │  │
     │  └─ Create: agent/data/user_id/log_emails/
     │
     ├─ Create: agent/data/user_id/log_emails/thread_id/
     │
     ├─ For each message:
     │  ├─ extract_new_content(body)
     │  │  └─ Remove quoted text
     │  │
     │  └─ clean_email_body(new_content)
     │     ├─ Remove HTML
     │     ├─ Remove URLs
     │     ├─ Remove disclaimers
     │     ├─ Remove signatures
     │     └─ Normalize whitespace
     │
     ├─ Create JSON output with:
     │  ├─ thread_id
     │  ├─ user_id
     │  ├─ cleaned messages[]
     │  └─ metadata{}
     │
     ├─ Write: thread_id.json
     │
     └─ Return success response
          │
          └─ JSON with file paths
```

## Directory Tree (Per User)

```
agent/data/
│
└── john@example.com/                                    [USER ID]
    │
    ├── log_emails/                                      [EMAIL LOGS]
    │   ├── thread_001/
    │   │   ├── thread_001.json                  ──┐
    │   │   │   {                                   │
    │   │   │     "thread_id": "thread_001",       │ Contains:
    │   │   │     "user_id": "john@...",           │ • All cleaned messages
    │   │   │     "messages": [...],               │ • Metadata
    │   │   │     "metadata": {...}                │ • Statistics
    │   │   │   }                                  │
    │   │   └─ (more thread.json files...)     ──┘
    │   │
    │   └── thread_002/
    │       └── thread_002.json
    │
    ├── store_attachments/                            [ATTACHMENTS]
    │   ├── thread_001/
    │   │   ├── msg_123_report.pdf          ┐
    │   │   ├── msg_123_spreadsheet.xlsx    ├─ Attachment files
    │   │   ├── msg_123_metadata.json       ├─ (prefixed with msg_id)
    │   │   ├── msg_124_image.png           │
    │   │   └── msg_124_metadata.json       ┘
    │   │
    │   └── thread_002/
    │       └── ...
    │
    ├── vector_db/                                      [VECTOR DATABASE]
    │   ├── chroma.sqlite3
    │   ├── chroma.sqlite3-shm
    │   ├── chroma.sqlite3-wal
    │   └── data/                           (ChromaDB/Pinecone/Weaviate)
    │
    └── sql_data/                                       [SQL DATABASES]
        ├── chat_thread_processing.db      (Chat interactions)
        └── draft_processing.db            (Draft generation)
```

## Data Isolation Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                      agent/data/                            │
│                                                             │
│  ┌────────────────────┐      ┌────────────────────┐       │
│  │  alice@acme.com    │      │   bob@corp.org     │       │
│  │                    │      │                    │       │
│  │  log_emails/   ✓   │      │  log_emails/   ✓   │       │
│  │  attach.../    ✓   │      │  attach.../    ✓   │       │
│  │  vector_db/    ✓   │      │  vector_db/    ✓   │       │
│  │  sql_data/     ✓   │      │  sql_data/     ✓   │       │
│  │                    │      │                    │       │
│  └────────────────────┘      └────────────────────┘       │
│                                                             │
│         NO DATA SHARING                                    │
│         COMPLETELY ISOLATED                                │
│                                                             │
└──────────────────────────────────────────────────────────────┘
```

## Data Cleaning Pipeline

```
INPUT EMAIL BODY
    │
    ▼
┌─────────────────────────────────────────────┐
│ Step 1: Decode HTML Entities                │
│ &nbsp; → (space), &lt; → <, etc.            │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│ Step 2: Extract New Content                 │
│ Remove quoted text:                         │
│ "On Date... wrote:"                         │
│ Lines starting with ">"                     │
│ "From:" headers                             │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│ Step 3: Remove HTML Tags                    │
│ <script>, <style>, <p>, <div>, etc.         │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│ Step 4: Remove URLs                         │
│ http://, https://, www., mailto:            │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│ Step 5: Remove Disclaimers                  │
│ Confidentiality, Legal, Unsubscribe, etc.   │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│ Step 6: Remove Signatures                   │
│ "Best regards", "Sincerely", etc.           │
└─────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│ Step 7: Normalize Whitespace                │
│ Multiple newlines → 2 newlines              │
│ Multiple spaces → 1 space                   │
└─────────────────────────────────────────────┘
    │
    ▼
CLEAN EMAIL BODY
```

## Error Handling Flow

```
REQUEST RECEIVED
    │
    ├─ No user_id? ──→ HTTP 400 (Bad Request)
    │
    ├─ No messages? ──→ HTTP 400 (Bad Request)
    │
    ├─ File write error? ──→ HTTP 500 (Server Error)
    │  │                      └─ Log traceback
    │
    ├─ Base64 decode error? ──→ Mark as error in metadata
    │  │                        └─ Continue processing
    │
    ├─ Directory creation? ──→ Auto-create if missing
    │  │
    └─ Success ──→ HTTP 200 (OK)
                  Return file paths and stats
```

## Integration Points

```
┌──────────────────────────────────────┐
│     Data Storage Pipeline            │
│  (log-email, store-attachments)      │
└──────────────────────────────────────┘
        │      │      │      │
        │      │      │      └─→ EmbeddingService
        │      │      │          (vectors in vector_db/)
        │      │      │
        │      │      └─→ RAGService
        │      │          (queries cleaned emails)
        │      │
        │      └─→ ChatWithThreadPipeline
        │          (uses cleaned email data)
        │
        └─→ DraftWithAttachmentsPipeline
            (accesses attachments & logs)


┌──────────────────────────────────────┐
│     SQL Databases                    │
├──────────────────────────────────────┤
│ chat_thread_processing.db            │  ← Chat interactions
│ draft_processing.db                  │  ← Draft generation
└──────────────────────────────────────┘
        │            │
        └─→ Future: Query/analytics
            Future: Reporting/metrics
```

## Response Structure

```
SUCCESS Response:
┌─────────────────────────────────────┐
│ {                                   │
│   "success": true,                  │
│   "message": "Description...",      │
│   "user_id": "user@example.com",    │
│   "thread_id": "thread_123",        │
│   "filepath": "/path/to/file",      │
│   "original_count": 5,              │
│   "clean_count": 5                  │
│ }                                   │
└─────────────────────────────────────┘

ERROR Response:
┌─────────────────────────────────────┐
│ {                                   │
│   "detail": "Error message..."      │
│ }                                   │
│ (HTTP 400/500 status code)          │
└─────────────────────────────────────┘
```

---

**Last Updated**: January 29, 2026
