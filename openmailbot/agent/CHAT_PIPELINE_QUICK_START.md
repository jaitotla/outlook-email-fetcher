# Quick Start: Chat Pipeline with Any Settings

## TL;DR - Just Works with Any Configuration!

```python
from services.chat_pipeline import ChatWithThreadPipeline

# Works with any settings combination automatically
pipeline = ChatWithThreadPipeline(user_id="user@example.com")

# All functions work with configured providers
result = pipeline.process_and_chat(
    user_id="user@example.com",
    thread_id="thread_123",
    user_question="What's the summary?"
)

print(result['answer'])  # Works regardless of settings
```

## What Gets Used From Settings?

| Setting | Usage | Default |
|---------|-------|---------|
| `llm_provider` | LLM for tool calling & answers | `inbuilt` |
| `llm_api_key` | API key for LLM | Config fallback |
| `llm_model` | Which model to use | Provider default |
| `llm_base_url` | Custom LLM endpoint | None |
| `embedding_provider` | Embeddings service | `inbuilt` |
| `embedding_api_key` | API key for embeddings | Inherits from llm |
| `embedding_model` | Which embedding model | Provider default |
| `temperature` | LLM temperature | `0.7` |
| `max_tokens` | Max tokens for answer | `2048` |

## All Supported Providers

### LLM Providers
- ✅ `openai` - GPT-4, GPT-3.5, etc.
- ✅ `anthropic` - Claude models
- ✅ `gemini` - Google Gemini
- ✅ `ollama` - Self-hosted local models
- ✅ `inbuilt` / `flask` - Central Flask server

### Embedding Providers
- ✅ `openai` - text-embedding-3-small, etc.
- ✅ `gemini` - models/embedding-001
- ✅ `inbuilt` / `flask` - Central Flask server

### Vector DB
- ✅ Local ChromaDB (default, always works)

## Configuration Combinations (All Work!)

```json
{
  "Mode 1: Pure OpenAI",
  "llm_provider": "openai",
  "embedding_provider": "openai"
}
```

```json
{
  "Mode 2: Mixed Providers",
  "llm_provider": "anthropic",
  "embedding_provider": "gemini"
}
```

```json
{
  "Mode 3: Inbuilt (Zero Config)",
  "llm_provider": "inbuilt",
  "embedding_provider": "inbuilt"
}
```

```json
{
  "Mode 4: Self-Hosted",
  "llm_provider": "ollama",
  "embedding_provider": "inbuilt"
}
```

## How It Works Internally

### 1. **Settings Loading**
```python
pipeline = ChatWithThreadPipeline(user_id="user@example.com")
# Automatically loads from config_settings.json
# Falls back to defaults if not found
```

### 2. **Provider Routing**

**For Embeddings:**
```
Try configured provider (OpenAI/Gemini) 
  ↓ (if fails or not configured)
Fall back to inbuilt (Flask API via utils.py)
  ↓ (if fails)
Raise error
```

**For LLM:**
```
Try configured provider (OpenAI/Anthropic/etc)
  ↓ (if fails or not configured)
Fall back to inbuilt (Flask API via utils.py)
  ↓ (if fails)
Raise error
```

**For Tool Calling:**
```
Prefer OpenAI for structured output
  ↓ (if no key)
Try configured provider
  ↓ (if fails)
Use OpenAI default
```

### 3. **Vector Storage**
```
Always local ChromaDB
Stored in: data/{user_id}/vector_db/
No remote connection needed
```

## Common Scenarios

### Scenario 1: User with Full OpenAI Setup
```python
pipeline = ChatWithThreadPipeline("john@company.com")
# config_settings.json has full OpenAI keys
# Result: Everything uses OpenAI ✅
```

### Scenario 2: User with Partial Config
```python
pipeline = ChatWithThreadPipeline("jane@company.com")
# config_settings.json has only embedding_api_key
# Result: Uses configured embedding, inbuilt for LLM ✅
```

### Scenario 3: No User Settings
```python
pipeline = ChatWithThreadPipeline()  # No user_id
# Result: Uses all defaults (inbuilt mode) ✅
```

### Scenario 4: API Key Invalid
```python
pipeline = ChatWithThreadPipeline("bob@company.com")
# config_settings.json has invalid OpenAI key
# Result: Automatically falls back to inbuilt ✅
```

## Error Recovery

The pipeline automatically recovers from:

1. **Invalid API Keys** → Falls back to inbuilt
2. **API Rate Limits** → Falls back to inbuilt
3. **API Timeouts** → Falls back to inbuilt
4. **Unknown Provider** → Falls back to inbuilt
5. **Missing Settings** → Uses defaults

## Logging Examples

```
✅ Loaded settings for user john@example.com
✅ Initialized ChromaDB client at /data/john@example.com/vector_db
📌 Using inbuilt mode - OpenAI for tool calling, Flask for answers
⚠️  OpenAI API key not set, falling back to inbuilt
❌ Embedding error with 'openai': 401 Unauthorized. Falling back
✅ Switched to inbuilt embedding provider
```

## Adding a New Provider (for developers)

### Add OpenAI variant
```python
elif llm_provider == 'azure_openai':
    # Your implementation
    pass
```

### Add Embedding Provider
```python
elif embedding_provider == 'cohere':
    # Your implementation
    pass
```

### Add Vector DB (future)
```python
elif vector_provider == 'pinecone':
    # Your implementation
    pass
```

## Testing Checklist

- [ ] Works with no user_id (defaults)
- [ ] Works with full settings (all providers)
- [ ] Works with partial settings (mixed providers)
- [ ] Works with invalid API keys (falls back)
- [ ] Works when provider is down (falls back)
- [ ] Vector storage is per-user
- [ ] Embeddings are cached properly
- [ ] Answers use correct provider
- [ ] Tool calling works
- [ ] Attachments are processed

## Performance Tips

1. **For Speed**: Use inbuilt mode (zero latency)
2. **For Quality**: Use OpenAI/Anthropic
3. **For Cost**: Use Gemini or self-hosted Ollama
4. **For Privacy**: Use self-hosted Ollama + local embeddings

## Troubleshooting

**Q: How do I know which provider was used?**
A: Check logs:
```
📌 Using inbuilt mode - OpenAI for tool calling, Flask for answers
```

**Q: Why did my configured provider not work?**
A: Check logs for error message and see if it fell back to inbuilt

**Q: Can I use different providers for LLM and embeddings?**
A: Yes! That's the whole point. Mix and match freely.

**Q: What if I have no settings?**
A: Falls back to inbuilt/Flask mode automatically

**Q: Is vector DB configurable?**
A: Currently local only, but prepare for future Pinecone/Weaviate support

## Next Steps

1. Set up `config_settings.json` with your preferences
2. Create pipeline: `pipeline = ChatWithThreadPipeline(user_id)`
3. Process threads: `result = pipeline.process_and_chat(...)`
4. Get answers automatically with your configured providers

**That's it! The pipeline handles all the rest.** 🚀
