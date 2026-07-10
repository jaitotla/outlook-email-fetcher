# Label Pipeline SQLite Implementation - Visual Guide

## Database Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    label_and_store_thread()                     │
│                    (Main Entry Point)                           │
└─────────────────┬───────────────────────────────────────────────┘
                  │
        ┌─────────┴─────────┐
        │                   │
        ▼                   ▼
   Step 1: Label      Step 2: Extract
   (Ollama)           Metadata
        │                   │
        │            ┌──────┴──────┐
        │            │             │
        │            ▼             ▼
        │        user_id      thread_id
        │
        └───────────┬─────────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │   Step 3: UPSERT in   │
        │        SQLite         │
        └───────────┬───────────┘
                    │
            ┌───────┴────────┐
            │                │
            ▼                ▼
     ┌────────────┐   ┌────────────┐
     │   Check    │   │  Check if  │
     │   Labels   │   │ (user_id,  │
     │    Table   │   │ thread_id) │
     │    Exists  │   │   Exists   │
     └────┬───────┘   └────┬───────┘
          │                │
          ▼                │
      CREATE TABLE    ┌────┴──────────┬─────────┐
                      │               │         │
                      ▼               ▼         ▼
                   EXISTS          NOT EXISTS  SKIP
                      │               │
                      ▼               ▼
                  UPDATE           INSERT
                   Label            Label
                      │               │
                      └───────┬───────┘
                              │
                              ▼
                  ┌──────────────────────┐
                  │  Commit Transaction  │
                  │  Return Success/Fail │
                  └──────────────────────┘
```

## Database Schema - email_labels Table

```
┌──────────────────────────────────────────────────────────────┐
│                      email_labels                            │
├──────────────────────────────────────────────────────────────┤
│ Column           │ Type         │ Constraint                 │
├──────────────────┼──────────────┼────────────────────────────┤
│ id               │ INTEGER      │ PRIMARY KEY AUTO_INCREMENT │
│ user_id          │ TEXT         │ NOT NULL                   │
│ thread_id        │ TEXT         │ NOT NULL                   │
│ label            │ TEXT         │ NOT NULL                   │
│ category         │ TEXT         │ NULLABLE                   │
│ topic            │ TEXT         │ NULLABLE                   │
│ subtopic         │ TEXT         │ NULLABLE                   │
│ subject_matter   │ TEXT         │ NULLABLE                   │
│ created_at       │ DATETIME     │ DEFAULT CURRENT_TIMESTAMP  │
│ updated_at       │ DATETIME     │ DEFAULT CURRENT_TIMESTAMP  │
├──────────────────┴──────────────┴────────────────────────────┤
│ UNIQUE(user_id, thread_id)  - One label per thread per user  │
└──────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
openmailbot/
├── backend/
│   └── data/
│       └── {user_id}@domain.com/
│           └── sql_data/
│               └── chat_thread_processing.db
│                   ├── Table: email_embeddings (existing)
│                   ├── Table: attachment_processing (existing)
│                   └── Table: email_labels (NEW)
│
└── agent/
    └── services/
        └── label_pipeline.py (UPDATED)
```

## Upsert Logic Flow Chart

```
                    ┌─ store_label() Called
                    │
    ┌───────────────┴──────────────┐
    │                              │
    ▼                              ▼
Query DB:                   Extract Label Data
SELECT id FROM              ├─ label: "meeting"
email_labels WHERE          ├─ category: "Event"
user_id = ?                 ├─ topic: "scheduling"
AND thread_id = ?           ├─ subtopic: "calendar"
    │                       └─ subject_matter: "..."
    │
    ├──────────────┬──────────────┐
    │              │              │
    ▼              ▼              ▼
  Result?      No Result?    NULL/Error?
    │              │              │
    YES            NO             │
    │              │              │
    ▼              ▼              │
 UPDATE         INSERT          HANDLE
 Record         Record          ERROR
    │              │              │
    │         SET created_at  LOG & RETURN
    │         = NOW()         FALSE
    │              │              │
    ▼              ▼              │
TIMESTAMP:     INSERT INTO    
updated_at     email_labels   
= NOW()        VALUES (...)   
    │              │
    └──────┬───────┘
           │
           ▼
    COMMIT TRANSACTION
           │
           ├─ LOG SUCCESS
           ├─ RETURN TRUE
           │
           ▼
    Ready for Next Operation
```

## Method Signatures

```python
# Database Management
ensure_user_db(user_id: str) -> None
  └─ Creates database and tables if they don't exist

# CRUD Operations
store_label(user_id: str, thread_id: str, label_data: Dict) -> bool
  ├─ Checks if record exists
  ├─ Updates OR inserts
  └─ Returns success status

get_label(user_id: str, thread_id: str) -> Optional[Dict]
  ├─ Retrieves single label
  └─ Returns label data or None

get_all_thread_labels(user_id: str) -> List[Dict]
  ├─ Retrieves all user's labels
  └─ Returns sorted list

delete_label(user_id: str, thread_id: str) -> bool
  ├─ Deletes specific label
  └─ Returns success status

# Main Pipeline Integration
label_and_store_thread(thread_id: str, messages: List, user_id: str) -> Dict
  ├─ Step 1: Label with Ollama
  ├─ Step 2: Extract metadata
  ├─ Step 3: Store in SQLite ← NEW
  └─ Returns combined result
```

## Execution Flow - Complete Pipeline

```
Input: thread_id, messages, user_id
  │
  ├─ Initialize EmailLabelPipeline
  │
  ├─ call: label_and_store_thread()
  │
  ├─ Step 1: Create OllamaEmailLabelPipeline
  │   └─ Call: label_thread(messages)
  │       ├─ Use last message
  │       ├─ Apply rules
  │       └─ LLM classification
  │           └─ Return: EmailLabelOutput
  │
  ├─ Step 2: Extract Metadata
  │   ├─ Get last message
  │   ├─ Extract: subject, from, to, message_id, timestamp
  │   └─ Store: thread_id, user_id, participants
  │
  ├─ Step 3: Store Label in SQLite ← NEW
  │   ├─ Call: store_label(user_id, thread_id, label_data)
  │   │
  │   ├─ In store_label():
  │   │   ├─ Call: ensure_user_db(user_id)
  │   │   │   └─ Create tables if needed
  │   │   │
  │   │   ├─ Open database connection
  │   │   │
  │   │   ├─ Query: SELECT id FROM email_labels
  │   │   │          WHERE user_id=? AND thread_id=?
  │   │   │
  │   │   ├─ If EXISTS:
  │   │   │   └─ UPDATE email_labels SET ...
  │   │   │       WHERE user_id=? AND thread_id=?
  │   │   │
  │   │   └─ If NOT EXISTS:
  │   │       └─ INSERT INTO email_labels VALUES (...)
  │   │
  │   ├─ Commit transaction
  │   └─ Return: True/False
  │
  ├─ Step 4: Build Return Object
  │   ├─ thread_id
  │   ├─ user_id
  │   ├─ label_result: {label, category, topic, subtopic, subject_matter}
  │   ├─ storage_result: {status, database_path}
  │   └─ status: "SUCCESS" or "PARTIAL_SUCCESS"
  │
  └─ Output: Complete result dict with all metadata

Output: {
    "thread_id": "abc123",
    "user_id": "user@example.com",
    "label_result": {...},
    "storage_result": {
        "status": "SUCCESS",
        "database_path": "backend/data/user@example.com/sql_data/..."
    },
    "status": "SUCCESS"
}
```

## Error Handling

```
┌────────────────────────────────────┐
│    store_label() Exception          │
└────────────┬───────────────────────┘
             │
    ┌────────┴────────┐
    │                 │
    ▼                 ▼
Database Error   Other Error
    │                 │
    ▼                 ▼
logger.error()   traceback.format_exc()
    │                 │
    └────────┬────────┘
             │
             ▼
    Return: False
             │
             ├─ storage_status = "FAILED"
             │
             └─ combined_result["status"] = "PARTIAL_SUCCESS"
```

## Sample SQLite Queries

```sql
-- View all labels for a user
SELECT * FROM email_labels 
WHERE user_id = 'john@example.com'
ORDER BY updated_at DESC;

-- Find labels of specific type
SELECT thread_id, subject_matter 
FROM email_labels 
WHERE user_id = ? AND label = 'meeting';

-- Count distribution
SELECT label, COUNT(*) as count 
FROM email_labels 
WHERE user_id = ? 
GROUP BY label 
ORDER BY count DESC;

-- Recent updates
SELECT thread_id, label, updated_at 
FROM email_labels 
WHERE user_id = ? 
AND DATE(updated_at) = DATE('now')
ORDER BY updated_at DESC;

-- Check if thread has label
SELECT EXISTS(
    SELECT 1 FROM email_labels 
    WHERE user_id = ? AND thread_id = ?
);
```

## Feature Comparison: Before vs After

```
FEATURE                BEFORE          AFTER
────────────────────────────────────────────────
Store Labels           ❌ Not stored    ✅ SQLite
Retrieve Labels        ❌ Not available ✅ Yes
Update Labels          ❌ N/A           ✅ Yes (upsert)
Delete Labels          ❌ N/A           ✅ Yes
Audit Trail            ❌ No            ✅ created_at, updated_at
User Isolation         ❌ No            ✅ per-user DB
Persistence            ❌ No            ✅ SQLite
API Consistency        ❌ N/A           ✅ Matches chat_pipeline.py
Error Handling         ⚠️  Basic        ✅ Comprehensive
Multi-user Support     ❌ Limited       ✅ Full
```

## Integration Points

```
label_pipeline.py
    │
    ├─ Imports: sqlite3, os, logging
    │
    ├─ Constants:
    │   └─ BASE_DATA_DIR = "backend/data"
    │
    ├─ Class: EmailLabelPipeline
    │   ├─ New Methods:
    │   │   ├─ ensure_user_db()
    │   │   ├─ store_label() ← MAIN UPSERT METHOD
    │   │   ├─ get_label()
    │   │   ├─ get_all_thread_labels()
    │   │   └─ delete_label()
    │   │
    │   ├─ Updated Methods:
    │   │   └─ label_and_store_thread() ← Now calls store_label()
    │   │
    │   └─ Existing Methods: (unchanged)
    │       ├─ label_email()
    │       ├─ label_thread()
    │       ├─ apply_rules()
    │       └─ classify_with_llm()
    │
    └─ Dependencies:
        ├─ settings_manager.py (user settings)
        └─ ollama_lable_pipline.py (labeling)
```

## Testing Scenarios

### Scenario 1: First-Time Label Storage
```
Input: user_id="new@user.com", thread_id="first_thread"
  ├─ ensure_user_db() → Creates new database
  ├─ store_label() → Query returns NULL
  ├─ Action: INSERT new record
  └─ Result: ✅ Label stored, status="SUCCESS"
```

### Scenario 2: Label Update
```
Input: Same user_id, thread_id but different label
  ├─ ensure_user_db() → Database exists
  ├─ store_label() → Query returns existing record ID
  ├─ Action: UPDATE record with new values
  ├─ updated_at timestamp updated
  └─ Result: ✅ Label updated, status="SUCCESS"
```

### Scenario 3: Multiple Users
```
User A: user_id="alice@example.com", thread_id="t1"
  └─ Stored in: backend/data/alice@example.com/sql_data/...

User B: user_id="bob@example.com", thread_id="t1"
  └─ Stored in: backend/data/bob@example.com/sql_data/...

Result: ✅ Complete isolation - same thread_id, different user_id
```

### Scenario 4: Same User, Multiple Threads
```
User: user_id="user@example.com"
  ├─ thread_id="t1" → label="meeting"
  ├─ thread_id="t2" → label="FYI"
  ├─ thread_id="t3" → label="response"
  └─ All stored in same database with UNIQUE(user_id, thread_id)
```
