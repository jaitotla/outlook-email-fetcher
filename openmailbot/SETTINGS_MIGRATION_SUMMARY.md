# Settings Migration Complete - Summary

## What Was Changed

The application has been migrated from storing user settings in `config_settings.json` file to encrypted SQLite database storage. This provides better security, scalability, and per-user isolation.

## Files Modified

### 1. **New File: `agent/services/settings_manager.py`**
   - Complete settings management module
   - Handles encryption/decryption of settings
   - Provides database CRUD operations
   - Main class: `SettingsManager`

### 2. **Updated: `agent/services/chat_pipeline.py`**
   - Removed: Direct JSON file reading of `config_settings.json`
   - Added: Import of `SettingsManager`
   - Updated: `__init__` method to load settings from encrypted DB
   - Settings now loaded via: `SettingsManager(user_id).get_settings(user_id, "general")`

### 3. **Updated: `agent/services/draft_pipeline.py`**
   - Same changes as chat_pipeline.py
   - Removed: Direct JSON file reading
   - Added: SettingsManager import
   - Updated: Settings loading from encrypted DB

### 4. **Updated: `agent/services/embeddings.py`**
   - Modified: `__init__` signature to accept `effective_settings` parameter
   - Before: `def __init__(self)`
   - After: `def __init__(self, effective_settings: Optional[Dict[str, Any]] = None)`
   - Falls back to CONFIG if settings not provided

### 5. **Updated: `agent/services/llm.py`**
   - Modified: `__init__` signature to accept `effective_settings` parameter
   - Before: `def __init__(self)`
   - After: `def __init__(self, effective_settings: Optional[Dict[str, Any]] = None)`
   - Falls back to CONFIG if settings not provided

### 6. **Updated: `agent/main.py`**
   - Added: Import of `SettingsManager`
   - Updated: `/api/settings` endpoint to save encrypted settings to DB
   - Before: Saved to `config_settings.json`
   - After: Encrypted and saved to `chat_thread_processing.db`

## Database Schema

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

## Key Features

### ✅ Encryption
- All sensitive data (API keys, tokens) encrypted using Fernet
- Per-user encryption key derived from user_id + salt
- PBKDF2 key derivation with 100,000 iterations

### ✅ Per-User Isolation
- Each user's settings stored in their own database
- Location: `data/{user_id}/sql_data/chat_thread_processing.db`
- Complete isolation from other users' data

### ✅ Backward Compatibility
- Services can still fall back to global `config.json` if no user settings
- Gradual migration - old and new approaches can coexist

### ✅ API Compatibility
- `/api/settings` endpoint maintains same request format
- Response indicates encrypted storage
- Transparent to frontend

## How It Works

### Saving Settings (from Frontend)

```
Frontend sends: POST /api/settings
    ↓
{
  "user_id": "user@example.com",
  "settings": {
    "llm_provider": "openai",
    "llm_api_key": "sk-...",
    ...
  }
}
    ↓
SettingsManager.save_settings()
    ↓
encrypt_settings() - Uses user_id as encryption key
    ↓
Save to SQLite table: user_settings
    ↓
Location: data/user@example.com/sql_data/chat_thread_processing.db
```

### Loading Settings (in Services)

```
ChatWithThreadPipeline.__init__(user_id="user@example.com")
    ↓
SettingsManager(user_id).get_settings(user_id, "general")
    ↓
Retrieve from user_settings table
    ↓
decrypt_settings() - Uses same user_id as key
    ↓
Return decrypted settings dict
    ↓
Pass to EmbeddingService and LLMService
```

## Usage Examples

### Example 1: Chat with User Settings

```python
from services.chat_pipeline import ChatWithThreadPipeline

user_id = "user@example.com"
pipeline = ChatWithThreadPipeline(user_id=user_id)

# Settings automatically loaded from encrypted DB
response = await pipeline.chat_with_thread(
    user_id=user_id,
    thread_id="thread_123",
    user_question="Summarize this email"
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

# Update a setting
manager.update_setting("user_tone", "formal", user_id, "general")
```

### Example 3: Creating Service with User Settings

```python
from services.embeddings import EmbeddingService
from services.settings_manager import SettingsManager

user_id = "user@example.com"
manager = SettingsManager(user_id)
settings = manager.get_settings(user_id, "general")

# Pass user settings to service
embedding_service = EmbeddingService(effective_settings=settings)

# Service now uses user's configured provider and keys
embedding = await embedding_service.generate_embedding("text")
```

## Security Improvements

### Before
- Plaintext API keys in `config_settings.json`
- File-based storage vulnerable to accidental exposure
- Hard to rotate keys
- No audit trail

### After
- ✅ All keys encrypted with Fernet
- ✅ Database-backed storage with proper access control
- ✅ User-specific encryption keys
- ✅ Easy to audit access (can add logging)
- ✅ Easy key rotation support

## Migration Path

### For Existing Users
1. Frontend sends settings to `/api/settings` (unchanged)
2. Settings are encrypted and saved to DB
3. On next request, services load from DB automatically
4. No manual action required

### For New Users
1. Settings flow directly to encrypted DB
2. Never stored in plaintext JSON
3. Complete security from day one

### Optional: Remove Old File
Once verified that all settings are migrated:
```bash
# Backup first
cp agent/config_settings.json agent/config_settings.json.backup

# Then remove (after verifying all users migrated)
rm agent/config_settings.json
```

## Testing Recommendations

### 1. Test Encryption/Decryption
```python
from services.settings_manager import SettingsManager

manager = SettingsManager("test@example.com")
test_settings = {"key1": "value1", "llm_api_key": "sk-secret"}
manager.save_settings(test_settings, "test@example.com", "general")
retrieved = manager.get_settings("test@example.com", "general")
assert retrieved == test_settings
```

### 2. Test Settings Loading in Pipelines
```python
# Sync settings via API
# Then create pipeline with user_id
# Verify settings are loaded and used correctly
```

### 3. Test Backward Compatibility
```python
# Create service without effective_settings
# Should fall back to global CONFIG
```

### 4. Test API Endpoint
```bash
curl -X POST http://localhost:8000/api/settings \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test@example.com",
    "settings": {"llm_provider": "openai", "llm_model": "gpt-4"}
  }'
```

## Configuration

### Environment Variables (Optional for Production)

```bash
# Set custom encryption salt
export ENCRYPTION_KEY_SALT="your-secure-salt"

# Increase security iterations if needed
export ENCRYPTION_ITERATIONS="150000"
```

## Troubleshooting

### Settings Not Loading
1. Check if user database exists: `ls -la data/{user_id}/sql_data/`
2. Verify settings were synced: Check `/api/settings` response
3. Check encryption key consistency (user_id must match)

### Decryption Errors
1. Ensure user_id is consistent between save and load
2. Check database file integrity
3. Verify encryption dependencies are installed

### Performance Issues
1. Settings queries are indexed on (user_id, setting_type)
2. Consider caching decrypted settings in memory
3. Use connection pooling for high-concurrency scenarios

## Next Steps

1. ✅ Deploy `settings_manager.py`
2. ✅ Update services and pipelines
3. ✅ Update `/api/settings` endpoint
4. Test with frontend
5. Monitor settings access in logs
6. Optional: Add settings caching layer
7. Optional: Add audit logging for settings access

## Documentation Files

- **SETTINGS_DB_MIGRATION.md** - Detailed technical migration guide
- **SETTINGS_IMPLEMENTATION_GUIDE.md** - Implementation patterns and examples

## Support

For issues or questions about the migration:
1. Check the implementation guide for code examples
2. Review the SettingsManager docstrings
3. Check database logs in `data/{user_id}/sql_data/`
4. Verify encryption dependencies: `pip list | grep cryptography`
