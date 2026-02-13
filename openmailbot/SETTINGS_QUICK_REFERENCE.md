# Quick Reference: Settings Manager Usage

## One-Line Summary
Settings are now stored in encrypted SQLite database instead of `config_settings.json`, providing better security and per-user isolation.

## For Frontend/API Developers

### Setting User Settings
```bash
POST /api/settings
Content-Type: application/json

{
  "user_id": "user@example.com",
  "settings": {
    "llm_provider": "openai",
    "llm_api_key": "sk-proj-...",
    "llm_model": "gpt-4o-mini",
    "embedding_provider": "sentence-transformers",
    "user_tone": "casual"
  }
}
```

### Response
```json
{
  "success": true,
  "message": "Settings synced successfully",
  "user_id": "user@example.com",
  "settings_saved": 5,
  "encrypted": true,
  "storage": "data/user@example.com/sql_data/chat_thread_processing.db"
}
```

## For Backend Developers

### Import
```python
from services.settings_manager import SettingsManager
```

### Get Settings
```python
manager = SettingsManager(user_id)
settings = manager.get_settings(user_id, "general")
# Returns: Dict with decrypted settings, or None if not found
```

### Get Specific Setting
```python
manager = SettingsManager(user_id)
api_key = manager.get_setting_value("llm_api_key", user_id, "general")
# Returns: Value or None
```

### Save Settings
```python
manager = SettingsManager(user_id)
success = manager.save_settings(settings_dict, user_id, "general")
# Returns: True if successful
```

### Update One Setting
```python
manager = SettingsManager(user_id)
manager.update_setting("user_tone", "formal", user_id, "general")
```

### Delete Settings
```python
manager = SettingsManager(user_id)
manager.delete_settings(user_id, "general")
```

## In Pipelines

### Chat Pipeline
```python
from services.chat_pipeline import ChatWithThreadPipeline

pipeline = ChatWithThreadPipeline(user_id="user@example.com")
# Settings automatically loaded from encrypted DB
```

### Draft Pipeline
```python
from services.draft_pipeline import DraftPipeline

pipeline = DraftPipeline(user_id="user@example.com")
# Settings automatically loaded from encrypted DB
```

## In Services

### Embedding Service
```python
from services.embeddings import EmbeddingService
from services.settings_manager import SettingsManager

manager = SettingsManager(user_id)
settings = manager.get_settings(user_id, "general")
embedding_service = EmbeddingService(effective_settings=settings)
```

### LLM Service
```python
from services.llm import LLMService
from services.settings_manager import SettingsManager

manager = SettingsManager(user_id)
settings = manager.get_settings(user_id, "general")
llm_service = LLMService(effective_settings=settings)
```

## Common Patterns

### Pattern 1: Load and Use
```python
user_id = "user@example.com"
manager = SettingsManager(user_id)
settings = manager.get_settings(user_id, "general")
service = SomeService(effective_settings=settings)
```

### Pattern 2: With Default Fallback
```python
manager = SettingsManager(user_id)
tone = manager.get_setting_value("user_tone", user_id, "general", "professional")
```

### Pattern 3: Update and Refresh
```python
manager = SettingsManager(user_id)
manager.update_setting("llm_model", "gpt-4", user_id, "general")
updated_settings = manager.get_settings(user_id, "general")
```

## Database Location
```
data/{user_id}/sql_data/chat_thread_processing.db
└── user_settings table (encrypted values)
```

## Encryption Details
- **Algorithm**: Fernet (symmetric)
- **Key**: Derived from user_id + salt using PBKDF2
- **Iterations**: 100,000 (security standard)
- **Stored As**: Base64 encoded encrypted bytes

## No Changes Required For
- ✅ Direct calls to ChatWithThreadPipeline(user_id=...)
- ✅ Direct calls to DraftPipeline(user_id=...)
- ✅ Existing `/api/settings` endpoint format
- ✅ Frontend code (uses same API)

## Changes Required For
- ⚠️ Custom embedding service initialization → pass `effective_settings`
- ⚠️ Custom LLM service initialization → pass `effective_settings`
- ⚠️ New services that need user settings → use SettingsManager

## Backward Compatibility
All services fall back to global `CONFIG` if no user settings provided:
```python
# This still works (uses global config)
service = EmbeddingService()

# This is better (uses user settings)
service = EmbeddingService(effective_settings=user_settings)
```

## Troubleshooting

### "No matches found"
Settings haven't been synced yet. Call `/api/settings` first.

### "Decryption failed"
Check that user_id matches between save and retrieve operations.

### "Database not found"
First sync of settings will create the database automatically.

### Settings not being used
Verify you're passing `effective_settings` parameter to service constructor.

## File Changes Summary

| File | Change |
|------|--------|
| `agent/services/settings_manager.py` | ✨ NEW - Main module |
| `agent/services/chat_pipeline.py` | 🔄 Updated - Use SettingsManager |
| `agent/services/draft_pipeline.py` | 🔄 Updated - Use SettingsManager |
| `agent/services/embeddings.py` | 🔄 Updated - Accept settings param |
| `agent/services/llm.py` | 🔄 Updated - Accept settings param |
| `agent/main.py` | 🔄 Updated - New /api/settings logic |

## Documentation Files

- `SETTINGS_MIGRATION_SUMMARY.md` - High-level overview
- `SETTINGS_DB_MIGRATION.md` - Detailed technical guide
- `SETTINGS_IMPLEMENTATION_GUIDE.md` - Code examples and patterns

## Key Points

1. **Security**: All API keys are now encrypted
2. **Isolation**: Each user has separate encrypted settings
3. **Automatic**: Pipelines load settings automatically
4. **Transparent**: Frontend API stays the same
5. **Backward Compatible**: Falls back to CONFIG if needed
