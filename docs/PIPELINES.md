# Pipeline Documentation

This document provides technical details for the Chat and Draft pipelines.

---

## Chat Pipeline

### Overview

The Chat Pipeline enables users to chat with their email threads using a RAG (Retrieval-Augmented Generation) approach.

**Components:**
- **OpenAI GPT-4o-mini** - Tool calling and decision making
- **Ollama (llama3.2)** - Local answer generation
- **ChromaDB** - Semantic search over emails and attachments
- **Flask/Embedding API** - Embeddings

### API Endpoints

#### Chat with Thread

**POST** `/api/chat/thread` (authenticated)

```json
// Request
{
  "user_id": "user@example.com",
  "thread_id": "gmail_thread_id",
  "question": "What is the main topic of this thread?"
}

// Response
{
  "success": true,
  "response": "The main topic is...",
  "sources": ["email_1", "attachment_2"]
}
```

#### Search Thread

**POST** `/api/chat/search` (authenticated)

```json
// Request
{
  "threadId": "gmail_thread_id",
  "query": "budget numbers"
}

// Response
{
  "results": [
    { "content": "...", "score": 0.92, "source": "attachment" }
  ]
}
```

#### Health Check

**GET** `/api/chat/health`

```json
{
  "success": true,
  "status": "healthy",
  "services": {
    "ollama": "connected",
    "chromadb": "connected"
  }
}
```

### How It Works

1. **Load Thread Data**
   - Read emails from `EMAIL_LOGS_PATH/{thread_id}/{thread_id}.json`
   - Parse email thread structure

2. **Process Unprocessed Items**
   - Check SQLite tracking database
   - Generate embeddings for new emails
   - Store in per-user ChromaDB collection

3. **Attachment Processing**
   - Load attachments from `EMAIL_ATTACHMENTS_PATH/{thread_id}/`
   - Extract content using LlamaIndex (PDF, CSV, PPTX)
   - Chunk and embed each attachment

4. **Tool-Based Retrieval**
   - OpenAI decides which tools to call:
     - `get_emails_by_id` - Get specific emails
     - `query_emails` - Semantic search in emails
     - `get_attachments_by_id` - Get attachment content
     - `query_attachments` - Semantic search in attachments
   - Execute tools to retrieve relevant context

5. **Answer Generation**
   - Ollama generates final answer
   - Uses retrieved context + original question
   - Cites sources in response

### Configuration

```env
# In agent/.env
FLASK_EMBED_URL=http://localhost:5050/embed
OPENAI_API_KEY=sk-your-key-here
OLLAMA_MODEL=llama3.2
OLLAMA_TEMP=0.4
EMAIL_LOGS_PATH=/path/to/email_logs
EMAIL_ATTACHMENTS_PATH=./email_attachments
CHAT_DB_PATH=./data_pipeline/chat_thread_processing.db
```

---

## Draft Pipeline

### Overview

The Draft Pipeline generates professional email replies with attachment context.

**Components:**
- **OpenAI GPT-4o-mini** - Intelligent tool selection
- **Ollama (llama3.2)** - Local draft generation (privacy)
- **ChromaDB** - Semantic search over attachments
- **Flask Embedding API** - Embeddings

### API Endpoints

#### Generate Draft with Attachments

**POST** `/api/draft/with-attachments` (authenticated)

```json
// Request
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

// Response
{
  "success": true,
  "response": "Dear [Recipient],\n\nThank you for your email...",
  "processing_info": {
    "attachments_found": 2,
    "attachments_processed": 2,
    "attachments_skipped": 0,
    "errors": []
  }
}
```

#### Get/Save Draft Preferences

**GET** `/api/draft/preferences?userId=user@example.com`

```json
{
  "name": "John Doe",
  "position": "Manager",
  "tone": "professional",
  "custom_instructions": ""
}
```

**POST** `/api/draft/preferences`

```json
{
  "userId": "user@example.com",
  "preferences": {
    "name": "John Doe",
    "position": "Manager",
    "tone": "professional and concise"
  }
}
```

### How It Works

1. **Load Thread Data**
   - Read emails from JSON file
   - Parse email thread structure

2. **Attachment Processing**
   - Load from `EMAIL_ATTACHMENTS_PATH/{thread_id}/`
   - Extract content (PDF, CSV, PPTX)
   - Generate embeddings
   - Store in per-user ChromaDB

3. **Tool-Based Context Retrieval**
   - OpenAI decides which tools to call:
     - `get_attachments_by_id` - Get all attachment content
     - `query_attachments` - Semantic search in attachments
   - Execute tools to retrieve relevant context

4. **Draft Generation**
   - Ollama generates professional email draft
   - Uses email thread + attachment context
   - Respects user preferences (tone, position, instructions)

### User Preferences

Preferences are stored in the User model:

```javascript
// MongoDB User.settings
{
  draftPreferences: {
    name: "John Doe",
    position: "Manager",
    tone: "professional",
    customInstructions: "Always include next steps"
  }
}
```

---

## Testing

### Prerequisites

1. All services running (Agent, Backend, Ollama, Flask Embeddings)
2. Test email logs created
3. Authentication configured

### Quick Health Check

```bash
# Chat service
curl http://localhost:3000/api/chat/health

# Draft service
curl http://localhost:3000/api/draft/health

# Agent health
curl http://localhost:8000/health
```

### Create Test Data

```bash
# Create test email logs directory
mkdir -p email_logs/test-thread-1

# Create test thread JSON
cat > email_logs/test-thread-1/test-thread-1.json << 'EOF'
{
  "messages": [
    {
      "message_id": "msg1",
      "from": "sender@example.com",
      "to": ["recipient@example.com"],
      "subject": "Project Update",
      "timestamp": "2024-01-27T10:00:00Z",
      "body": "Hi, can you review the attached project update?"
    }
  ]
}
EOF

# Create test attachments directory
mkdir -p email_attachments/test-thread-1

# Create test attachment
echo "Project Status: On track. Budget: $50,000" > email_attachments/test-thread-1/update.txt
```

### Test Chat Endpoint

```bash
curl -X POST http://localhost:3000/api/chat/thread \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "user_id": "test@example.com",
    "thread_id": "test-thread-1",
    "question": "What is the project status?"
  }'
```

### Test Draft Endpoint

```bash
curl -X POST http://localhost:3000/api/draft/with-attachments \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "user_id": "test@example.com",
    "thread_id": "test-thread-1",
    "user_preferences": {
      "name": "John Doe",
      "tone": "professional"
    }
  }'
```

---

## Performance Notes

| Operation | First Run | Cached |
|-----------|-----------|--------|
| Chat with thread | 10-30s | 3-5s |
| Draft generation | 15-40s | 5-10s |
| Attachment processing | 5-15s per file | Skipped |

### Optimization Tips

1. **Pre-process attachments** - Run ingestion before user requests
2. **Use smaller models** - `llama3.2:3b` for faster responses
3. **Limit chunk size** - Smaller chunks = faster retrieval
4. **Cache embeddings** - SQLite tracking prevents reprocessing

---

## Troubleshooting

### "Ollama connection refused"
```bash
# Check Ollama is running
curl http://localhost:11434/api/version

# Start Ollama
ollama serve
```

### "ChromaDB not found"
```bash
# Check ChromaDB is running
curl http://localhost:8500/api/v1/heartbeat

# Start ChromaDB
chroma run --host localhost --port 8500
```

### "OpenAI API error"
- Check `OPENAI_API_KEY` is set
- Verify key has credits
- Check rate limits

### "Embeddings timeout"
- Check Flask embedding service at `FLASK_EMBED_URL`
- Verify network connectivity
- Check GPU availability
