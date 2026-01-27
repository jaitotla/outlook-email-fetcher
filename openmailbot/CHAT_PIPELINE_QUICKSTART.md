# Chat Pipeline - Quick Start Guide

## 🚀 30-Minute Setup

### Prerequisites
- Python 3.8+
- Node.js 16+
- OpenAI API key
- Ollama installed locally
- Flask embedding service running (port 5050)

---

## Step 1: Install Python Dependencies (5 min)

```bash
cd openmailbot/agent

# Create virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

## Step 2: Configure Environment (5 min)

### Create/Update `.env` in `openmailbot/agent/`

```env
# Required: OpenAI API Key
OPENAI_API_KEY=sk-your-actual-key-here

# Required: Embedding API endpoint
FLASK_EMBED_URL=http://localhost:5050/embed

# Optional: Ollama settings
OLLAMA_MODEL=llama3.2
OLLAMA_TEMP=0.4

# Required: Email data paths
EMAIL_LOGS_PATH=/path/to/email_logs
EMAIL_ATTACHMENTS_PATH=./email_attachments

# MongoDB (from existing config)
MONGODB_URI=mongodb://localhost:27017/openmailbot
```

---

## Step 3: Start Services (5 min)

### Terminal 1: Start Ollama
```bash
ollama serve
# Should display: "listening on 127.0.0.1:11434"
```

### Terminal 2: Start FastAPI Agent
```bash
cd openmailbot/agent
python main.py
# Should display: "Uvicorn running on http://0.0.0.0:8000"
```

### Terminal 3: Start Express Backend
```bash
cd openmailbot/backend
npm start
# Should display: "listening on port 3000"
```

### Terminal 4: Ensure Flask Embedding Service
```bash
# This should already be running separately
# Make sure it's on port 5050
curl http://localhost:5050/health
```

---

## Step 4: Verify Installation (5 min)

### Test 1: Health Checks
```bash
# Test FastAPI Agent
curl http://localhost:8000/health
# Response: {"status": "ok", ...}

# Test Express Backend
curl http://localhost:3000/health
# Response: {"status": "ok", ...}

# Test Chat API
curl http://localhost:3000/api/chat/health
# Response: {"success": true, "status": "healthy", ...}
```

### Test 2: Full Chat Test
```bash
curl -X POST http://localhost:3000/api/chat/thread \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test@example.com",
    "thread_id": "test-thread-123",
    "question": "What is the main topic?"
  }'
```

**Expected Response**:
```json
{
  "success": true,
  "answer": "The answer based on your emails...",
  "processing_info": {
    "emails": {...},
    "attachments": {...}
  }
}
```

---

## API Endpoints Available

### 1. Chat with Thread
```
POST /api/chat/thread
Headers: Content-Type: application/json
Body: {
  "user_id": "user@example.com",
  "thread_id": "gmail_thread_id", 
  "question": "Your question here"
}
```

### 2. Search Within Thread
```
POST /api/chat/search
Body: {
  "user_id": "user@example.com",
  "thread_id": "gmail_thread_id",
  "query": "search term"
}
```

### 3. Get Chat History
```
GET /api/chat/thread/{threadId}?userId=user@example.com
```

### 4. Health Check
```
GET /api/chat/health
```

---

## Directory Structure Created

```
openmailbot/
├── agent/
│   ├── prompt/
│   │   ├── __init__.py         ✨ NEW
│   │   └── prompt.py           ✨ NEW
│   ├── services/
│   │   └── chat_pipeline.py    ✨ NEW
│   ├── main.py                 📝 UPDATED
│   └── requirements.txt         📝 UPDATED
│
└── backend/
    ├── controllers/
    │   └── chatController.js   ✨ NEW
    ├── routes/
    │   └── chat.js             ✨ NEW
    └── server.js               📝 UPDATED
```

---

## Common Issues & Solutions

### Issue: "Chat service unavailable"
```bash
# Check if agent is running
curl http://localhost:8000/health

# If not, start it
cd openmailbot/agent
python main.py
```

### Issue: "Embedding API error"
```bash
# Check if Flask embedding service is running
curl http://localhost:5050/health

# If not, start it on the correct port
```

### Issue: "Ollama not responding"
```bash
# Check if Ollama is running
ollama serve

# Verify the model exists
ollama list | grep llama3.2
```

### Issue: "No emails found"
```bash
# Verify email logs directory structure:
# EMAIL_LOGS_PATH/thread-id/thread-id.json

# Verify JSON format is correct (see docs)
cat /path/to/email_logs/your-thread-id/your-thread-id.json
```

### Issue: "Database error"
```bash
# Check SQLite database location
ls -la ./data_pipeline/

# Recreate if needed (will auto-init on next run)
rm -f ./data_pipeline/chat_thread_processing.db
```

---

## Testing with Sample Data

### Create Test Email JSON
```bash
mkdir -p /path/to/email_logs/test-thread-1

cat > /path/to/email_logs/test-thread-1/test-thread-1.json << 'EOF'
{
  "messages": [
    {
      "message_id": "msg1",
      "from": "sender@example.com",
      "to": ["recipient@example.com"],
      "subject": "Project Update",
      "timestamp": "2024-01-27T10:00:00Z",
      "body": "Here's the latest project status..."
    },
    {
      "message_id": "msg2",
      "from": "recipient@example.com",
      "to": ["sender@example.com"],
      "subject": "Re: Project Update",
      "timestamp": "2024-01-27T11:00:00Z",
      "body": "Thanks for the update. I agree with the timeline..."
    }
  ]
}
EOF
```

### Test Chat with Sample Data
```bash
curl -X POST http://localhost:3000/api/chat/thread \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user@example.com",
    "thread_id": "test-thread-1",
    "question": "What is the project status?"
  }'
```

---

## Monitoring & Logs

### View Agent Logs
```bash
# Terminal where agent is running
tail -f agent.log
```

### View Backend Logs
```bash
# Terminal where backend is running
tail -f backend.log
```

### View Chat Pipeline Database
```bash
# SQLite database location
./data_pipeline/chat_thread_processing.db

# View with sqlite3
sqlite3 ./data_pipeline/chat_thread_processing.db
.tables
SELECT * FROM email_embeddings LIMIT 5;
```

### View ChromaDB Storage
```bash
# Vector database location (per user)
./data_pipeline/cdb_{user_id}/

# Lists all user ChromaDB instances
ls -la ./data_pipeline/ | grep cdb_
```

---

## Performance Tips

1. **First Query**: Will be slow (processing emails/attachments)
   - Typical: 5-30 seconds
   - Reason: Generating embeddings for all content

2. **Subsequent Queries**: Much faster
   - Typical: 2-5 seconds
   - Reason: Using cached embeddings

3. **Large Attachments**: May take extra time
   - Typical: +10-15 seconds per large PDF
   - Optimize: Limit attachment size if possible

4. **Batch Operations**: Not supported yet
   - Process one thread at a time
   - Future: Can add batch endpoints if needed

---

## Next Steps

1. ✅ Setup complete!
2. 📖 Read [CHAT_PIPELINE_INTEGRATION.md](CHAT_PIPELINE_INTEGRATION.md) for detailed guide
3. 📝 Check [prompt/prompt.py](agent/prompt/prompt.py) to customize prompts
4. 🔧 Integrate into frontend if needed
5. 🚀 Deploy to production when ready

---

## Example Integration in Frontend

### React Component (example)
```jsx
import { useState } from 'react';

export function ChatWithThread({ threadId, userId }) {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [loading, setLoading] = useState(false);

  const handleChat = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/chat/thread', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({
          user_id: userId,
          thread_id: threadId,
          question
        })
      });
      
      const data = await response.json();
      setAnswer(data.answer);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <textarea 
        value={question} 
        onChange={(e) => setQuestion(e.target.value)}
        placeholder="Ask about this thread..."
      />
      <button onClick={handleChat} disabled={loading}>
        {loading ? 'Processing...' : 'Ask'}
      </button>
      {answer && <div>{answer}</div>}
    </div>
  );
}
```

---

## Troubleshooting Checklist

- [ ] All 3 services running (Agent, Backend, Ollama)
- [ ] OpenAI API key set in `.env`
- [ ] Email logs directory exists and has data
- [ ] Flask embedding service on port 5050
- [ ] MongoDB connection working
- [ ] Ports 3000, 8000, 11434 not in use
- [ ] Python 3.8+ installed
- [ ] Node 16+ installed
- [ ] Ollama model available: `ollama list`

---

## Support

For detailed information:
- **Full Guide**: [CHAT_PIPELINE_INTEGRATION.md](CHAT_PIPELINE_INTEGRATION.md)
- **Changes Made**: [CHANGES_MADE.md](CHANGES_MADE.md)
- **Integration Summary**: [INTEGRATION_SUMMARY.md](INTEGRATION_SUMMARY.md)

Good luck! 🚀
