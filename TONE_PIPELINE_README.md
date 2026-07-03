# Email Tone Pipeline Implementation

## Summary

The email tone/relationship personalization pipeline has been successfully implemented and integrated into OpenMailBot. This feature captures and stores the user's writing style when they send emails, enabling the drafting agent to generate replies that match their established tone with each recipient.

## What Was Implemented

### 1. **Core Service: `agent/services/email_tone_pipeline.py`**

A production-ready pipeline service (870+ lines) that provides:

- **LLM Integration**: Calls Ollama `llama3.2` to extract structured tone information from sent emails
- **Dual Storage**:
  - **SQLite** (`email_history.db`): Keeps full audit history of all processed emails per user
  - **ChromaDB** (`chroma_store/`): Maintains rolling window of 3 most recent emails per recipient with embeddings
- **Per-User Isolation**: All data stored in `data/{user_id}/tone_db/`
- **Graceful Degradation**: Falls back to safe defaults if Ollama is unavailable
- **Embedding Support**: Uses `nomic-embed-text:latest` for email vectorization
- **Rolling Window Management**: Automatically evicts old entries when limit (3 per recipient) is exceeded

### 2. **Integration with Labeling System**

Modified `backend/main.py` to integrate tone capture:

- Added import: `from agent.services.email_tone_pipeline import TonePipelineManager`
- Created helper function: `_capture_tone_for_sent_emails()` (lines 2252-2323)
  - Detects emails sent by the user (where `from == user_id`)
  - Extracts recipient(s) and email body
  - Runs tone extraction for each sent email
  - Stores results in per-user tone_db
  - Non-fatal: errors don't break the labeling pipeline
  
- Integrated into `_run_label_and_push_to_gmail()` async task (lines 2476-2488)
  - Called after label is determined, before Gmail push
  - Captures intent/tone in one API call alongside labeling
  - Logs results to job status

### 3. **Database Schema**

**SQLite Schema** (`email_history.db`):
```
Table: emails
  - id (TEXT PRIMARY KEY)
  - recipient (TEXT)
  - email_text (TEXT)
  - relationship_type (TEXT)
  - familiarity (TEXT)
  - authority (TEXT)
  - tone (TEXT)
  - politeness (TEXT)
  - warmth (TEXT)
  - directness (TEXT)
  - professionalism (TEXT)
  - respectfulness (TEXT)
  - confidence (TEXT)
  - created_at (REAL, Unix timestamp)

Index: idx_emails_recipient (for fast per-recipient queries)
```

**Extracted Schema** (captured from email):
```json
{
  "recipient": "prof.sharma@university.edu",
  "relationship": {
    "type": "Professor|Manager|Senior Colleague|Peer|Friend|Client|Other",
    "familiarity": "New|Developing|Established",
    "authority": "Higher|Equal|Lower"
  },
  "writing_style": {
    "tone": "Formal|Semi-formal|Casual",
    "politeness": "Very Polite|Polite|Neutral|Blunt",
    "warmth": "Warm|Neutral|Cold",
    "directness": "Direct|Indirect",
    "professionalism": "High|Medium|Low",
    "respectfulness": "High|Medium|Low",
    "confidence": "High|Moderate|Low"
  }
}
```

### 4. **Directory Structure**

```
data/
└── {user_id}/
    ├── sql_data/              (existing - chat/draft processing)
    │   ├── chat_thread_processing.db
    │   └── draft_processing.db
    ├── tone_db/               (NEW - tone pipeline storage)
    │   ├── email_history.db   (full audit history - SQLite)
    │   └── chroma_store/      (rolling embeddings - ChromaDB)
    ├── log_emails/            (existing - preprocessed emails)
    ├── store_attachments/     (existing - email attachments)
    └── vector_db/             (existing - email embeddings)
```

### 5. **Documentation**

- **`EMAIL_TONE_INTEGRATION.md`**: Comprehensive integration guide covering:
  - Architecture and data flow
  - Schema documentation
  - Usage examples from code
  - Ollama requirements
  - Fallback behavior
  - Admin notes for cleanup/monitoring

- **`email_tone_pipeline_demo.py`**: Demo script with:
  - End-to-end pipeline walkthrough
  - Mock data for testing without live Ollama
  - Directory structure verification
  - Profile aggregation examples
  - Integration point documentation

## Data Flow

```
┌─ Email sent by user
│
├─ POST /api/label-email-async (with messages[])
│
├─ Preprocessing Pipeline
│
├─ Label Pipeline (determine category)
│
├─ ★ TONE CAPTURE (NEW)
│  ├─ Check: from == user_id?
│  ├─ If YES → extract tone
│  ├─ Store in SQLite (full history)
│  ├─ Embed + store in ChromaDB (keep 3 per recipient)
│  └─ Non-fatal errors logged
│
├─ Gmail API Push (apply label)
│
└─ Cleanup
```

## Key Features

✅ **Per-User Isolation**: Each user's tone data is siloed in their own directories  
✅ **Dual Storage**: SQLite for audit trail, ChromaDB for fast retrieval  
✅ **Automatic Eviction**: Rolling window enforced (3 emails per recipient in ChromaDB)  
✅ **Full Audit Trail**: All 100+ emails per recipient kept in SQLite  
✅ **Non-Fatal Errors**: Pipeline continues if Ollama/embeddings fail  
✅ **Graceful Degradation**: Works with or without Ollama server  
✅ **Integrated with Labeling**: Tone captured in same API call as label assignment  
✅ **Production-Ready**: Full error handling, logging, and clean interfaces  

## Usage

### Automatic (via Labeling API)

When a user's email is processed through the labeling pipeline:

```python
# POST /api/label-email-async
{
    "user_id": "student@university.edu",
    "thread_id": "thread_abc123",
    "messages": [...],
    "access_token": "ya29.xxx"
}
# Response: 202 Accepted
# Automatically captures tone for any emails where from == user_id
```

### Programmatic (Direct Usage)

```python
from agent.services.email_tone_pipeline import TonePipelineManager

# Initialize per-user manager
manager = TonePipelineManager(
    user_id="student@university.edu",
    base_data_dir="/path/to/data"
)

# Process a sent email
extracted = manager.process_sent_email(
    recipient="prof.sharma@university.edu",
    email_text="Dear Professor Sharma, thank you for..."
)

# Retrieve history (for aggregate profiling)
all_emails = manager.get_all_emails_for_recipient("prof.sharma@university.edu")

# Retrieve recent examples (for drafting)
recent_3 = manager.get_recent_emails_for_recipient("prof.sharma@university.edu", n_results=3)

manager.close()
```

## Testing

### Run Demo
```bash
cd d:\manotr\openmailbot
python agent/services/email_tone_pipeline_demo.py demo
```

### Check Schema
```bash
python agent/services/email_tone_pipeline_demo.py schema
```

### Show Integration Points
```bash
python agent/services/email_tone_pipeline_demo.py integration
```

### Unit Tests (if Ollama available)
```bash
python agent/services/email_tone_pipeline.py test
```

## Requirements

### Ollama (Optional but Recommended)

For automatic tone extraction:
```bash
ollama pull llama3.2
ollama pull nomic-embed-text:latest
ollama serve
```

If Ollama is unavailable:
- Tone extraction falls back to safe defaults
- No errors propagate
- Labeling pipeline continues normally

### Python Packages

Already in `agent/requirements.txt` or `backend/requirements.txt`:
- `chromadb` (for embeddings storage)
- `ollama` (for LLM calls)

## Integration Points

1. **`backend/main.py` - Line 28**: Import TonePipelineManager
2. **`backend/main.py` - Lines 2252-2323**: Helper function `_capture_tone_for_sent_emails()`
3. **`backend/main.py` - Lines 2476-2488**: Call tone capture in async labeling task

## Files Modified/Created

### New Files
- ✅ `agent/services/email_tone_pipeline.py` (870+ lines)
- ✅ `agent/services/email_tone_pipeline_demo.py` (250+ lines)
- ✅ `agent/services/EMAIL_TONE_INTEGRATION.md` (documentation)

### Modified Files
- ✅ `backend/main.py`
  - Added import (line 28)
  - Added helper function `_capture_tone_for_sent_emails()` (lines 2252-2323)
  - Integrated tone capture call (lines 2476-2488)

## Configuration

No additional configuration needed. The system automatically:
1. Creates `tone_db/` directory per user on first email
2. Initializes SQLite database schema
3. Creates ChromaDB collection
4. Manages rolling window eviction

## Future Enhancements

Potential extensions:
- [ ] Drafting agent integration (use stored profiles to generate replies)
- [ ] Tone clustering (group similar recipient relationships)
- [ ] Trend analysis (how does tone change over time per recipient?)
- [ ] Multi-recipient sent emails (handle CC/BCC)
- [ ] Analytics dashboard (show tone distribution)
- [ ] Export to other systems (backup/archive tone profiles)

## Troubleshooting

**No tone data being captured:**
- Check logs for `[tone]` entries
- Verify email has `from == user_id`
- Ensure email has recipients and body

**Ollama connection failed:**
- Falls back to defaults gracefully
- Check `ollama serve` is running
- Verify `http://localhost:11434` is reachable

**Database errors:**
- Check `data/{user_id}/tone_db/` exists
- Verify permissions on data directory
- Check disk space available

**Performance issues:**
- ChromaDB queries are fast (only 3 docs per recipient)
- SQLite queries indexed on recipient
- LLM calls are async (non-blocking)

## Support

See `EMAIL_TONE_INTEGRATION.md` for:
- Detailed architecture
- Complete usage examples
- Database schema reference
- Admin operations
- Monitoring guidelines

## Version History

- **2026-07-03**: Initial implementation
  - Core pipeline service
  - SQLite + ChromaDB storage
  - Label pipeline integration
  - Demo and documentation

---

**Status**: ✅ Production Ready  
**Last Updated**: 2026-07-03
