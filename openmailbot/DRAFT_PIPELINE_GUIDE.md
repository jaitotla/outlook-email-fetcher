# Draft Pipeline Integration Guide

## Overview

The Draft with Attachments Pipeline has been integrated into your OpenMailBot codebase. This system generates professional email drafts using:

- **OpenAI GPT-4o-mini** for intelligent tool selection
- **Ollama (llama3.2)** for local draft generation
- **ChromaDB** for semantic search over attachments
- **Flask Embedding API** for embeddings
- Hybrid approach (local + cloud) for privacy and cost efficiency

## File Structure

### New Files Created

```
openmailbot/agent/
└── services/
    └── draft_pipeline.py          # Main draft pipeline service

openmailbot/backend/
├── controllers/
│   └── draftController.js         # Draft request handlers
└── routes/
    └── draft.js                   # Draft API routes
```

### Modified Files

- `openmailbot/agent/main.py` - Added DraftWithAttachmentsPipeline import and endpoint
- `openmailbot/backend/server.js` - Added draft routes

## How It Works

### Processing Pipeline

1. **Load Thread Data**
   - Read emails from `EMAIL_LOGS_PATH/{thread_id}/{thread_id}.json`
   - Parse email thread structure

2. **Attachment Processing**
   - Load attachments from `EMAIL_ATTACHMENTS_PATH/{thread_id}/`
   - Extract content using LlamaIndex (PDF, CSV, PPTX)
   - Generate embeddings via Flask API
   - Store in user-specific ChromaDB

3. **Tool-Based Context Retrieval**
   - OpenAI decides which tools to call:
     - `get_attachments_by_id` - Get all attachment content
     - `query_attachments` - Semantic search in attachments
   - Execute tools to retrieve relevant context

4. **Draft Generation**
   - Ollama generates professional email draft
   - Uses email thread + attachment context
   - Respects user preferences (tone, position, custom instructions)

## API Endpoints

### Generate Draft with Attachments

**POST** `/api/draft/with-attachments` (requires authentication)

Request body:
```json
{
  "user_id": "user@example.com",
  "thread_id": "gmail_thread_id",
  "user_preferences": {
    "name": "John Doe",
    "position": "Manager",
    "tone": "professional and concise",
    "custom_instructions": "Include action items in bullets"
  }
}
```

Response:
```json
{
  "success": true,
  "response": "Dear [Recipient],\n\nThank you for your email...",
  "processing_info": {
    "attachments_found": 2,
    "attachments_processed": 2,
    "attachments_skipped": 0,
    "errors": []
  },
  "thread_id": "gmail_thread_id",
  "user_id": "user@example.com"
}
```

### Get Draft Preferences

**GET** `/api/draft/preferences?userId=user@example.com` (requires authentication)

Response:
```json
{
  "success": true,
  "preferences": {
    "name": "John Doe",
    "position": "Manager",
    "tone": "professional and concise",
    "custom_instructions": "Include action items"
  }
}
```

### Save Draft Preferences

**POST** `/api/draft/preferences` (requires authentication)

Request body:
```json
{
  "userId": "user@example.com",
  "preferences": {
    "name": "John Doe",
    "position": "Senior Manager",
    "tone": "friendly and professional",
    "custom_instructions": "Keep it brief"
  }
}
```

### Health Check

**GET** `/api/draft/health`

Response:
```json
{
  "success": true,
  "status": "healthy",
  "agent_status": "ok",
  "agent_url": "http://localhost:8000"
}
```

## Database Schema

### SQLite: draft_processing table

```sql
CREATE TABLE draft_processing (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    attachment_id TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    processed_status TEXT DEFAULT 'pending',
    processed_timestamp DATETIME,
    chroma_collection TEXT,
    metadata TEXT,
    UNIQUE(user_id, thread_id, attachment_id)
)
```

### ChromaDB: User-specific collections

- **Location**: `./data_pipeline/draft_cdb_{user_id}/`
- **Collection**: `draft_documents`
- **Metadata**: `{"hnsw:space": "cosine"}`

## Configuration

### Environment Variables

In `openmailbot/agent/.env`:

```env
# Embedding service
FLASK_EMBED_URL=http://localhost:5050/embed

# OpenAI API (for tool calling)
OPENAI_API_KEY=sk-your-key-here

# Ollama service
OLLAMA_MODEL=llama3.2
OLLAMA_TEMP=0.4

# Email data paths
EMAIL_LOGS_PATH=/path/to/email_logs
EMAIL_ATTACHMENTS_PATH=./email_attachments
```

## User Preferences

User draft preferences are stored in MongoDB User model:

- `firstName` → name
- `position` → position/title
- `draftTone` → preferred tone
- `customInstructions` → custom instructions

These can be set via:
- `/api/draft/preferences` endpoint
- User settings in frontend
- User model direct update

## Performance Notes

- **First draft (with new attachments)**: 10-30 seconds
- **Subsequent drafts (cached embeddings)**: 3-5 seconds
- **Large attachments**: May add 10-15 seconds per PDF

## File Format Requirements

### Email Logs Structure

```
/path/to/email_logs/
└── {thread_id}/
    └── {thread_id}.json
```

**JSON Format:**
```json
{
  "messages": [
    {
      "message_id": "msg123",
      "from": "sender@example.com",
      "to": ["recipient@example.com"],
      "subject": "Meeting Follow-up",
      "timestamp": "2024-01-27T10:00:00Z",
      "body": "Here are the items we discussed..."
    }
  ]
}
```

### Attachments Structure

```
./email_attachments/
└── {thread_id}/
    ├── document.pdf
    ├── spreadsheet.csv
    └── {message_id}_metadata.json
```

**Metadata Format:**
```json
{
  "message_id": "msg123",
  "attachments": [
    {
      "filename": "document.pdf",
      "filepath": "./email_attachments/thread123/document.pdf"
    }
  ]
}
```

## Troubleshooting

### Service Connection Issues

**Problem**: "Python agent service unavailable"

**Solution**:
```bash
# Check agent is running
curl http://localhost:8000/health

# Check backend can reach agent
curl http://localhost:3000/api/draft/health
```

### No Thread Data Found

**Problem**: "Thread JSON not found for thread_id: xyz"

**Solution**:
- Verify email logs exist: `EMAIL_LOGS_PATH/{thread_id}/{thread_id}.json`
- Check JSON format matches schema
- Verify thread_id matches actual file

### Embedding API Errors

**Problem**: "Embedding API error"

**Solution**:
- Verify Flask embedding service running on port 5050
- Check `FLASK_EMBED_URL` environment variable
- Test: `curl -X POST http://localhost:5050/embed -H "Content-Type: application/json" -d '{"text": "test"}'`

### Ollama Not Responding

**Problem**: "Ollama service unavailable"

**Solution**:
```bash
# Start Ollama
ollama serve

# Verify model available
ollama list | grep llama3.2
```

## Breaking Changes Analysis

✅ **No Breaking Changes**

- New pipeline is completely separate
- Existing chat pipeline unchanged
- Existing endpoints unchanged
- New endpoints only additions
- No database schema modifications to existing tables
- No existing service modifications

## Testing the Draft Pipeline

### Manual API Test

```bash
# Health check
curl http://localhost:3000/api/draft/health

# Generate draft (requires auth token)
curl -X POST http://localhost:3000/api/draft/with-attachments \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -d '{
    "user_id": "user@example.com",
    "thread_id": "abc123",
    "user_preferences": {
      "name": "John",
      "position": "Manager",
      "tone": "professional"
    }
  }'
```

### Verify Database

```powershell
# Check processed attachments
sqlite3.exe .\data_pipeline\draft_processing.db "SELECT * FROM draft_processing LIMIT 5;"

# List user ChromaDB instances
Get-ChildItem .\data_pipeline\ | Where-Object {$_.Name -like "draft_cdb_*"}
```

## Comparison: Chat vs Draft Pipeline

| Feature | Chat Pipeline | Draft Pipeline |
|---------|---------------|----------------|
| **Purpose** | Answer questions about threads | Generate email drafts |
| **Tool Selection** | OpenAI decides search strategy | OpenAI decides attachment retrieval |
| **Final Generation** | Ollama (answer generation) | Ollama (draft generation) |
| **Input** | Question from user | Thread + preferences |
| **Output** | Answer text | Draft email |
| **Attachments** | Searchable via semantic search | Retrieved for draft context |
| **DB Name** | chat_thread_processing.db | draft_processing.db |
| **ChromaDB Prefix** | cdb_ | draft_cdb_ |
| **Collection Name** | email_threads | draft_documents |

## Integration Points

### Frontend
- Call `/api/draft/with-attachments` for draft generation
- Display draft response to user
- Use `/api/draft/preferences` for user settings

### Backend
- Express routes forward requests to Python agent
- Authentication middleware protects endpoints
- MongoDB stores user preferences

### Python Agent
- FastAPI endpoint `/draft-with-attachments`
- DraftWithAttachmentsPipeline orchestrates process
- Uses existing embeddings and Ollama services

## Future Enhancements

Potential improvements:
- [ ] Save generated drafts to database
- [ ] Draft versioning/history
- [ ] Batch draft generation
- [ ] Draft templates
- [ ] Custom system prompts per user
- [ ] Draft regeneration with feedback
- [ ] Integration with Gmail API to send

## Support

For detailed setup, see:
- [CHAT_PIPELINE_QUICKSTART.md](CHAT_PIPELINE_QUICKSTART.md) - General setup
- [CHAT_PIPELINE_INTEGRATION.md](CHAT_PIPELINE_INTEGRATION.md) - Environment config
