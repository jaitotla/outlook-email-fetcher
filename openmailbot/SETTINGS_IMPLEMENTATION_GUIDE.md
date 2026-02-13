# Implementation Guide: Using Settings Manager in Services

This guide explains how to properly integrate the new `SettingsManager` with services like `EmbeddingService` and `LLMService`.

## Quick Reference

### Chat Pipeline (Already Updated)

```python
from services.settings_manager import SettingsManager
from services.chat_pipeline import ChatWithThreadPipeline

user_id = "user@example.com"

# Create pipeline - settings loaded automatically from DB
pipeline = ChatWithThreadPipeline(user_id=user_id)

# Use pipeline with user's settings
await pipeline.chat_with_thread(user_id, thread_id, question)
```

### Embedding Service (New)

Before:
```python
embedding_service = EmbeddingService()
```

After:
```python
from services.embeddings import EmbeddingService
from services.settings_manager import SettingsManager

# Option 1: Provide settings explicitly
user_id = "user@example.com"
manager = SettingsManager(user_id)
settings = manager.get_settings(user_id, "general")
embedding_service = EmbeddingService(effective_settings=settings)

# Option 2: Use default settings from config (backward compatible)
embedding_service = EmbeddingService()  # Falls back to CONFIG
```

### LLM Service (New)

Before:
```python
llm_service = LLMService()
```

After:
```python
from services.llm import LLMService
from services.settings_manager import SettingsManager

# Option 1: Provide settings explicitly
user_id = "user@example.com"
manager = SettingsManager(user_id)
settings = manager.get_settings(user_id, "general")
llm_service = LLMService(effective_settings=settings)

# Option 2: Use default settings from config (backward compatible)
llm_service = LLMService()  # Falls back to CONFIG
```

## Detailed Integration Examples

### Example 1: Custom Embedding Pipeline

```python
from services.embeddings import EmbeddingService
from services.settings_manager import SettingsManager

class CustomEmbeddingPipeline:
    def __init__(self, user_id: str):
        self.user_id = user_id
        
        # Load user's encrypted settings
        settings_manager = SettingsManager(user_id)
        user_settings = settings_manager.get_settings(user_id, "general")
        
        # Initialize embedding service with user settings
        self.embedding_service = EmbeddingService(effective_settings=user_settings)
    
    async def embed_text(self, text: str):
        return await self.embedding_service.generate_embedding(text)
```

### Example 2: Multi-User LLM Processing

```python
from services.llm import LLMService
from services.settings_manager import SettingsManager
from typing import Dict

class MultiUserLLMProcessor:
    def __init__(self):
        self.llm_services: Dict[str, LLMService] = {}
    
    def get_llm_service(self, user_id: str) -> LLMService:
        """Get or create LLM service for user"""
        if user_id not in self.llm_services:
            # Load user's settings from DB
            manager = SettingsManager(user_id)
            settings = manager.get_settings(user_id, "general")
            
            # Create service with user settings
            self.llm_services[user_id] = LLMService(effective_settings=settings)
        
        return self.llm_services[user_id]
    
    async def process_for_user(self, user_id: str, prompt: str) -> str:
        llm_service = self.get_llm_service(user_id)
        return await llm_service.generate_response(prompt)
```

### Example 3: Settings Update and Refresh

```python
from services.settings_manager import SettingsManager
from services.embeddings import EmbeddingService

def update_user_embedding_settings(user_id: str, new_model: str):
    """Update user's embedding model and refresh service"""
    
    # Update setting in DB
    manager = SettingsManager(user_id)
    manager.update_setting("embedding_model", new_model, user_id, "general")
    
    # Get updated settings
    updated_settings = manager.get_settings(user_id, "general")
    
    # Create new service with updated settings
    embedding_service = EmbeddingService(effective_settings=updated_settings)
    
    return embedding_service
```

## Flow Diagrams

### Settings Save Flow

```
Frontend (Gmail Add-on)
    ↓
POST /api/settings
    ↓
main.py::sync_settings()
    ↓
SettingsManager.save_settings()
    ↓
encrypt_settings()
    ↓
SQLite DB: user_settings table
    ↓
data/{user_id}/sql_data/chat_thread_processing.db
```

### Settings Load Flow

```
ChatWithThreadPipeline.__init__(user_id)
    ↓
SettingsManager(user_id).get_settings()
    ↓
Retrieve from SQLite DB
    ↓
decrypt_settings()
    ↓
Return decrypted Dict
    ↓
Initialize EmbeddingService(effective_settings=...)
Initialize LLMService(effective_settings=...)
```

## Code Patterns

### Pattern 1: Lazy Loading

```python
class LazyLoadedService:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self._service = None
    
    @property
    def service(self):
        if self._service is None:
            manager = SettingsManager(self.user_id)
            settings = manager.get_settings(self.user_id, "general")
            self._service = EmbeddingService(effective_settings=settings)
        return self._service
```

### Pattern 2: Settings with Defaults

```python
def get_setting_with_default(user_id: str, key: str, default=None):
    """Get setting with fallback to default"""
    manager = SettingsManager(user_id)
    value = manager.get_setting_value(key, user_id, "general", default)
    return value

# Usage
llm_model = get_setting_with_default(
    user_id="user@example.com",
    key="llm_model",
    default="gpt-4o-mini"
)
```

### Pattern 3: Conditional Initialization

```python
from services.llm import LLMService
from services.settings_manager import SettingsManager

def initialize_llm_service(user_id: str = None) -> LLMService:
    """Initialize LLM service with user settings if available"""
    
    service = LLMService()  # Initialize with defaults first
    
    if user_id:
        # Override with user settings if provided
        manager = SettingsManager(user_id)
        user_settings = manager.get_settings(user_id, "general")
        
        if user_settings:
            service.effective_settings = user_settings
            service.default_provider = user_settings.get("llm_provider", "inbuilt")
            service.default_model = user_settings.get("llm_model")
            service._init_clients()
    
    return service
```

## Migration Checklist for New Features

If you're building a new feature that needs user settings:

- [ ] Import `SettingsManager` from `services.settings_manager`
- [ ] Accept `user_id` as a parameter
- [ ] Load settings: `manager = SettingsManager(user_id); settings = manager.get_settings(user_id, "general")`
- [ ] Pass to service: `Service(effective_settings=settings)`
- [ ] Test with and without user_id (backward compatibility)
- [ ] Document in docstring which settings are expected
- [ ] Handle None/empty settings gracefully

## Testing Settings Manager

```python
from services.settings_manager import SettingsManager

# Test encryption and decryption
user_id = "test@example.com"
manager = SettingsManager(user_id)

# Create test settings
test_settings = {
    "llm_provider": "openai",
    "llm_api_key": "sk-test-key",
    "llm_model": "gpt-4",
    "user_name": "Test User"
}

# Save
success = manager.save_settings(test_settings, user_id, "general")
print(f"Save successful: {success}")

# Retrieve
retrieved = manager.get_settings(user_id, "general")
print(f"Retrieved: {retrieved}")

# Verify
assert retrieved == test_settings, "Settings mismatch!"
print("✅ Settings manager working correctly")
```

## Environment Variables

For production deployment, consider these environment variables:

```bash
# Encryption configuration
ENCRYPTION_KEY_SALT=your-secure-salt-here
ENCRYPTION_ITERATIONS=100000

# Database configuration
DB_POOL_SIZE=10
DB_TIMEOUT=30

# Logging
SETTINGS_DEBUG=false
```

## Performance Considerations

1. **Caching**: Cache decrypted settings in memory for 5-10 minutes
2. **Async Loading**: Use async DB calls for better concurrency
3. **Indexing**: Indexes on (user_id, setting_type) for faster queries
4. **Connection Pooling**: Reuse SQLite connections when possible

## Security Best Practices

1. **Never Log Keys**: Don't print or log API keys even in debug mode
2. **Validate Input**: Validate settings before saving to DB
3. **Audit Trail**: Log settings access and modifications
4. **Key Rotation**: Periodically rotate encryption keys
5. **Secure Transport**: Use HTTPS for all /api/settings calls
