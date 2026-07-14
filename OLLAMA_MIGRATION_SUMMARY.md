# Ollama Structured Output Migration - Summary

## Overview
Migrated hardcoded Ollama URLs to a centralized `chat_structure()` function in `utils.py`. This ensures:
- ✅ Single source of truth for Ollama URL configuration (via `MANOTR_OLLAMA` environment variable)
- ✅ Consistent structured output handling across pipelines
- ✅ Better error handling and logging
- ✅ Easier maintenance and updates

## Changes Made

### 1. **Added `chat_structure()` function to `agent/utils.py`**

**Purpose:** Centralized Ollama structured output API wrapper

**Features:**
- Uses `MANOTR_OLLAMA` environment variable (loaded from `.env`)
- Supports custom JSON schema for structured output
- Native Ollama `/api/chat` endpoint with `format` parameter
- Comprehensive error handling with timeouts
- Validates responses and provides helpful error messages

**Signature:**
```python
def chat_structure(
    query: str, 
    json_schema: dict, 
    model: str = "llama3.2", 
    timeout_seconds: int = 60
) -> dict
```

**Returns:** Parsed JSON dict conforming to schema (or error dict)

---

### 2. **Updated `agent/services/ollama_lable_pipline.py`**

**Migration:**
- ❌ Removed hardcoded URL: `https://lsdiedb39c.pagekite.me/chat_structure`
- ❌ Removed `ollama_url` parameter from `__init__()`
- ✅ Now uses `chat_structure()` function from utils

**Changes:**
| Old | New |
|-----|-----|
| `__init__(ollama_url=None, model="llama3.2")` | `__init__(model="llama3.2")` |
| `self.ollama_url = ollama_url or "https://lsdiedb39c..."` | Removed |
| Direct `requests.post()` to hardcoded URL | `chat_structure()` function call |
| Manual JSON parsing | Automatic via `chat_structure()` |

**Benefits:**
- No external URL hardcoding
- Automatic fallback to environment config
- Better error logging
- Schema validation

---

### 3. **Updated `agent/services/label_pipeline.py`**

**Migration:**
- ❌ Removed: `from ollama import chat as ollama_chat` dependency
- ✅ Added: `from agent.utils import chat_structure`
- ✅ Simplified `_init_llm()` for Ollama provider
- ✅ Replaced `ollama_chat()` call with `chat_structure()`

**Changes:**
| Section | Old | New |
|---------|-----|-----|
| Import | `from ollama import chat as ollama_chat` | `from agent.utils import chat_structure` |
| Ollama init | Requires `ollama` library installed | Uses `chat_structure()` (no library needed) |
| API call | `ollama_chat(model=..., messages=..., format=...)` | `chat_structure(query=..., json_schema=..., model=...)` |

**Benefits:**
- Removes external `ollama` library dependency
- Cleaner code
- Consistent with utils pattern
- Single URL configuration point

---

## Configuration

### Environment Variable
Set in `.env` file:
```bash
MANOTR_OLLAMA=http://localhost:11434
# or for remote:
MANOTR_OLLAMA=https://your-ollama-server.com:port
```

### Fallback Behavior
If `MANOTR_OLLAMA` not set:
- Will try `INBUILT_OLLAMA_URL` 
- Falls back to `http://localhost:11434/` (local development)

---

## How `chat_structure()` Works

### Flow Diagram
```
chat_structure(query, schema, model)
    ↓
Load MANOTR_OLLAMA URL from env
    ↓
Call Ollama /api/chat with format parameter
    ↓
Parse JSON response
    ↓
Validate against schema
    ↓
Return parsed dict (or error dict)
```

### Example Usage
```python
from agent.utils import chat_structure
from agent.services.label_pipeline import EmailLabelOutput

result = chat_structure(
    query="Classify this email: ...",
    json_schema=EmailLabelOutput.model_json_schema(),
    model="llama3.2",
    timeout_seconds=30
)

if "error" in result:
    print(f"Error: {result['error']}")
else:
    label_output = EmailLabelOutput(**result)
    print(f"Label: {label_output.label}")
```

---

## Files Modified

| File | Changes |
|------|---------|
| `agent/utils.py` | Added `chat_structure()` function (95 lines) |
| `agent/services/ollama_lable_pipline.py` | Updated imports, `__init__()`, `_test_ollama_connection()`, `classify_with_ollama()` |
| `agent/services/label_pipeline.py` | Updated imports, removed `ollama` library dependency, updated `_init_llm()` and Ollama classification section |

---

## Testing Checklist

- [ ] Set `MANOTR_OLLAMA` environment variable in `.env`
- [ ] Test email classification with Ollama provider
- [ ] Verify structured output is correctly parsed
- [ ] Test error handling (invalid schema, timeout, connection error)
- [ ] Verify logs show proper debug messages
- [ ] Test with different Ollama models (llama3.2, llama2, etc.)

---

## Benefits Summary

| Aspect | Before | After |
|--------|--------|-------|
| **URL Configuration** | Hardcoded in code (2 locations) | Single `MANOTR_OLLAMA` env var |
| **Dependency** | `ollama` library required | No library needed |
| **Error Handling** | Basic requests exceptions | Comprehensive with timeouts & validation |
| **Maintainability** | Spread across files | Centralized in `utils.py` |
| **Testing** | Hard to mock URLs | Easy to test via env var |

---

## Migration Notes

✅ **Backward Compatible:** Old code won't break, but environment variable must be set
⚠️ **Important:** Remove `ollama` from `requirements.txt` if not needed elsewhere
🔄 **Consistent:** Both `ollama_lable_pipline.py` and `label_pipeline.py` now use same approach
📝 **Logging:** Enhanced with `chat_structure()` function logging for debugging
