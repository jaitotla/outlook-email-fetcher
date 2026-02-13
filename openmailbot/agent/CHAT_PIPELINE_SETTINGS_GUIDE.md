# Chat Pipeline Settings Guide

## Overview

The Chat Pipeline has been enhanced to be fully configurable and support multiple providers for LLMs, embeddings, and vector databases. It reads user-specific settings from `config_settings.json` and adapts its behavior accordingly.

## Key Features

### 1. **Multi-Provider Support**

The pipeline now supports:

#### **LLM Providers**
- **OpenAI**: GPT-4, GPT-3.5, GPT-4o-mini, etc.
- **Anthropic**: Claude models (Sonnet, Opus, Haiku)
- **Google Gemini**: Gemini Pro and other models
- **Ollama**: Self-hosted models (Llama, Mistral, etc.)
- **Inbuilt**: Uses central Flask/Ollama server

#### **Embedding Providers**
- **OpenAI**: text-embedding-3-small, text-embedding-ada-002
- **Google Gemini**: models/embedding-001
- **Flask/Inbuilt**: Central embedding server

#### **Vector Database Providers**
- **ChromaDB**: Local or remote instances
- **Pinecone**: Cloud vector database (prepared for future integration)

### 2. **Settings Loading**

Settings are loaded from `config_settings.json` with this structure:

```json
{
  "users": {
    "user@example.com": {
      "settings": {
        "mode": "custom",
        "llm_provider": "openai",
        "llm_api_key": "sk-...",
        "llm_model": "gpt-4o-mini",
        "llm_base_url": "",
        "embedding_provider": "gemini",
        "embedding_api_key": "AIza...",
        "embedding_model": "models/embedding-001",
        "vector_provider": "chroma",
        "vector_url": "http://localhost:8500",
        "vector_api_key": "",
        "temperature": 0.7,
        "max_tokens": 2048
      }
    }
  }
}
```

### 3. **Dual-LLM Architecture**

The pipeline maintains a **hybrid approach** for optimal performance:

1. **Tool Caller LLM**: Handles tool selection and orchestration
   - Configurable via `llm_provider` setting
   - Falls back to OpenAI for reliability if provider fails

2. **Answer Generator LLM**: Generates final responses
   - Uses the same `llm_provider` setting
   - Can be the same or different from tool caller

## Configuration Examples

### Example 1: Full OpenAI Stack
```json
{
  "llm_provider": "openai",
  "llm_api_key": "sk-...",
  "llm_model": "gpt-4o-mini",
  "embedding_provider": "openai",
  "embedding_api_key": "sk-...",
  "embedding_model": "text-embedding-3-small",
  "vector_provider": "chroma"
}
```

### Example 2: Mixed Providers
```json
{
  "llm_provider": "anthropic",
  "llm_api_key": "sk-ant-...",
  "llm_model": "claude-3-sonnet-20240229",
  "embedding_provider": "gemini",
  "embedding_api_key": "AIza...",
  "embedding_model": "models/embedding-001",
  "vector_provider": "chroma",
  "vector_url": "http://remote-chroma:8500"
}
```

### Example 3: Self-Hosted Stack
```json
{
  "llm_provider": "ollama",
  "llm_base_url": "http://localhost:11434",
  "llm_model": "llama3.2",
  "embedding_provider": "inbuilt",
  "vector_provider": "chroma"
}
```

### Example 4: Google Gemini Stack
```json
{
  "llm_provider": "gemini",
  "llm_api_key": "AIza...",
  "llm_model": "gemini-pro",
  "embedding_provider": "gemini",
  "embedding_api_key": "AIza...",
  "embedding_model": "models/embedding-001",
  "vector_provider": "chroma"
}
```

## Implementation Details

### 1. Initialization
```python
pipeline = ChatWithThreadPipeline(user_id="user@example.com")
# Automatically loads settings from config_settings.json
# Initializes configured providers
```

### 2. Settings Access
```python
# Get a specific setting with fallback
llm_model = pipeline.get_setting('llm_model', 'gpt-4o-mini')

# Access all user settings
settings = pipeline.user_settings
```

### 3. Provider Selection

The pipeline automatically selects the right provider for each operation:

- **Tool Calling**: Uses `get_tool_caller_llm()` → Configured LLM
- **Embeddings**: Uses `call_embed_api()` → Configured embedding provider
- **Vector Storage**: Uses `get_user_chroma_client()` → Configured vector DB
- **Answer Generation**: Uses `generate_final_answer()` → Configured LLM

### 4. Fallback Strategy

If a provider fails, the pipeline automatically falls back:

1. **LLM**: Falls back to OpenAI GPT-4o-mini
2. **Embeddings**: Falls back to Flask embedding API
3. **Vector DB**: Falls back to local ChromaDB

## Usage Examples

### Basic Chat with Configured Providers
```python
from services.chat_pipeline import ChatWithThreadPipeline

# Initialize with user settings
pipeline = ChatWithThreadPipeline(user_id="user@example.com")

# Process and chat - uses all configured providers
result = pipeline.process_and_chat(
    user_id="user@example.com",
    thread_id="thread_123",
    user_question="What did John say about the project?"
)

print(result['answer'])
```

### Manual Provider Testing
```python
# Test embedding provider
embedding = pipeline.call_embed_api("Test text")
print(f"Embedding dimension: {len(embedding)}")

# Test LLM provider
answer = pipeline.generate_final_answer(
    system_prompt="You are a helpful assistant.",
    user_prompt="Say hello!"
)
print(answer)
```

## Settings Priority

1. **User Settings**: From `config_settings.json` (highest priority)
2. **Method Defaults**: Passed to individual methods
3. **Fallback Defaults**: Hardcoded in the pipeline

## Benefits

### For Users
- ✅ **Flexibility**: Choose preferred providers
- ✅ **Cost Control**: Mix expensive and cheap models
- ✅ **Privacy**: Use self-hosted models
- ✅ **Performance**: Optimize for speed or quality

### For Developers
- ✅ **Maintainability**: Centralized configuration
- ✅ **Extensibility**: Easy to add new providers
- ✅ **Testing**: Test with different providers
- ✅ **Fallback**: Graceful degradation on failures

## Adding New Providers

### Add a New LLM Provider

1. Update imports:
```python
from langchain_newprovider import ChatNewProvider
```

2. Add to `get_tool_caller_llm()`:
```python
elif llm_provider == 'newprovider':
    api_key = self.get_setting('llm_api_key')
    model = self.get_setting('llm_model', 'default-model')
    return ChatNewProvider(
        model=model,
        temperature=0,
        api_key=api_key
    )
```

3. Add to `generate_final_answer()`:
```python
elif llm_provider == 'newprovider':
    # Implementation
    pass
```

### Add a New Embedding Provider

Update `call_embed_api()`:
```python
elif embedding_provider == 'newprovider':
    api_key = self.get_setting('embedding_api_key')
    # Call provider API
    return embedding
```

### Add a New Vector Database

Update `get_user_chroma_client()` or create new methods for the vector DB.

## Migration Guide

### From Hardcoded to Settings-Based

**Before:**
```python
pipeline = ChatWithThreadPipeline()
# Always used OpenAI + Flask embeddings
```

**After:**
```python
pipeline = ChatWithThreadPipeline(user_id="user@example.com")
# Uses providers from user's config_settings.json
```

### No Breaking Changes

The pipeline remains backward compatible:
- If no user_id provided → Uses defaults
- If no settings found → Falls back to OpenAI/Flask
- All existing methods work as before

## Troubleshooting

### Issue: "No settings found for user"
**Solution**: Add user entry to `config_settings.json`

### Issue: "Failed to initialize LLM"
**Solution**: Check API key and model name in settings

### Issue: "Embedding error"
**Solution**: Verify embedding provider settings and API key

### Issue: "Unknown provider"
**Solution**: Check provider name spelling in settings

## Performance Considerations

1. **Settings Loading**: Done once during initialization
2. **Provider Initialization**: Lazy initialization where possible
3. **Fallback Overhead**: Minimal, only on errors
4. **Caching**: Settings cached in memory during pipeline lifetime

## Security Notes

- ⚠️ API keys stored in `config_settings.json`
- ⚠️ Ensure proper file permissions
- ⚠️ Consider encrypting sensitive settings
- ⚠️ Never commit `config_settings.json` to version control

## Future Enhancements

- [ ] Support for Pinecone vector database
- [ ] Support for Weaviate vector database
- [ ] Caching layer for embeddings
- [ ] Encrypted settings storage
- [ ] Settings validation on load
- [ ] Provider health checks
- [ ] Automatic provider fallback chains
- [ ] Settings hot-reload without restart

## Conclusion

The enhanced Chat Pipeline is now production-ready and fully configurable. Users can choose their preferred providers while maintaining the reliability of the inbuilt tools for tool calling operations.
