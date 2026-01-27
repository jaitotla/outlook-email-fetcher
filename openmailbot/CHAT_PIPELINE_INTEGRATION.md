# Chat Pipeline Integration Guide

## Overview

The Chat Pipeline has been successfully integrated into the OpenMailBot codebase. This system enables users to chat with their email threads using a RAG (Retrieval-Augmented Generation) approach with:

- **OpenAI GPT-4o-mini** for tool calling and decision making
- **Ollama (llama3.2)** for local answer generation
- **ChromaDB** for semantic search over emails and attachments
- **Flask/Embedding API** for embeddings

## File Structure

### New Files Created

```
openmailbot/agent/
├── prompt/
│   ├── __init__.py          # Prompt module exports
│   └── prompt.py            # All prompts and utilities
│
└── services/
    └── chat_pipeline.py     # Main chat pipeline service

openmailbot/backend/
├── controllers/
│   └── chatController.js    # Chat request handlers
│
└── routes/
    └── chat.js              # Chat API routes
```

### Modified Files

- `openmailbot/agent/main.py` - Added ChatWithThreadPipeline import and endpoint
- `openmailbot/agent/requirements.txt` - Added new dependencies
- `openmailbot/backend/server.js` - Added chat routes

## Installation & Setup

### 1. Install Python Dependencies

```bash
cd openmailbot/agent
pip install -r requirements.txt
```

### 2. Configure Environment Variables

In `openmailbot/agent/.env`:

```env
# Embedding service
FLASK_EMBED_URL=http://localhost:5050/embed

# OpenAI API (for tool calling)
OPENAI_API_KEY=sk-your-key-here

# Ollama service (running locally)
OLLAMA_MODEL=llama3.2
OLLAMA_TEMP=0.4

# Email data paths
EMAIL_LOGS_PATH=/path/to/email_logs
EMAIL_ATTACHMENTS_PATH=./email_attachments

# Database
CHAT_DB_PATH=./data_pipeline/chat_thread_processing.db
```

### 3. Start Required Services

```bash
# Terminal 1: Start Python Agent (FastAPI)
cd openmailbot/agent
python main.py

# Terminal 2: Start Node Backend
cd openmailbot/backend
npm start

# Terminal 3: Ensure Ollama is running
ollama serve
```

## API Endpoints

### Chat with Thread

**POST** `/api/chat/thread` (requires authentication)

Request body:
```json
{
  "user_id": "user@example.com",
  "thread_id": "gmail_thread_id",
  "question": "What is the main topic of this thread?"
}
```

Response:
```json
{
  "success": true,
  "answer": "The main topic is...",
  "processing_info": {
    "emails": {
      "total_messages": 5,
      "already_processed": 3,
      "newly_processed": 2,
      "errors": []
    },
    "attachments": {
      "attachments_found": 2,
      "attachments_processed": 1,
      "attachments_skipped": 1,
      "errors": []
    }
  },
  "thread_id": "gmail_thread_id",
  "user_id": "user@example.com"
}
```

### Search Thread

**POST** `/api/chat/search` (requires authentication)

Request body:
```json
{
  "user_id": "user@example.com",
  "thread_id": "gmail_thread_id",
  "query": "budget numbers"
}
```

### Get Chat History

**GET** `/api/chat/thread/:threadId` (requires authentication)

Query parameters:
- `userId` (required)

### Health Check

**GET** `/api/chat/health`

Returns:
```json
{
  "success": true,
  "status": "healthy",
  "agent_status": "ok",
  "agent_url": "http://localhost:8000"
}
```

## How It Works

### Processing Pipeline

1. **Email Processing**
   - Load emails from `EMAIL_LOGS_PATH/{thread_id}/{thread_id}.json`
   - Check if already processed in ChromaDB
   - Generate embeddings via Flask API
   - Store in user-specific ChromaDB collection

2. **Attachment Processing**
   - Load attachments from `EMAIL_ATTACHMENTS_PATH/{thread_id}/`
   - Extract content using LlamaIndex file readers (PDF, CSV, PPTX)
   - Generate embeddings for each chunk
   - Store in ChromaDB with metadata

3. **Chat/Query Processing**
   - Use OpenAI to determine which tools to call:
     - `search_thread_emails` - Search email content
     - `search_attachments` - Search document content
   - Execute tools to retrieve relevant context
   - Pass context to Ollama for natural language answer
   - Return answer with processing metadata

### Data Isolation

- Each user has their own ChromaDB instance: `./data_pipeline/cdb_{user_id}/`
- Each user has their own collection: `email_threads`
- SQLite tracks processed emails and attachments

## Prompt Management

All prompts are centralized in `agent/prompt/prompt.py`:

- `TOOL_CALLING_SYSTEM_PROMPT` - For OpenAI tool selection
- `FINAL_ANSWER_SYSTEM_PROMPT_TEMPLATE` - For Ollama answer generation
- Formatting templates for email and attachment results
- Helper functions: `get_final_answer_system_prompt()`, `format_email_result()`, etc.

### Using Prompts

```python
from prompt import (
    TOOL_CALLING_SYSTEM_PROMPT,
    get_final_answer_system_prompt,
    format_email_result
)

# Use system prompt
system_msg = TOOL_CALLING_SYSTEM_PROMPT

# Generate dynamic prompt
final_prompt = get_final_answer_system_prompt(
    thread_id="xyz123",
    user_id="user@example.com"
)

# Format results
result = format_email_result(
    index=1,
    relevance=0.95,
    message_id="msg123",
    from_email="sender@example.com",
    subject="Test",
    timestamp="2024-01-27T10:00:00",
    content="Email body..."
)
```

## Database Schema

### SQLite Tables

**email_embeddings**
```sql
CREATE TABLE email_embeddings (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    processed_status TEXT DEFAULT 'completed',
    chroma_collection TEXT,
    UNIQUE(user_id, thread_id, message_id)
)
```

**attachment_processing**
```sql
CREATE TABLE attachment_processing (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    message_id TEXT,
    attachment_id TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    processed_status TEXT DEFAULT 'pending',
    processed_timestamp DATETIME,
    chroma_collection TEXT,
    metadata TEXT,
    UNIQUE(user_id, thread_id, attachment_id)
)
```

## Configuration Files

### config.py (Agent)

Add these settings to your `.env`:

```python
# In agent/config.py
FLASK_EMBED_URL: str = "http://localhost:5050/embed"
OLLAMA_MODEL: str = "llama3.2"
OLLAMA_TEMP: float = 0.4
```

### Environment Variables

Required:
- `OPENAI_API_KEY` - For GPT-4o-mini
- `FLASK_EMBED_URL` - Embedding service URL
- `EMAIL_LOGS_PATH` - Path to email logs
- `EMAIL_ATTACHMENTS_PATH` - Path to attachments

Optional:
- `OLLAMA_MODEL` - Default: `llama3.2`
- `OLLAMA_TEMP` - Default: `0.4`
- `CHAT_DB_PATH` - Default: `./data_pipeline/chat_thread_processing.db`

## File Format Requirements

### Email Logs Structure

```
/home/manotr/swapnil/email_logs/
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
      "subject": "Re: Discussion",
      "timestamp": "2024-01-27T10:00:00Z",
      "body": "Email content here..."
    }
  ]
}
```

### Attachments Structure

```
./email_attachments/
└── {thread_id}/
    ├── {filename}.pdf
    ├── {filename}.csv
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

**Problem:** "Chat service unavailable"

**Solution:**
```bash
# Check agent is running
curl http://localhost:8000/health

# Check backend can reach agent
curl http://localhost:3000/api/chat/health
```

### Embedding API Errors

**Problem:** "Embedding API error"

**Solution:**
- Verify Flask embedding service is running on port 5050
- Check `FLASK_EMBED_URL` in environment

### Ollama Not Responding

**Problem:** "Ollama service unavailable"

**Solution:**
```bash
# Start Ollama
ollama serve

# Verify model is available
ollama list | grep llama3.2
```

### No Emails Processing

**Problem:** "No messages found in thread"

**Solution:**
- Verify email logs exist at `EMAIL_LOGS_PATH`
- Check JSON format matches schema
- Verify user_id and thread_id match

## Performance Notes

- **First query per thread**: ~5-30 seconds (processing all emails/attachments)
- **Subsequent queries**: ~2-5 seconds (using cached embeddings)
- **Large attachments**: May take additional time for PDF extraction
- **ChromaDB**: Stores embeddings locally, no external calls

## Breaking Changes

✅ **No breaking changes** - All existing functionality preserved:
- Existing FastAPI endpoints work as before
- Existing Express routes work as before
- New endpoints are additions only
- New chat routes use existing auth middleware

## Testing

### Manual API Testing

```bash
# Health check
curl http://localhost:3000/api/chat/health

# Chat with thread
curl -X POST http://localhost:3000/api/chat/thread \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -d '{
    "user_id": "user@example.com",
    "thread_id": "abc123",
    "question": "What is this about?"
  }'
```

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review logs in `/data_pipeline/` directory
3. Verify all services are running: agent, backend, ollama, embedding API
4. Check environment variables are set correctly
