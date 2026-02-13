# Settings Management Guide

## Overview
Settings are now fully persistent and can be updated via API endpoints or Python code.

## Features
✅ **Persistent Storage** - Settings are saved to `agent/config_settings.json`  
✅ **API Endpoints** - Update settings via HTTP requests  
✅ **Auto-Loading** - Saved settings load automatically on app startup  
✅ **Runtime Updates** - Change settings without restarting  

---

## API Endpoints

### 1. Get Current Settings
```bash
GET /api/settings
```
**Response:**
```json
{
  "success": true,
  "settings": {
    "LLM_PROVIDER": "openai",
    "EMBEDDING_PROVIDER": "inbuilt",
    "TEMPERATURE": 0.7,
    ...
  },
  "timestamp": "2026-02-03T10:30:00"
}
```

### 2. Update Settings (and Save)
```bash
POST /api/settings
Content-Type: application/json

{
  "LLM_PROVIDER": "openai",
  "OPENAI_API_KEY": "sk-...",
  "TEMPERATURE": 0.5,
  "OPENAI_MODEL": "gpt-4"
}
```
**Response:**
```json
{
  "success": true,
  "message": "Updated 4 settings",
  "updated_settings": {...},
  "saved_file": "/home/ubuntu/openmailbot/openmailbot/agent/config_settings.json"
}
```

### 3. Reload Settings from File
```bash
GET /api/settings/reload
```
**Useful for:** Reverting to last saved settings or picking up changes made to the JSON file

### 4. Explicitly Save Current Settings
```bash
POST /api/settings/save
```
**Useful for:** Manual checkpoint of current in-memory settings

---

## Python Code Usage

### Update Settings Programmatically
```python
from config import settings

# Update and automatically save to disk
settings.update_settings({
    'LLM_PROVIDER': 'openai',
    'OPENAI_API_KEY': 'sk-...',
    'TEMPERATURE': 0.5
})

# Changes are immediately persisted
```

### Get All Settings
```python
from config import settings

all_settings = settings.get_settings_dict()
print(all_settings)
```

### Load from File
```python
from config import settings

settings.load_from_file()  # Uses default location
# OR
settings.load_from_file('/custom/path/to/config_settings.json')
```

### Save to File
```python
from config import settings

filepath = settings.save_to_file()  # Uses default location
# OR
filepath = settings.save_to_file('/custom/path/to/config_settings.json')
```

---

## Storage Details

**Default Location:** `agent/config_settings.json`

**File Format:**
```json
{
  "LLM_PROVIDER": "openai",
  "EMBEDDING_PROVIDER": "inbuilt",
  "VECTOR_PROVIDER": "chroma",
  "OPENAI_API_KEY": "sk-...",
  "TEMPERATURE": 0.7,
  "MAX_TOKENS": 2048,
  ...
}
```

**Persistence Flow:**
1. App starts → loads defaults from `config.py`
2. Loads `config_settings.json` if it exists
3. API request updates settings → saved to `config_settings.json`
4. Next app restart → loads from saved file

---

## Examples

### cURL Examples

**Get settings:**
```bash
curl http://localhost:5050/api/settings
```

**Update settings:**
```bash
curl -X POST http://localhost:5050/api/settings \
  -H "Content-Type: application/json" \
  -d '{
    "LLM_PROVIDER": "openai",
    "OPENAI_API_KEY": "sk-xxx",
    "TEMPERATURE": 0.5
  }'
```

**Reload from file:**
```bash
curl http://localhost:5050/api/settings/reload
```

### Python Examples

**Using requests library:**
```python
import requests

# Get settings
response = requests.get('http://localhost:5050/api/settings')
print(response.json())

# Update settings
response = requests.post('http://localhost:5050/api/settings', json={
    'LLM_PROVIDER': 'openai',
    'TEMPERATURE': 0.5
})
print(response.json())
```

---

## Key Changes

### In `config.py`:
- Added `persist` parameter to `update_settings()` (default: True)
- Added `save_to_file()` method
- Added `load_from_file()` method
- Settings auto-load from file on module import

### In `main.py`:
- Added `GET /api/settings` - retrieve all current settings
- Added `POST /api/settings` - update and persist settings
- Added `GET /api/settings/reload` - reload from file
- Added `POST /api/settings/save` - explicit save operation

---

## Troubleshooting

**Q: Settings aren't persisting**  
A: Check that `POST /api/settings` is used instead of just updating in memory. Verify `config_settings.json` is created in the `agent/` directory.

**Q: Changes don't appear after restart**  
A: Make sure you're using the API endpoint or calling `settings.save_to_file()`. Simply using `setattr()` won't persist.

**Q: Want to reset to defaults**  
A: Delete `agent/config_settings.json` and restart the app, or call `settings.update_settings({})` to clear.
