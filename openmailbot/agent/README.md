# Agent (Python + FastAPI)

AI processing backend for OpenMailBot. Handles email ingestion, embeddings generation, RAG queries, and LLM interactions.

## Features

### Core Services
- **Email Ingestion** - Fetch emails from Gmail/Outlook APIs
- **Embeddings** - Generate and store email embeddings (OpenAI, Sentence Transformers)
- **Vector Search** - Semantic search using Pinecone or FAISS
- **RAG Pipeline** - Retrieval-Augmented Generation for email queries
- **LLM Integration** - OpenAI, Anthropic Claude, Google Gemini, Ollama
- **Graph Database** - Thread relationships and contact networks (Neo4j)

## Architecture

```
FastAPI Server (main.py)
├── Services
│   ├── EmailIngestionService - Gmail/Outlook email fetching
│   ├── EmbeddingService - Embedding generation & vector storage
│   ├── RAGService - Semantic search + LLM generation
│   └── LLMService - Multi-provider LLM interface
├── Vector DB
│   ├── PineconeClient - Cloud vector database
│   └── FAISSClient - Local vector database
├── Graph DB
│   └── Neo4jClient - Thread relationships
└── Database
    └── MongoDBClient - Email metadata storage
```

## API Endpoints

### Health Check
- `GET /health` - Service health status

### Email Ingestion
- `POST /api/ingest` - Ingest emails from Gmail/Outlook
  ```json
  {
    "userId": "user-123",
    "tenantId": "tenant-456",
    "provider": "google",
    "accessToken": "token",
    "syncFrom": "2024-01-01T00:00:00Z"
  }
  ```

### Embeddings
- `POST /api/embed` - Generate and store embedding
  ```json
  {
    "text": "Email content...",
    "userId": "user-123",
    "tenantId": "tenant-456"
  }
  ```

### Summarization
- `POST /api/summarize` - Summarize email thread
  ```json
  {
    "emails": [
      {
        "from": "sender@example.com",
        "to": ["recipient@example.com"],
        "subject": "Meeting",
        "content": "Email body...",
        "timestamp": "2024-01-01T00:00:00Z"
      }
    ],
    "userId": "user-123",
    "tenantId": "tenant-456"
  }
  ```

### Reply Generation
- `POST /api/generate-reply` - Generate context-aware reply
  ```json
  {
    "email": { /* email object */ },
    "threadContext": [ /* previous emails */ ],
    "tone": "professional",
    "additionalContext": "Optional context",
    "userId": "user-123",
    "tenantId": "tenant-456"
  }
  ```

### RAG Query
- `POST /api/rag` - Query email history using RAG
  ```json
  {
    "query": "What's the status of Project X?",
    "userId": "user-123",
    "tenantId": "tenant-456",
    "emailContext": { /* optional current email */ }
  }
  ```

### Related Threads
- `POST /api/related-threads` - Find related email threads
  ```json
  {
    "threadId": "thread-789",
    "userId": "user-123",
    "tenantId": "tenant-456",
    "limit": 5
  }
  ```

### Sentiment Analysis
- `POST /api/analyze-sentiment` - Analyze email sentiment
  ```json
  {
    "text": "Email content..."
  }
  ```

## Setup

### 1. Install Dependencies

```bash
cd agent
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Update `.env` with your configuration:
- MongoDB URI
- OpenAI API key (for embeddings & GPT)
- Pinecone credentials (or use FAISS locally)
- Neo4j credentials
- LLM provider keys

### 3. Start the Server

```bash
python main.py
```

Or with uvicorn:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The agent will be available at `http://localhost:8000`.

## Configuration

### Vector Database

Choose between Pinecone (cloud) or FAISS (local):

**Pinecone:**
```env
VECTOR_DB_TYPE=pinecone
PINECONE_API_KEY=your-key
PINECONE_ENVIRONMENT=us-east-1-aws
```

**FAISS (Local):**
```env
VECTOR_DB_TYPE=faiss
```

### LLM Provider

Choose your LLM provider:

**OpenAI:**
```env
DEFAULT_LLM_PROVIDER=openai
OPENAI_API_KEY=your-key
DEFAULT_MODEL=gpt-4-turbo-preview
```

**Anthropic Claude:**
```env
DEFAULT_LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-key
DEFAULT_MODEL=claude-3-sonnet-20240229
```

**Ollama (Local):**
```env
DEFAULT_LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama2
```

### Embeddings

Choose embedding model:

**OpenAI:**
```env
EMBEDDING_MODEL=text-embedding-ada-002
EMBEDDING_DIMENSION=1536
```

**Sentence Transformers (Local):**
```env
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
```

## Services

### Email Ingestion Service
- Fetches emails from Gmail/Outlook APIs
- Extracts metadata (from, to, subject, content, etc.)
- Stores in MongoDB via backend API

### Embedding Service
- Generates embeddings using OpenAI or Sentence Transformers
- Stores embeddings in Pinecone or FAISS
- Provides semantic search capabilities
- Supports batch operations

### RAG Service
- Combines vector search with LLM generation
- Retrieves relevant emails based on query
- Generates contextual answers
- Returns sources for transparency

### LLM Service
- Multi-provider support (OpenAI, Anthropic, Ollama)
- Email summarization
- Context-aware reply generation
- Sentiment analysis
- Tone adaptation (professional, casual, etc.)

### Neo4j Client
- Manages email thread relationships
- Tracks contact networks
- Finds related threads by shared contacts
- Thread timeline visualization

## Development

### Run Tests
```bash
pytest
```

### Code Formatting
```bash
black .
```

### Type Checking
```bash
mypy .
```

## Performance

- **Embeddings**: ~100ms per email (OpenAI), <50ms (local)
- **RAG Query**: ~2-3 seconds (including LLM)
- **Summarization**: ~3-5 seconds for typical thread
- **Reply Generation**: ~2-4 seconds

## Dependencies

Key dependencies:
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `openai` - OpenAI API client
- `anthropic` - Anthropic API client
- `pinecone-client` - Pinecone vector DB
- `faiss-cpu` - Local vector search
- `sentence-transformers` - Local embeddings
- `neo4j` - Graph database client
- `motor` - Async MongoDB client
- `google-api-python-client` - Gmail API
- `msal` - Microsoft authentication

## Security

- API keys stored in environment variables
- No credential storage in code
- Tenant isolation in vector DB namespaces
- Secure OAuth token handling

## Monitoring

Check service health:
```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "ok",
  "timestamp": "2024-01-01T00:00:00Z",
  "service": "openmailbot-agent"
}
```