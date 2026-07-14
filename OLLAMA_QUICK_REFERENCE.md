# Quick Reference: Ollama Structured Output Migration

## What Changed?

### ❌ Old Way (Hardcoded URL)
```python
# In ollama_lable_pipline.py
self.ollama_url = "https://lsdiedb39c.pagekite.me/chat_structure"

# Direct requests call
response = requests.post(self.ollama_url, json=payload, timeout=30)
```

### ✅ New Way (Environment-based)
```python
# In utils.py - centralized function
def chat_structure(query: str, json_schema: dict, model: str = "llama3.2"):
    """Use MANOTR_OLLAMA from environment"""
    ...

# In ollama_lable_pipline.py - clean import and use
from agent.utils import chat_structure

result = chat_structure(
    query=user_query,
    json_schema=EmailLabelOutput.model_json_schema(),
    model=self.model,
    timeout_seconds=30
)
```

---

## Files Modified Summary

### 1. `agent/utils.py` ✅
- **Added:** `chat_structure()` function (95 lines)
- **Purpose:** Centralized Ollama structured output wrapper
- **Key Features:**
  - Uses `MANOTR_OLLAMA` environment variable
  - Automatic JSON parsing and validation
  - Comprehensive error handling
  - Logging with debug info

### 2. `agent/services/ollama_lable_pipline.py` ✅
- **Removed:** Hardcoded URL parameter
- **Removed:** Direct requests to `https://lsdiedb39c.pagekite.me/chat_structure`
- **Added:** Import from `agent.utils import chat_structure`
- **Updated Methods:**
  - `__init__()` - no more ollama_url parameter
  - `_test_ollama_connection()` - uses chat_structure for testing
  - `classify_with_ollama()` - uses chat_structure for classification

### 3. `agent/services/label_pipeline.py` ✅
- **Removed:** `from ollama import chat as ollama_chat` (no longer needed)
- **Added:** `from agent.utils import chat_structure`
- **Updated Methods:**
  - `_init_llm()` - simplified Ollama initialization
  - Ollama classification section - uses chat_structure instead of ollama_chat

---

## Environment Configuration

### Required Setup
Add to `.env` file:
```bash
MANOTR_OLLAMA=http://localhost:11434
```

Or for remote Ollama:
```bash
MANOTR_OLLAMA=https://your-ollama-server.com:11434
```

### Defaults (if MANOTR_OLLAMA not set)
Falls back to: `http://localhost:11434/`

---

## How to Use

### For Email Classification
```python
from agent.services.label_pipeline import EmailLabelPipeline

# Initialize (no URL parameter needed!)
pipeline = EmailLabelPipeline(user_id="user@example.com")

# Classify email
email_data = {
    'subject': 'Meeting Reminder',
    'body': 'Our meeting is scheduled for tomorrow...',
    'from': 'sender@example.com',
    'to': ['user@example.com']
}

result = pipeline.classify_email(email_data)
print(f"Label: {result.label}")
```

### For Custom Structured Output
```python
from agent.utils import chat_structure
from pydantic import BaseModel

class MyOutputSchema(BaseModel):
    field1: str
    field2: int

result = chat_structure(
    query="Your prompt here",
    json_schema=MyOutputSchema.model_json_schema(),
    model="llama3.2",
    timeout_seconds=60
)

if "error" not in result:
    output = MyOutputSchema(**result)
else:
    print(f"Error: {result['error']}")
```

---

## Error Handling

The `chat_structure()` function returns error dict:
```python
{
    "error": "Error message here",
    "raw_content": "Optional raw response if JSON parse failed"
}
```

### Common Errors
| Error | Cause | Fix |
|-------|-------|-----|
| `MANOTR_OLLAMA not configured` | Env var not set | Add to .env |
| `Request timeout` | Ollama too slow | Increase timeout_seconds |
| `Connection refused` | Ollama not running | Start Ollama service |
| `Invalid JSON in response` | Model returned bad format | Check model, try different one |

---

## Testing

### Quick Test
```bash
# Set environment variable
export MANOTR_OLLAMA=http://localhost:11434

# Run classification
python -c "
from agent.services.ollama_lable_pipline import EmailLabelPipeline
p = EmailLabelPipeline()
print('✅ Connection successful!' if p.ollama_available else '❌ Connection failed')
"
```

### With Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Now run your code - will see detailed logs
```

---

## Migration Checklist

- [x] Removed hardcoded URLs from code
- [x] Added `chat_structure()` to utils.py
- [x] Updated ollama_lable_pipline.py
- [x] Updated label_pipeline.py
- [x] Removed example with old URL format
- [x] Tested imports (no syntax errors)
- [ ] Set MANOTR_OLLAMA in .env
- [ ] Test email classification end-to-end
- [ ] Verify logs show correct Ollama URL being used

---

## Benefits

✨ **Single Source of Truth:** One environment variable for all Ollama calls
🔒 **Security:** No hardcoded URLs in code
🧪 **Testability:** Easy to mock or switch Ollama endpoints for testing
📊 **Logging:** Centralized error handling and debug logging
♻️ **Reusability:** `chat_structure()` can be used by other services
🚀 **Maintenance:** Updates to Ollama handling in one place
