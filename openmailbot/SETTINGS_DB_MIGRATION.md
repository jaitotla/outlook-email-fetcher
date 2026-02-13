# Settings Migration: From config_settings.json to Encrypted SQLite Database

## Overview

This document describes the migration from storing user settings in `config_settings.json` file to encrypted SQLite database storage. This provides:

- **Security**: All sensitive keys (API keys, tokens) are encrypted using Fernet encryption
- **Scalability**: Per-user database storage in isolated directories
- **Performance**: Faster retrieval than file-based JSON
- **Isolation**: Each user's settings are completely isolated from others

## Architecture

### Storage Structure

```
agent/data/
└── {user_id}/
    ├── log_emails/
    ├── store_attachments/
    ├── vector_db/
    └── sql_data/
        ├── chat_thread_processing.db  ← Settings stored here (new table)
        └── draft_processing.db
```

### Database Schema

New table added to `chat_thread_processing.db`:

```sql
CREATE TABLE user_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    setting_key TEXT NOT NULL,
    encrypted_value TEXT NOT NULL,
    setting_type TEXT DEFAULT 'general',
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, setting_key, setting_type)
)
```

### Encryption

- **Algorithm**: Fernet (symmetric encryption)
- **Key Derivation**: PBKDF2 with SHA256
- **Salt**: User-specific salt derived from user_id
- **Iterations**: 100,000 (security standard)

## Migration Changes

### 1. New Module: `services/settings_manager.py`

Provides the `SettingsManager` class with these methods:

```python
# Initialize manager
manager = SettingsManager(user_id="user@example.com")

# Save encrypted settings
manager.save_settings(settings_dict, user_id, "general")

# Retrieve and decrypt settings
settings = manager.get_settings(user_id, "general")

# Get specific setting value
api_key = manager.get_setting_value("llm_api_key", user_id, "general")

# Update single setting
manager.update_setting("llm_model", "gpt-4", user_id, "general")

# Delete settings
manager.delete_settings(user_id, "general")
```

### 2. Updated Files

#### `agent/services/chat_pipeline.py`

**Before:**
```python
CONFIG_PATH2 = "/home/ubuntu/openmailbot/openmailbot/agent/config_settings.json"
with open(CONFIG_PATH2, 'r') as f:
    CONFIG2 = json.load(f)

# In __init__:
if user_id and isinstance(CONFIG2, dict) and "users" in CONFIG2 and user_id in CONFIG2["users"]:
    self.effective_settings = CONFIG2["users"][user_id].get("settings", {})
```

**After:**
```python
from services.settings_manager import SettingsManager

# In __init__:
elif user_id:
    settings_manager = SettingsManager(user_id)
    retrieved_settings = settings_manager.get_settings(user_id, "general")
    self.effective_settings = retrieved_settings if retrieved_settings else {}
```

#### `agent/services/draft_pipeline.py`

Same changes as chat_pipeline.py

#### `agent/services/embeddings.py`

**Before:**
```python
def __init__(self):
    self.effective_settings = CONFIG or {}
```

**After:**
```python
def __init__(self, effective_settings: Optional[Dict[str, Any]] = None):
    self.effective_settings = effective_settings if effective_settings else (CONFIG or {})
```

#### `agent/services/llm.py`

**Before:**
```python
def __init__(self):
    self.effective_settings = CONFIG or {}
```

**After:**
```python
def __init__(self, effective_settings: Optional[Dict[str, Any]] = None):
    self.effective_settings = effective_settings if effective_settings else (CONFIG or {})
```

#### `agent/main.py`

**Before:**
```python
@app.post("/api/settings")
async def sync_settings(request: SyncSettingsRequest):
    # Saved to config_settings.json
    with open(config_settings_path, 'w') as f:
        json.dump(config_data, f, indent=2, default=str)
```

**After:**
```python
@app.post("/api/settings")
async def sync_settings(request: SyncSettingsRequest):
    settings_manager = SettingsManager(request.user_id)
    success = settings_manager.save_settings(
        request.settings,
        request.user_id,
        "general"
    )
```

## API Endpoints

### Sync Settings (Modified)

**Endpoint:** `POST /api/settings`

**Request:**
```json
{
  "user_id": "user@example.com",
  "settings": {
    "mode": "custom",
    "llm_provider": "openai",
    "llm_api_key": "sk-proj-...",
    "llm_model": "gpt-4o-mini",
    "embedding_provider": "sentence-transformers",
    "embedding_model": "text-embedding-3-small",
    "user_name": "Swapnil Patil",
    "user_tone": "casual",
    "system_prompt": "keep everything simple and short"
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Settings synced successfully",
  "user_id": "user@example.com",
  "settings_saved": 13,
  "encrypted": true,
  "storage": "data/user@example.com/sql_data/chat_thread_processing.db"
}
```

## Usage Examples

### Example 1: Chat Pipeline with User Settings

```python
from services.chat_pipeline import ChatWithThreadPipeline
from services.settings_manager import SettingsManager

user_id = "user@example.com"

# Settings are automatically loaded from encrypted DB
pipeline = ChatWithThreadPipeline(user_id=user_id)

# Pipeline uses decrypted settings internally
response = await pipeline.chat_with_thread(
    user_id=user_id,
    thread_id="thread_123",
    user_question="Summarize this email thread"
)
```

### Example 2: Direct Settings Access

```python
from services.settings_manager import SettingsManager

user_id = "user@example.com"
manager = SettingsManager(user_id)

# Get all settings (automatically decrypted)
settings = manager.get_settings(user_id, "general")

# Get specific setting
api_key = manager.get_setting_value("llm_api_key", user_id, "general")
model = manager.get_setting_value("llm_model", user_id, "general", "gpt-4o-mini")

# Update a setting
manager.update_setting("user_tone", "formal", user_id, "general")
```

### Example 3: Embedding Service with Settings

```python
from services.embeddings import EmbeddingService
from services.settings_manager import SettingsManager

user_id = "user@example.com"
manager = SettingsManager(user_id)

# Get user's settings
user_settings = manager.get_settings(user_id, "general")

# Pass to embedding service
embedding_service = EmbeddingService(effective_settings=user_settings)

# Use for embeddings
embedding = await embedding_service.generate_embedding("Some text")
```

## Migration Checklist

- [x] Create `services/settings_manager.py` with encryption/decryption
- [x] Update `chat_pipeline.py` to use DB-based settings
- [x] Update `draft_pipeline.py` to use DB-based settings
- [x] Update `embeddings.py` to accept settings parameter
- [x] Update `llm.py` to accept settings parameter
- [x] Update `/api/settings` endpoint in `main.py`
- [ ] Test settings encryption/decryption
- [ ] Test settings retrieval from DB
- [ ] Update frontend to send settings to `/api/settings`
- [ ] Remove `config_settings.json` (after verification)

## Security Considerations

1. **Encryption Keys**: Currently uses user_id + salt. In production:
   - Store salt in environment variable
   - Consider master key rotation
   - Use key management service (KMS) if available

2. **API Keys**: Never log or print encrypted settings containing:
   - llm_api_key
   - embedding_api_key
   - vector_api_key

3. **Database Access**: 
   - Ensure proper file permissions on SQLite files
   - Consider database password protection for production
   - Regular backups of encrypted data

## Backward Compatibility

Settings can still be loaded from `config.json` as fallback:

```python
# In embeddings.py and llm.py:
self.effective_settings = effective_settings if effective_settings else (CONFIG or {})
```

This allows services to work with:
1. User-specific encrypted settings (preferred)
2. Global config fallback (for backward compatibility)
3. Empty settings (will use provider defaults)

## Troubleshooting

### Settings Not Found

```python
# Check if DB exists and has settings
import os
user_db = os.path.join("agent/data", user_id, "sql_data", "chat_thread_processing.db")
if os.path.exists(user_db):
    print("Database exists")
else:
    print("Database not found - settings will be created on first sync")
```

### Decryption Failures

1. Verify user_id matches between save and retrieve
2. Check database integrity with sqlite3
3. Ensure encryption key derivation is consistent

### Performance Issues

- Settings are cached in memory once loaded
- Database queries use indexed UNIQUE constraint
- Consider caching layer if frequent access needed

## Future Enhancements

1. **Settings Versioning**: Track setting changes over time
2. **Audit Logging**: Log all settings access and modifications
3. **Settings Templates**: Pre-defined settings for common use cases
4. **Bulk Operations**: Update multiple users' settings at once
5. **Settings Validation**: Validate settings before encryption
6. **Secrets Management**: Integrate with external secrets manager

## References

- [Cryptography.io Fernet](https://cryptography.io/en/latest/hazmat/primitives/ciphers/fernet/)
- [SQLite Documentation](https://www.sqlite.org/docs.html)
- [PBKDF2 Key Derivation](https://en.wikipedia.org/wiki/PBKDF2)
