# 🏗️ OpenMailBot Architecture & Data Flow Guide

*A visual guide to understanding how OpenMailBot works*

---

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          USER INTERFACES                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────────┐      ┌──────────────────┐    ┌────────────────┐   │
│  │   Gmail Add-on   │      │ Thunderbird      │    │  Web Dashboard │   │
│  │  (Google Apps    │      │  Extension       │    │  (Next.js)     │   │
│  │   Script)        │      │  (WebExtension)  │    │  Frontend      │   │
│  └────────┬─────────┘      └────────┬─────────┘    └────────┬───────┘   │
│           │                         │                       │            │
│           └─────────────┬───────────┴───────────────────────┘            │
│                         │                                                 │
└─────────────────────────┼─────────────────────────────────────────────────┘
                          │
                    HTTPS/REST API
                          │
         ┌────────────────┴────────────────┐
         │                                 │
┌────────▼───────────────────┐   ┌────────▼──────────────────┐
│   BACKEND (Node.js/        │   │  AGENT (Python/FastAPI)    │
│   Express)                 │   │                            │
│   Port: 3000               │   │  Port: 5051                │
├────────────────────────────┤   ├────────────────────────────┤
│ • Authentication (JWT)     │   │ • Email Ingestion          │
│ • User Settings Storage    │   │ • AI/LLM Processing        │
│ • Email Metadata           │   │ • Embeddings Generation    │
│ • API Orchestration        │   │ • RAG Query Pipeline       │
│ • Rate Limiting            │   │ • Label Classification     │
│ • Notifications            │   │ • Sentiment Analysis       │
└────────┬───────────────────┘   └────────┬──────────────────┘
         │                                │
         └──────────────┬─────────────────┘
                        │
              Database Connections
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
   ┌─────────┐   ┌──────────┐   ┌────────────┐
   │ MongoDB │   │  Neo4j   │   │   Vector   │
   │ (User   │   │ (Graph   │   │   DB       │
   │ Data)   │   │  Store)  │   │ (Pinecone) │
   └─────────┘   └──────────┘   └────────────┘
        │               │               │
        │  Metadata     │  Relations    │  Embeddings
        │  Settings     │  Threads      │  Search Index
        │  Accounts     │  Contacts     │  Semantic Data
```

---

## Data Flow: Email Ingestion to Response

```
1. USER SENDS EMAIL
   │
   ├─ Gmail: User receives email
   ├─ Thunderbird: New email arrives
   │
   ▼
2. EMAIL SYNC (via IMAP/Gmail API)
   │
   Backend periodically checks:
   │
   ├─ Gmail API: GET /messages
   ├─ IMAP: FETCH new emails
   │
   ▼
3. EMAIL PREPROCESSING (Backend)
   │
   ├─ Parse email content
   ├─ Extract sender, recipient, subject
   ├─ Generate email ID & metadata
   ├─ Store in MongoDB
   │
   ▼
4. SEND TO AGENT FOR PROCESSING
   │
   POST /api/store
   │
   ├─ Email content
   ├─ User ID (email address)
   ├─ Tenant ID
   │
   ▼
5. EMBEDDING GENERATION (Agent)
   │
   ├─ Provider: OpenAI / Ollama / Sentence Transformers
   │
   "Convert email text to vector (768-1536 dimensions)"
   │
   ▼
6. VECTOR DATABASE STORAGE
   │
   Store embedding in:
   ├─ Pinecone (cloud) with metadata
   ├─ OR Local FAISS/Qdrant
   │
   ├─ Namespace: {user_id}
   ├─ Metadata: subject, sender, date
   │
   ▼
7. GRAPH DATABASE UPDATE (Neo4j)
   │
   ├─ Create NODE: Email
   ├─ Create RELATIONSHIP: User → Email
   ├─ Create RELATIONSHIP: Email → Thread
   ├─ Track: Email → Sender → Contact Network
   │
   ▼
8. INDEXED & SEARCHABLE ✅
   │
   Email is now ready for:
   ├─ Semantic search
   ├─ RAG queries
   ├─ Summarization
   ├─ Draft generation
```

---

## User Query to Response Flow

```
USER ASKS: "What was the status update on Project X?"

                    ↓

1. USER INTERFACE RECEIVES QUERY
   │
   ├─ Gmail Add-on: User types in sidebar
   ├─ Thunderbird: User types in chat panel
   ├─ Web Dashboard: User types in chat box
   │
   POST /api/query
   {
     "query": "What was the status update on Project X?",
     "user_id": "user@example.com",
     "tenant_id": "tenant-123"
   }
   │
   ▼

2. BACKEND RECEIVES REQUEST
   │
   ├─ Validate JWT token
   ├─ Check rate limit
   ├─ Extract user context
   │
   Forward to Agent:
   POST /api/rag
   │
   ▼

3. AGENT: EMBEDDING QUERY
   │
   ├─ Provider: OpenAI / Ollama / Sentence Transformers
   │
   "Convert query to same vector space as emails"
   │
   ▼

4. AGENT: VECTOR SEARCH
   │
   Query Vector DB:
   │
   ├─ Find top-K similar email vectors
   ├─ Filter by user_id namespace
   ├─ Score by cosine similarity
   │
   RESULT: Top 5 most relevant emails
   │
   ▼

5. AGENT: BUILD CONTEXT FOR LLM
   │
   Retrieve full email content:
   │
   ├─ Email 1: "Project X update: 50% complete"
   ├─ Email 2: "Meeting notes for Project X"
   ├─ Email 3: "Project X milestone achieved"
   ├─ Email 4: "Next steps for Project X"
   ├─ Email 5: "Budget approved for Project X"
   │
   ▼

6. AGENT: LLM GENERATION
   │
   Provider: OpenAI GPT-4 / Anthropic Claude / Ollama Llama
   │
   PROMPT:
   ─────────────────────────────
   You are an email assistant.
   
   Based on these emails:
   [Email 1 content]
   [Email 2 content]
   ...
   
   Answer: "What was the status update on Project X?"
   ─────────────────────────────
   │
   ▼

7. LLM GENERATES RESPONSE
   │
   RESPONSE:
   "Based on the emails, Project X is 50% complete.
    Recent updates include:
    - Meeting held to discuss progress
    - Milestone was achieved
    - Budget has been approved for next phase
    - Next steps being finalized"
   │
   ▼

8. RESPONSE SENT TO USER INTERFACE
   │
   POST /api/response
   │
   ├─ Gmail Add-on displays in sidebar
   ├─ Thunderbird displays in chat panel
   ├─ Web Dashboard shows in chat history
   │
   ▼

9. USER READS RESPONSE ✅

```

---

## Component Communication Map

```
┌──────────────────────────────────────────────────────────────┐
│                     FRONTEND LAYER                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │Gmail Add-on │  │Thunderbird  │  │ Web         │          │
│  │             │  │ Extension   │  │ Dashboard   │          │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘          │
└─────────┼─────────────────┼─────────────────┼────────────────┘
          │                 │                 │
          └─────────────────┼─────────────────┘
                            │
                  REST API (HTTPS)
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
┌─────────▼──────┐  ┌───────▼────────┐  ┌────▼──────────┐
│  BACKEND       │  │  AGENT         │  │  THIRD-PARTY  │
│  Express.js    │  │  FastAPI       │  │  SERVICES     │
├────────────────┤  ├────────────────┤  ├───────────────┤
│ • Auth Routes  │  │ • RAG Routes   │  │ • OpenAI API  │
│ • User API     │  │ • Pipeline API │  │ • Anthropic   │
│ • Settings API │  │ • Health Check │  │ • Groq API    │
│ • Proxy Routes │  │ • Settings Mgr │  │ • Pinecone    │
│ • Email API    │  │ • Ingest Svc   │  │ • Neo4j Cloud │
└────────┬───────┘  └────────┬───────┘  └───────────────┘
         │                   │
         └───────────┬───────┘
                     │
         ┌───────────┴────────────┐
         │                        │
    ┌────▼────┐  ┌─────────┐ ┌────▼─────┐
    │ MongoDB │  │  Neo4j  │ │ Pinecone  │
    │ (Local) │  │ (Cloud) │ │ (Cloud)   │
    └─────────┘  └─────────┘ └───────────┘
         │
    User Data
    Settings
    Metadata
```

---

## Deployment Options

### Option 1: Cloud (openmailbot.com)

```
                    User
                     │
                     │ HTTPS
                     ▼
        ┌────────────────────────┐
        │  openmailbot.com       │
        │  (Production Servers)  │
        ├────────────────────────┤
        │ • Frontend: Next.js    │
        │ • Backend: Express.js  │
        │ • Agent: FastAPI       │
        │ • DB: MongoDB Atlas    │
        │ • Vector: Pinecone     │
        │ • Graph: Neo4j Aura    │
        └────────────────────────┘
        
        Advantages:
        ✅ Zero setup
        ✅ Always available
        ✅ No infrastructure costs
        ✅ Automatic backups
        
        Disadvantages:
        ⚠️ Data sent to cloud
        ⚠️ Requires internet
        ⚠️ Monthly subscription
```

### Option 2: Self-Hosted (Docker)

```
        Your Server (Cloud or On-Prem)
                    │
    ┌───────────────┴───────────────┐
    │                               │
    ▼                               ▼
  Docker                         Docker
  Container                      Container
  ┌─────────────┐              ┌─────────────┐
  │ Backend     │◄────────────►│ Agent       │
  │ + Frontend  │              │ + Services  │
  └─────────────┘              └─────────────┘
         │                           │
         └───────────────┬───────────┘
                         │
         ┌───────────────┴───────────────┐
         │                               │
         ▼                               ▼
      Docker                         Docker
      Volume                         Volume
    ┌─────────────┐              ┌─────────────┐
    │ MongoDB     │              │ Neo4j       │
    │ Local DB    │              │ Graph DB    │
    └─────────────┘              └─────────────┘
    
    Advantages:
    ✅ Full control
    ✅ Data stays on your server
    ✅ No subscription fees
    ✅ Can work offline
    
    Disadvantages:
    ⚠️ Need to manage server
    ⚠️ Requires infrastructure knowledge
    ⚠️ Manual backups & updates
```

### Option 3: Local Development (Your Computer)

```
    Your Computer
         │
    ┌────┴─────────────────────────┐
    │                              │
    ▼                              ▼
Terminal 1                    Terminal 2-4
    │                              │
    ├─ Backend                     ├─ Agent
    │  :3000                       │  :5051
    │                              │
    │                          ┌───┴────────┐
    │                          │            │
    │                      Terminal 3   Terminal 4
    │                          │            │
    │                      Frontend     Ollama
    │                        :3000       :11434
    │
    └──────────────────────────┬───────────────┘
                               │
    ┌──────────────────────────┴───────────────────┐
    │                                              │
    ▼                                              ▼
Local Files                                  Ollama Local Models
├─ MongoDB                                   ├─ llama2
├─ data/                                     ├─ nomic-embed-text
└─ Vector indexes (FAISS)                    └─ (No cloud needed)

    Advantages:
    ✅ Completely free
    ✅ Works offline
    ✅ Fast for testing
    ✅ No data leaves computer
    
    Disadvantages:
    ⚠️ 5+ terminal windows
    ⚠️ Manual startup each time
    ⚠️ Not suitable for production
```

---

## Authentication Flow

```
1. USER LOGS IN
   │
   ├─ Gmail: Google OAuth popup
   ├─ Thunderbird: Manual setup of API key
   ├─ Web Dashboard: Google OAuth or email/password
   │
   ▼

2. BACKEND VALIDATES
   │
   ├─ Check Google OAuth token (if using Google)
   ├─ Verify API key (if using API auth)
   ├─ Create JWT token
   │
   ▼

3. JWT TOKEN ISSUED
   │
   Token = {
     "user_id": "user@example.com",
     "tenant_id": "tenant-123",
     "exp": 1234567890
   }
   │
   ▼

4. FRONTEND STORES TOKEN
   │
   ├─ Gmail Add-on: browser.storage.local
   ├─ Thunderbird: Extension storage
   ├─ Web Dashboard: localStorage or cookie
   │
   ▼

5. ALL REQUESTS INCLUDE TOKEN
   │
   Authorization: Bearer {JWT_TOKEN}
   │
   ▼

6. BACKEND VALIDATES EVERY REQUEST
   │
   ├─ Check token signature
   ├─ Check expiration
   ├─ Check user permissions
   ├─ Proceed if valid, reject if invalid
```

---

## Settings Synchronization

```
User Updates Settings in:
┌─ Gmail Add-on UI
├─ Thunderbird Extension
└─ Web Dashboard

          ▼

POST /api/settings
{
  "user_id": "user@example.com",
  "llm_provider": "openai",
  "llm_model": "gpt-4o",
  "embedding_provider": "openai",
  "vector_db": "pinecone"
}

          ▼

BACKEND PROCESSES
├─ Validate settings
├─ Store in MongoDB
├─ Broadcast to Agent

          ▼

AGENT UPDATES
├─ Reload settings from DB
├─ Apply to next query
├─ All pipelines use updated config

          ▼

FRONTEND UPDATES
├─ Settings saved confirmation
├─ UI reflects new values
└─ Ready for next operation
```

---

## Service Port Reference

```
┌──────────────────────────┬──────────────┬────────────────────────┐
│ Service                  │ Port         │ Purpose                │
├──────────────────────────┼──────────────┼────────────────────────┤
│ Frontend (Next.js)       │ 3000         │ Web Dashboard UI       │
│ Backend (Express.js)     │ 3000 (prod)  │ REST API Endpoints     │
│ Agent (FastAPI)          │ 5051         │ AI Processing API      │
│ MongoDB                  │ 27017        │ Database               │
│ Neo4j                    │ 7687 (bolt)  │ Graph Database         │
│ Neo4j Browser            │ 7474         │ Web Interface for Graph│
│ Ollama                   │ 11434        │ Local LLM              │
│ Redis (optional)         │ 6379         │ Caching                │
└──────────────────────────┴──────────────┴────────────────────────┘

Note: These are defaults, can be changed in .env
```

---

## Performance & Scaling Considerations

### Bottlenecks

```
1. EMBEDDING GENERATION
   Problem: Time-consuming (1-5 seconds per email)
   Solution: Batch processing, use faster model, GPU

2. VECTOR SIMILARITY SEARCH
   Problem: Large vector DB can be slow
   Solution: Use Pinecone (indexed), implement filtering

3. LLM RESPONSE TIME
   Problem: API latency (5-30 seconds)
   Solution: Local Ollama, model selection, caching

4. DATABASE QUERIES
   Problem: Slow MongoDB queries on large datasets
   Solution: Indexing, query optimization, data archival
```

### Optimization Tips

```
✅ Use NVIDIA GPU for embeddings (10x faster)
✅ Batch process emails during off-hours
✅ Use smaller LLM models for faster responses
✅ Implement caching for frequent queries
✅ Archive old emails to reduce query scope
✅ Use read replicas for MongoDB
✅ Monitor agent performance with metrics
```

---

## Troubleshooting Guide

### Service Won't Start

```
╔═══════════════════════════════════════╗
║ Backend won't start?                  ║
╚═══════════════════════════════════════╝

Check:
1. Port 3000 already in use?
   → Kill process or use different port

2. Node.js not installed?
   → node --version (must be 18+)

3. npm packages missing?
   → npm install

4. Environment variables?
   → Check .env file exists
   → Check MONGODB_URI is valid
```

### Database Connection Fails

```
╔═══════════════════════════════════════╗
║ MongoDB not connecting?               ║
╚═══════════════════════════════════════╝

Check:
1. MongoDB running?
   → mongod (local) or Docker running

2. Connection string correct?
   → mongosh <connection_string>

3. Credentials valid?
   → username/password in .env

4. Network accessible?
   → telnet localhost 27017
```

### API Integration Issues

```
╔═══════════════════════════════════════╗
║ OpenAI/Anthropic/etc. API fails?      ║
╚═══════════════════════════════════════╝

Check:
1. API key valid?
   → Test on provider's website

2. Whitespace in key?
   → Copy again carefully

3. Correct provider type?
   → LLM vs Embedding

4. Rate limit hit?
   → Wait or upgrade plan

5. Model exists for provider?
   → Check available models
```

---

## Next Steps for Integration

1. **Choose Deployment Option**
   - Cloud (easiest)
   - Self-hosted (control)
   - Local dev (testing)

2. **Configure Databases**
   - MongoDB for persistence
   - Neo4j for relationships
   - Pinecone for vectors

3. **Setup LLM Provider**
   - OpenAI, Anthropic, Groq, or Ollama

4. **Deploy Frontend**
   - Gmail Add-on or Thunderbird Extension

5. **Test & Iterate**
   - Verify each component
   - Adjust settings
   - Monitor performance

---

**For detailed setup instructions, see:** [COMPLETE_SETUP_GUIDE.md](COMPLETE_SETUP_GUIDE.md)  
**For quick reference:** [QUICK_START_CHEAT_SHEET.md](QUICK_START_CHEAT_SHEET.md)
