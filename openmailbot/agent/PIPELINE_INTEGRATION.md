# Pipeline Integration with User-Isolated Data Storage

## Overview

Both `ChatWithThreadPipeline` and `DraftWithAttachmentsPipeline` have been updated to work seamlessly with the new user-isolated data storage structure implemented in `main.py`.

## Key Changes

### 1. **Data Directory Access**

Both pipelines now have access to user-specific data directories through helper functions:

```python
# Helper function to get all user directories
get_user_data_dir(user_id: str) -> Dict[str, str]
# Returns: {
#     "user_base": "/path/to/data/{user_id}",
#     "log_emails": "/path/to/data/{user_id}/log_emails",
#     "attachments": "/path/to/data/{user_id}/store_attachments",
#     "vector_db": "/path/to/data/{user_id}/vector_db",
#     "sql_data": "/path/to/data/{user_id}/sql_data",
# }

# Helper function to get user's chat/draft database path
get_sql_db_path(user_id: str) -> str
# Returns: "/path/to/data/{user_id}/sql_data/chat_thread_processing.db"
#          or "/path/to/data/{user_id}/sql_data/draft_processing.db"
```

### 2. **Pipeline Initialization**

Pipelines are now initialized **per-user** in the endpoints instead of globally:

#### Before:
```python
# global initialization
chat_pipeline = ChatWithThreadPipeline()
draft_pipeline = DraftWithAttachmentsPipeline()
```

#### After:
```python
@app.post("/chat-with-thread")
async def chat_with_thread(request: ChatWithThreadRequest):
    # Initialize with user_id
    chat_pipeline = ChatWithThreadPipeline(user_id=request.user_id)
    result = await chat_pipeline.process_and_chat(...)
```

### 3. **Database Isolation**

Each user has separate SQLite databases:

- **Chat Processing**: `data/{user_id}/sql_data/chat_thread_processing.db`
- **Draft Processing**: `data/{user_id}/sql_data/draft_processing.db`

Databases are created automatically on first pipeline initialization.

### 4. **Email and Attachment Loading**

Pipelines now read from user-specific directories:

#### Email Logs:
```
Before: /home/manotr/swapnil/email_logs/{thread_id}/
After:  data/{user_id}/log_emails/{thread_id}/
```

#### Attachments:
```
Before: ./email_attachments/{thread_id}/
After:  data/{user_id}/store_attachments/{thread_id}/
```

### 5. **Vector Database Storage**

Vector embeddings are stored in user-specific directories:
```
data/{user_id}/vector_db/
├── chroma.sqlite3
├── chroma.sqlite3-shm
├── chroma.sqlite3-wal
└── data/
```

## Chat Pipeline Changes

### File: `services/chat_pipeline.py`

**Constants Updated:**
```python
# Old
BASE_PATH = "./data_pipeline"
EMAIL_LOGS_PATH = os.getenv("EMAIL_LOGS_PATH", "...")
EMAIL_ATTACHMENTS_PATH = os.getenv("EMAIL_ATTACHMENTS_PATH", "...")
DB_PATH = os.path.join(BASE_PATH, "chat_thread_processing.db")

# New
BASE_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
# Functions handle directory generation per user
```

**Class Initialization:**
```python
# Old
def __init__(self):
    self.db_path = DB_PATH
    self.setup_database()

# New
def __init__(self, user_id: str = None):
    self.user_id = user_id
    self.db_path = get_sql_db_path(user_id) if user_id else None
    if self.db_path:
        self.setup_database()
```

**Methods Updated:**
- `setup_database()` - Creates database in user-specific sql_data directory
- `load_thread_data()` - Reads from user's log_emails directory
- `get_thread_attachments()` - Reads from user's store_attachments directory

## Draft Pipeline Changes

### File: `services/draft_pipeline.py`

**Constants Updated:**
Same as chat pipeline - uses centralized `BASE_DATA_DIR`

**Class Initialization:**
```python
# Old
def __init__(self):
    self.db_path = DB_PATH
    self.setup_database()

# New
def __init__(self, user_id: str = None):
    self.user_id = user_id
    self.db_path = get_sql_db_path(user_id) if user_id else None
    if self.db_path:
        self.setup_database()
```

**Methods Updated:**
- `setup_database()` - Creates database in user-specific sql_data directory
- `get_thread_json_data()` - Reads from user's log_emails directory
- `get_thread_attachments()` - Reads from user's store_attachments directory

## Main API Changes

### File: `main.py`

**Endpoint Updates:**

```python
@app.post("/chat-with-thread")
async def chat_with_thread(request: ChatWithThreadRequest):
    # NOW: Initialize pipeline with user_id
    chat_pipeline = ChatWithThreadPipeline(user_id=request.user_id)
    result = await chat_pipeline.process_and_chat(
        user_id=request.user_id,
        thread_id=request.thread_id,
        user_question=request.question
    )
    return result

@app.post("/draft-with-attachments")
async def draft_with_attachments(request: DraftWithAttachmentsRequest):
    # NOW: Initialize pipeline with user_id
    draft_pipeline = DraftWithAttachmentsPipeline(user_id=request.user_id)
    result = await draft_pipeline.process_email_request(
        user_id=request.user_id,
        thread_id=request.thread_id,
        user_preferences=request.user_preferences
    )
    return result
```

## Data Flow Diagram

```
Client Request
    ↓
FastAPI Endpoint
    ├─ Extract user_id
    ├─ Create pipeline instance with user_id
    │   ├─ Initialize database in user-specific location
    │   ├─ Create user-isolated directories
    │   └─ Setup logging
    └─ Execute pipeline method
        ├─ Load emails from user's log_emails/
        ├─ Load attachments from user's store_attachments/
        ├─ Store vectors in user's vector_db/
        ├─ Update records in user's sql_data/ database
        └─ Return response

Response back to client
```

## Error Handling

Both pipelines include error checks:

```python
# In each data-access method
if not self.user_id:
    logger.error("user_id not set - cannot access data")
    return None/[]

# Database initialization check
if not self.db_path:
    logger.error("Database path not initialized - user_id required")
    return
```

## Benefits of New Structure

✅ **Complete User Isolation**
- Each user's data is completely separate
- No risk of data leakage between users

✅ **Scalability**
- Easily support multiple concurrent users
- Each user has independent resources

✅ **Maintainability**
- Clear separation of concerns
- Per-user database and file management

✅ **Debugging**
- Easy to trace which user's data is being accessed
- Separate logs per user (if logging per user)

✅ **Performance**
- No global state conflicts
- User-specific databases can be optimized independently

## Usage Examples

### Calling Chat Pipeline

```python
# Request
{
    "user_id": "john@example.com",
    "thread_id": "thread_123",
    "question": "What is the status?"
}

# Data Access Path
data/john@example.com/
├── log_emails/thread_123/thread_123.json     (read)
├── store_attachments/thread_123/             (read)
├── vector_db/                                 (read/write)
└── sql_data/chat_thread_processing.db        (read/write)
```

### Calling Draft Pipeline

```python
# Request
{
    "user_id": "alice@company.com",
    "thread_id": "thread_456",
    "user_preferences": {
        "name": "Alice",
        "tone": "professional"
    }
}

# Data Access Path
data/alice@company.com/
├── log_emails/thread_456/thread_456.json     (read)
├── store_attachments/thread_456/             (read)
├── vector_db/                                 (read/write)
└── sql_data/draft_processing.db              (read/write)
```

## Testing Recommendations

1. **Test with multiple users**
   - Verify data isolation between users
   - Ensure no cross-user data access

2. **Test database creation**
   - Verify user-specific databases are created
   - Check database exists on second call

3. **Test file operations**
   - Verify email logs are read from correct user directory
   - Verify attachments are read from correct user directory

4. **Test error handling**
   - Initialize pipeline without user_id
   - Access data with missing user directories
   - Check error messages in logs

5. **Test concurrency**
   - Multiple users accessing pipelines simultaneously
   - Verify no database locking issues

## Migration Notes

- ✅ Old hardcoded paths are no longer used
- ✅ Environment variables (EMAIL_LOGS_PATH, EMAIL_ATTACHMENTS_PATH) are no longer needed
- ✅ Global pipeline instances are replaced with per-request instances
- ✅ All existing functionality is preserved with improved isolation

---

**Last Updated**: January 29, 2026
**Status**: ✅ Complete - Ready for testing and deployment
