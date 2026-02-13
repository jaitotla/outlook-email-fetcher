# Draft Pipeline Refactor Summary

## Overview
Refactored `draft_pipeline.py` to use `EmbeddingService` and `LLMService` from the services module, matching the architecture implemented in `chat_pipeline.py`.

## Key Changes

### 1. **Service Imports** 
```python
from services.embeddings import EmbeddingService
from services.llm import LLMService
```
- Added imports for EmbeddingService and LLMService
- Added traceback import for better error logging

### 2. **Configuration Loading**
```python
CONFIG_PATH2 = "/home/ubuntu/openmailbot/openmailbot/agent/config_settings.json"
with open(CONFIG_PATH2, 'r') as f:
    CONFIG2 = json.load(f)
```
- Now loads `config_settings.json` for LLM provider configuration

### 3. **Service Initialization in `__init__`**
- **LLMService**: Initialized with error handling and logging
  ```python
  self.llm_service = LLMService()
  ```
- **EmbeddingService**: Initialized with error handling and logging
  ```python
  self.embedding_service = EmbeddingService()
  ```
- **Provider Configuration**: Stores LLM provider and model from settings
  ```python
  self.llm_provider = self.effective_settings.get("llm_provider", "inbuilt")
  self.llm_model = self.effective_settings.get("llm_model", "gpt-4o-mini")
  ```
- **Conditional Tool Caller**: OpenAI only initialized for inbuilt mode
  ```python
  if self.llm_provider == "inbuilt":
      self.tool_caller_llm = ChatOpenAI(...)
  ```

### 4. **Async Helper Methods**
Added three new helper methods (matching `chat_pipeline.py`):
- `_run_async_task()`: Safely runs async code with proper event loop handling
- `_run_in_new_loop()`: Creates new event loop for thread pool execution
- `_get_embedding_sync()`: Synchronous wrapper for async embedding generation

### 5. **Embedding Generation**
**Replaced Direct API Calls:**
- ❌ `self.call_embed_api(text)` - Old Flask API approach
- ✅ `self._get_embedding_sync(text)` - EmbeddingService approach

**Updated Methods:**
- `process_attachment()`: Now uses `EmbeddingService.store_embedding()`
- `_query_attachments_internal()`: Now uses `EmbeddingService.search_similar()`

### 6. **LLM Response Generation**
**Replaced Direct Ollama Calls:**
- ❌ `call_ollama_chat_params()` - Old Flask Ollama approach
- ✅ `await self.llm_service.generate()` - LLMService approach

**Updated Methods:**
- `generate_draft_hybrid()`: Now uses LLMService for response generation
- New: `_tool_calling_with_openai_draft()`: Handles OpenAI tool calling (inbuilt mode)
- New: `_tool_calling_with_llm_service_draft()`: Handles LLMService tool calling (other providers)

### 7. **Hybrid Approach Implementation**
The `generate_draft_hybrid()` method now:
1. Uses provider-specific tool calling (OpenAI for inbuilt, LLMService for others)
2. Retrieves attachment context based on tool decisions
3. Uses LLMService to generate final draft with configurable provider and model

### 8. **Namespace for Vector Storage**
All embeddings now use consistent namespace:
```python
namespace = f"{user_id}_drafts"
```

### 9. **Removed Components**
- ❌ `call_ollama_chat_params()` function - Replaced by LLMService
- ❌ Direct Flask embedding API calls - Replaced by EmbeddingService

## Architecture Benefits

| Aspect | Before | After |
|--------|--------|-------|
| **Embedding Provider** | Direct Flask API | EmbeddingService (abstracted) |
| **LLM Provider** | Direct Ollama/Flask | LLMService (multi-provider) |
| **Configuration** | Hardcoded | Settings-driven |
| **Error Handling** | Basic try-except | Comprehensive with logging |
| **Tool Calling** | OpenAI only | Provider-aware (OpenAI + LLMService) |
| **Code Reusability** | Custom implementations | Shared services |

## Migration Notes

### For Existing Code Using DraftPipeline:
1. **No Breaking Changes** to public API
2. `process_email_request()` still works the same way
3. Internal implementation now uses services layer

### Configuration Requirements:
Ensure `config_settings.json` has:
```json
{
  "llm_provider": "inbuilt",  // or "openai", "anthropic", etc.
  "llm_model": "gpt-4o-mini"  // or appropriate model for provider
}
```

### Error Handling:
- LLMService and EmbeddingService initialization failures are now caught and logged
- Async operations properly handle existing event loops
- Better traceback logging for debugging

## Testing Checklist

- [ ] Verify EmbeddingService initialization succeeds
- [ ] Verify LLMService initialization succeeds  
- [ ] Test attachment embedding with inbuilt provider (OpenAI)
- [ ] Test attachment embedding with alternative provider
- [ ] Test hybrid draft generation (tool calling + response)
- [ ] Verify vector search returns relevant results
- [ ] Test error scenarios (missing attachments, API failures)
- [ ] Performance comparison with old implementation

## Related Files

- [chat_pipeline.py](agent/services/chat_pipeline.py) - Reference implementation
- [embeddings.py](agent/services/embeddings.py) - EmbeddingService
- [llm.py](agent/services/llm.py) - LLMService
- [config_settings.json](agent/config_settings.json) - Configuration file
