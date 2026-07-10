# Label Pipeline SQLite Update

## Overview
Updated `agent/services/label_pipeline.py` to store email labels in SQLite database following the same pattern as `chat_pipeline.py`.

## Changes Made

### 1. **Imports Added**
- Added `sqlite3` for database operations
- Added `json` for potential JSON storage
- Added `datetime` for timestamp tracking

### 2. **Database Configuration**
- Added `BASE_DATA_DIR` pointing to `backend/data` (consistent with chat_pipeline.py)
- Database location: `data/{user_id}/sql_data/chat_thread_processing.db`
- Uses existing per-user SQLite database alongside email embeddings

### 3. **New Database Table Schema**
```sql
CREATE TABLE IF NOT EXISTS email_labels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    label TEXT NOT NULL,
    category TEXT,
    topic TEXT,
    subtopic TEXT,
    subject_matter TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, thread_id)
)
```

### 4. **New Methods in EmailLabelPipeline Class**

#### `ensure_user_db(user_id: str)`
- Ensures per-user SQLite database and label table exist
- Creates `sql_data` folder if needed
- Initializes the `email_labels` table

#### `store_label(user_id: str, thread_id: str, label_data: Dict) -> bool`
**Main Upsert Method - Implements the required logic:**
- ✅ Checks if (user_id, thread_id) exists in database
- ✅ If exists: **UPDATE** label, category, topic, subtopic, subject_matter
- ✅ If not exists: **INSERT** new record
- Returns: `True` if successful, `False` if failed
- Logs operations with clear messages

#### `get_label(user_id: str, thread_id: str) -> Optional[Dict]`
- Retrieves stored label for a thread
- Returns dict with: label, category, topic, subtopic, subject_matter, created_at, updated_at
- Returns `None` if not found

#### `get_all_thread_labels(user_id: str) -> List[Dict]`
- Retrieves all labels for a user
- Returns list sorted by updated_at descending
- Useful for analytics and display

#### `delete_label(user_id: str, thread_id: str) -> bool`
- Deletes label for a specific thread
- Returns `True` if successful, `False` otherwise

### 5. **Updated label_and_store_thread() Method**

**Now includes Step 3: SQLite Storage**

```python
# Step 3: Store label in SQLite database
print("\nStep 3: Storing label in SQLite database...")

label_data = {
    'label': label_result.label,
    'category': label_result.category,
    'topic': label_result.topic,
    'subtopic': label_result.subtopic,
    'subject_matter': label_result.subject_matter
}

storage_result = self.store_label(user_id, thread_id, label_data)
```

**Updated Return Value:**
```python
{
    "thread_id": thread_id,
    "user_id": user_id,
    "label_result": {
        "label": label_result.label,
        "category": label_result.category,
        "topic": label_result.topic,
        "subtopic": label_result.subtopic,
        "subject_matter": label_result.subject_matter
    },
    "storage_result": {
        "status": "SUCCESS" | "FAILED",
        "database_path": "data/{user_id}/sql_data/chat_thread_processing.db"
    },
    "status": "SUCCESS" | "PARTIAL_SUCCESS"
}
```

## Database File Structure

```
backend/
└── data/
    └── {user_id}/
        └── sql_data/
            └── chat_thread_processing.db
                ├── Table: email_embeddings (existing)
                ├── Table: attachment_processing (existing)
                └── Table: email_labels (NEW)
```

## Usage Example

```python
from agent.services.label_pipeline import EmailLabelPipeline

# Initialize pipeline
label_pipeline = EmailLabelPipeline(user_id="user@example.com")

# Label and store a thread
result = label_pipeline.label_and_store_thread(
    thread_id="abc123",
    messages=[...],
    user_id="user@example.com"
)

# Retrieve stored label
label_data = label_pipeline.get_label(
    user_id="user@example.com",
    thread_id="abc123"
)

# Get all labels for user
all_labels = label_pipeline.get_all_thread_labels(user_id="user@example.com")
```

## Key Features

✅ **Automatic Database Creation** - Ensures database and tables exist before operations
✅ **Upsert Logic** - Automatically updates existing labels or inserts new ones
✅ **Per-User Isolation** - Each user has isolated database in data/{user_id}/
✅ **Timestamp Tracking** - created_at and updated_at for audit trail
✅ **Unique Constraint** - Only one label per (user_id, thread_id) pair
✅ **Error Handling** - Comprehensive logging and exception handling
✅ **Consistent with Chat Pipeline** - Same directory structure and patterns

## Backward Compatibility

✅ No breaking changes to existing methods
✅ All existing methods continue to work unchanged
✅ Storage is optional and additive to labeling pipeline

## Testing

To test the new functionality:

```python
# 1. Create test data
messages = [
    {
        'user_id': 'test@example.com',
        'from': 'sender@example.com',
        'to': ['recipient@example.com'],
        'subject': 'Test Meeting',
        'body': 'Let\'s schedule a meeting for tomorrow'
    }
]

# 2. Label and store
pipeline = EmailLabelPipeline(user_id='test@example.com')
result = pipeline.label_and_store_thread(
    thread_id='thread_001',
    messages=messages,
    user_id='test@example.com'
)

# 3. Verify storage
label = pipeline.get_label('test@example.com', 'thread_001')
print(label)  # Should return stored label data

# 4. Update label
result2 = pipeline.label_and_store_thread(
    thread_id='thread_001',
    messages=messages,
    user_id='test@example.com'
)
# Should show "Updated label" in logs
```

## Related Files

- **chat_pipeline.py** - Reference implementation for database patterns
- **settings_manager.py** - User settings management
- **ollama_lable_pipline.py** - Ollama-based labeling
- **database/mongodb.py** - Related backend storage

## Database Queries

```sql
-- View all labels for a user
SELECT * FROM email_labels WHERE user_id = 'user@example.com';

-- View label for specific thread
SELECT * FROM email_labels WHERE user_id = ? AND thread_id = ?;

-- Find all labels of type
SELECT * FROM email_labels WHERE user_id = ? AND label = 'meeting';

-- Count labels by type
SELECT label, COUNT(*) as count FROM email_labels 
WHERE user_id = ? GROUP BY label;
```

## Summary

The label pipeline now automatically persists email labels to SQLite with:
- ✅ Upsert logic (update if exists, insert if new)
- ✅ User-scoped isolation
- ✅ Full CRUD operations
- ✅ Timestamp auditing
- ✅ Integrated into existing label_and_store_thread() workflow
