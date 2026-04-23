# OpenMailBot — Complete Architecture, Data Flow & Process Documentation

> **Generated:** March 8, 2026  
> **Scope:** Full system — Backend, Agent, Inbuilt services, LLM providers, Vector DB, Graph DB

---

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [Component Inventory](#2-component-inventory)
3. [Backend → Agent Data Flow](#3-backend--agent-data-flow)
4. [Agent Internal Architecture](#4-agent-internal-architecture)
5. [LLM Service — Multi-Provider Routing](#5-llm-service--multi-provider-routing)
6. [Inbuilt Mode — Zero-Config Path](#6-inbuilt-mode--zero-config-path)
7. [Embedding & Vector DB Flow](#7-embedding--vector-db-flow)
8. [Data Flow Diagrams](#8-data-flow-diagrams)
9. [Activity Diagrams](#9-activity-diagrams)
10. [Process Flow Diagrams](#10-process-flow-diagrams)
11. [Data Objects Reference](#11-data-objects-reference)
12. [Storage Architecture](#12-storage-architecture)
13. [Observations & Notes](#13-observations--notes)

---

## 1. System Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           CLIENT LAYER                                       │
│                                                                              │
│   ┌───────────┐   ┌───────────────┐   ┌──────────────┐   ┌──────────────┐  │
│   │  Frontend  │   │ Gmail Add-on  │   │  Thunderbird │   │ Zoho Add-on  │  │
│   │  (React)   │   │ (Apps Script) │   │  Extension   │   │  Extension   │  │
│   └─────┬─────┘   └──────┬────────┘   └──────┬───────┘   └──────┬───────┘  │
│         │                │                    │                  │           │
└─────────┼────────────────┼────────────────────┼──────────────────┼───────────┘
          │                │                    │                  │
          ▼                ▼                    ▼                  ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                     BACKEND (Node.js / Express :3000)                        │
│                                                                              │
│   ┌───────────┐   ┌──────────────┐   ┌────────────┐   ┌─────────────────┐  │
│   │  Auth &    │   │  Controllers │   │  Middleware │   │  Models         │  │
│   │  Passport  │   │  (addOn,chat │   │  (auth.js)  │   │  (User,Email   │  │
│   │            │   │   draft,slack)│   │             │   │   Metadata)    │  │
│   └───────────┘   └──────┬───────┘   └────────────┘   └─────────────────┘  │
│                          │                                                    │
│                 axios HTTP calls to AGENT_API_URL                             │
└──────────────────┬───────────────────────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                     AGENT (Python / FastAPI :8000)                            │
│                                                                              │
│   ┌──────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│   │  main.py │  │  Pipelines   │  │  Services    │  │  Storage          │  │
│   │ endpoints│  │  (chat,draft │  │  (llm,embed, │  │  (SQLite,ChromaDB │  │
│   │          │  │   label,store)│  │   inbuilt)   │  │   Neo4j, Disk)    │  │
│   └──────────┘  └──────────────┘  └──────┬───────┘  └───────────────────┘  │
│                                          │                                    │
└──────────────────────────────────────────┼───────────────────────────────────┘
                                           │
              ┌────────────────────────────┼──────────────────────┐
              │                            │                      │
              ▼                            ▼                      ▼
┌──────────────────┐   ┌──────────────────────┐   ┌────────────────────────┐
│   LLM Providers  │   │  Embedding Providers  │   │    Vector Databases    │
│                  │   │                        │   │                        │
│  • OpenAI        │   │  • OpenAI Embeddings   │   │  • ChromaDB (local)    │
│  • Anthropic     │   │  • Nomic               │   │  • Pinecone (cloud)    │
│  • Google Gemini │   │  • Google Gemini       │   │  • Weaviate            │
│  • Ollama (local)│   │  • Sentence-Transform. │   │  • Inbuilt (Chroma)    │
│  • Inbuilt/Flask │   │  • Inbuilt/Flask       │   │                        │
└──────────────────┘   └──────────────────────┘   └────────────────────────┘
```

---

## 2. Component Inventory

### Backend (Node.js)

| File | Purpose |
|------|---------|
| `backend/server.js` | Express server, route registration, MongoDB connection |
| `backend/controllers/chatController.js` | Proxies chat requests to Agent `/api/chat-with-thread` |
| `backend/controllers/draftController.js` | Proxies draft requests to Agent `/api/draft-with-attachments` |
| `backend/controllers/addOnController.js` | Proxies summarize, reply, query, related-threads to Agent |
| `backend/controllers/slackController.js` | Slack integration controller |
| `backend/routes/chat.js` | Chat route definitions (`/thread`, `/search`, `/health`) |
| `backend/routes/draft.js` | Draft route definitions |
| `backend/routes/emails.js` | Email metadata routes |
| `backend/routes/settings.js` | User settings routes |
| `backend/middleware/auth.js` | Authentication middleware |
| `backend/models/User.js` | MongoDB User model |
| `backend/models/EmailMetadata.js` | MongoDB EmailMetadata model |

### Agent (Python / FastAPI)

| File | Purpose |
|------|---------|
| `agent/main.py` | FastAPI app, all REST endpoints, request models |
| `agent/config.py` | Pydantic Settings with provider defaults |
| `agent/utils.py` | Inbuilt mode functions: `call_chat_api`, `call_embed_api`, `ollama_generate_chat` |
| `agent/services/chat_pipeline.py` | `ChatWithThreadPipeline` — RAG chat with email threads |
| `agent/services/draft_pipeline.py` | `DraftPipeline` — draft generation with attachment context |
| `agent/services/label_pipeline.py` | `EmailLabelPipeline` — rule-based + LLM email labeling |
| `agent/services/store_pipeline.py` | `CheckAndStoreEmailPipeline`, `CheckAndStoreAttachmentsPipeline` |
| `agent/services/preprocessing_emails.py` | `EmailPreprocessingPipeline` — HTML cleaning, dedup |
| `agent/services/llm.py` | `LLMService` — multi-provider LLM dispatcher |
| `agent/services/embeddings.py` | `EmbeddingService` — multi-provider embedding + vector storage |
| `agent/services/inbuilt.py` | `InbuiltLLMService`, `InbuiltEmbeddingService`, `InbuiltVectorClient` |
| `agent/services/settings_manager.py` | `SettingsManager` — encrypted SQLite settings storage |
| `agent/services/store_graph_pipeline.py` | `StoreGraphPipeline` — Neo4j graph storage |
| `agent/services/label_email_lockbook.py` | Metric tracking for labeling operations |
| `agent/services/ollama_lable_pipline.py` | Ollama-based label pipeline (alternative) |
| `agent/vector/__init__.py` | `get_vector_client()` factory |
| `agent/vector/chroma_client.py` | ChromaDB client implementation |
| `agent/vector/pinecone_client.py` | Pinecone client implementation |
| `agent/vector/weaviate_client.py` | Weaviate client implementation |
| `agent/graph/agent.py` | Neo4j graph operations (create nodes, link) |
| `agent/prompt/prompt.py` | System prompts and prompt templates |

---

## 3. Backend → Agent Data Flow

The Backend acts as an authentication and enrichment proxy. All AI processing is delegated to the Agent via HTTP.

### Route Mapping Table

| Backend Controller | Backend Route | Agent Endpoint | Agent Pipeline / Service |
|---|---|---|---|
| `chatController.chatWithThread` | `POST /api/chat/thread` | `POST /api/chat-with-thread` | `ChatWithThreadPipeline.process_and_chat()` |
| `chatController.searchThread` | `POST /api/chat/search` | `POST /api/chat-with-thread` | `ChatWithThreadPipeline.process_and_chat()` |
| `draftController.draftWithAttachments` | `POST /api/draft/with-attachments` | `POST /api/draft-with-attachments` | `DraftPipeline.process_email_request()` |
| `addOnController.summarize` | `POST /api/summarize` | `POST /api/summarize` | `LLMService.summarize()` |
| `addOnController.generateReply` | `POST /api/generate-reply` | `POST /api/generate-reply` | `LLMService.generate_reply()` |
| `addOnController.handleQuery` | `POST /api/query` | `POST /api/rag` | `RAGService.query()` |
| `addOnController.getRelatedThreads` | `POST /api/related-threads` | `POST /api/related-threads` | Vector similarity search |
| Direct agent call | — | `POST /api/log-email` | Disk storage + deduplication |
| Direct agent call | — | `POST /api/label-email` | Full pipeline: preprocess → embed → label → graph |
| Direct agent call | — | `POST /api/store-attachments` | Disk storage of base64 attachments |
| Direct agent call | — | `POST /api/settings` | `SettingsManager` encrypted storage |

### Backend → Agent Data Enrichment

```
Frontend Request                   Backend Processing                 Agent Request
─────────────────                  ────────────────────               ──────────────
{ userId,                    →     1. User.findOne({email})     →    { user_id,
  threadId,                        2. Fetch tenantId                   thread_id,
  question }                       3. Fetch EmailMetadata              question }
                                   4. axios.post(AGENT_API_URL)

{ userId,                    →     1. Verify user exists         →    { user_id,
  emailId,                         2. Get email from MongoDB           thread_id,
  tone }                           3. Get thread context               user_preferences }
                                   4. axios.post(AGENT_API_URL)
```

---

## 4. Agent Internal Architecture

### Settings Resolution Chain

```
┌─────────────────────────────────────────────────────────────┐
│                   Settings Priority Order                     │
│                                                               │
│   1. effective_settings (per-user, from encrypted SQLite)     │
│      ↳ SettingsManager(user_id).get_settings()               │
│      ↳ Stored encrypted with PBKDF2 + Fernet                │
│                                                               │
│   2. Environment variables (tenant-level)                     │
│      ↳ .env file or docker environment                       │
│                                                               │
│   3. config.py hardcoded defaults                            │
│      ↳ LLM_PROVIDER = "inbuilt"                             │
│      ↳ EMBEDDING_PROVIDER = "inbuilt"                        │
│      ↳ VECTOR_PROVIDER = "inbuilt"                           │
└─────────────────────────────────────────────────────────────┘
```

### Pipeline Initialization Pattern

Every pipeline follows the same initialization:
```python
Pipeline(user_id)
  ├→ SettingsManager(user_id).get_settings()   # load encrypted per-user settings
  ├→ LLMService(effective_settings)            # configure LLM provider
  ├→ EmbeddingService(effective_settings)      # configure embedding + vector DB
  └→ Setup per-user SQLite DB                  # tracking tables
```

---

## 5. LLM Service — Multi-Provider Routing

`services/llm.py` → `LLMService` is the central dispatcher for all LLM calls.

### Provider Routing Diagram

```mermaid
flowchart TD
    A[LLMService.generate] --> B{provider?}
    
    B -->|openai| C{model starts with gpt-5?}
    C -->|Yes| D["_call_openai_responses()<br/>POST /v1/responses"]
    C -->|No| E["_call_openai()<br/>openai.chat.completions.create()"]
    
    B -->|anthropic| F["_call_anthropic()<br/>anthropic.messages.create()"]
    
    B -->|gemini| G["_call_gemini()<br/>genai.GenerativeModel()"]
    
    B -->|ollama| H["_call_ollama()<br/>POST localhost:11434/api/chat"]
    
    B -->|inbuilt| I["_call_inbuilt()<br/>→ utils.call_chat_api()"]
    I --> J["POST {FLASK_URL}/chat"]
    
    D --> K[Return response text]
    E --> K
    F --> K
    G --> K
    H --> K
    J --> K
```

### LLM Service Methods

| Method | Purpose | Used By |
|--------|---------|---------|
| `generate(messages, provider, model)` | Main dispatch — routes to correct provider | All pipelines |
| `summarize(content, user_id, tenant_id)` | Summarize email thread | `/api/summarize` endpoint |
| `generate_reply(email_content, ...)` | Generate context-aware reply | `/api/generate-reply` endpoint |
| `analyze_sentiment(text)` | Sentiment analysis | `/api/analyze-sentiment` endpoint |

---

## 6. Inbuilt Mode — Zero-Config Path

For tenants without their own API keys, "inbuilt" mode uses centrally hosted services.

### Inbuilt Service Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        INBUILT MODE                                  │
│                                                                      │
│   ┌─────────────────┐          ┌─────────────────────────────┐      │
│   │ InbuiltLLMService│    →    │ utils.call_chat_api(prompt)  │      │
│   │ (inbuilt.py)     │         │    POST {FLASK_URL}/chat     │      │
│   └─────────────────┘          └──────────────┬──────────────┘      │
│                                                │                     │
│   ┌──────────────────────┐     ┌──────────────▼──────────────┐      │
│   │InbuiltEmbeddingService│ →  │ utils.call_embed_api(text)   │      │
│   │ (inbuilt.py)          │    │    POST {FLASK_URL}/embed    │      │
│   └──────────────────────┘     └──────────────┬──────────────┘      │
│                                                │                     │
│   ┌──────────────────────┐     ┌──────────────▼──────────────┐      │
│   │ InbuiltVectorClient  │  →  │ ChromaDBClient(inbuilt=True) │      │
│   │ (inbuilt.py)          │    │ Uses INBUILT_CHROMA_URL      │      │
│   └──────────────────────┘     └─────────────────────────────┘      │
│                                                                      │
│                     Central Flask Server                              │
│              ┌──────────────────────────────┐                        │
│              │   Flask + Ollama Wrapper      │                        │
│              │   /chat  → Ollama LLM         │                        │
│              │   /embed → Embedding model    │                        │
│              │                               │                        │
│              │   FLASK_URL (configurable)     │                        │
│              └──────────────────────────────┘                        │
└─────────────────────────────────────────────────────────────────────┘
```

### utils.py Function Reference

| Function | Endpoint | Purpose |
|----------|----------|---------|
| `call_chat_api(prompt)` | `POST {FLASK_URL}/chat` | LLM text generation via Flask/Ollama |
| `call_embed_api(text)` | `POST {FLASK_URL}/embed` | Embedding generation via Flask server |
| `ollama_generate_chat(prompt, model)` | `POST {OLLAMA_URL}/api/generate` | Direct Ollama access |
| `openai_generate_chat(prompt, comment)` | `POST api.openai.com/v1/responses` | OpenAI gpt-5-mini (Responses API) |

---

## 7. Embedding & Vector DB Flow

### Embedding Provider Routing

```mermaid
flowchart TD
    A[EmbeddingService.generate_embedding] --> B{provider?}
    
    B -->|openai| C["openai.embeddings.create()<br/>model: text-embedding-ada-002"]
    B -->|nomic| D["nomic SDK<br/>model: nomic-embed-text-v1.5"]
    B -->|gemini| E["genai.embed_content()<br/>model: embedding-001"]
    B -->|sentence-transformers| F["SentenceTransformer.encode()<br/>model: all-MiniLM-L6-v2"]
    B -->|inbuilt| G["utils.call_embed_api()<br/>POST {FLASK_URL}/embed"]
    
    C --> H["List[float] embedding"]
    D --> H
    E --> H
    F --> H
    G --> H
```

### Vector DB Factory

```mermaid
flowchart TD
    A["get_vector_client(provider, settings)"] --> B{provider?}
    
    B -->|pinecone| C[PineconeClient]
    B -->|chroma| D["ChromaDBClient<br/>(per-user persistent)"]
    B -->|weaviate| E[WeaviateClient]
    B -->|inbuilt| F["ChromaDBClient<br/>(inbuilt_mode=True)"]
    
    C --> G[BaseVectorStore interface]
    D --> G
    E --> G
    F --> G
    
    G --> H["upsert(id, embedding, metadata, namespace)"]
    G --> I["query(embedding, namespace, limit, filter)"]
    G --> J["delete(id, namespace)"]
```

---

## 8. Data Flow Diagrams

### 8.1 Level 0 — Context Diagram

```mermaid
flowchart LR
    User((User)) -->|"Email actions<br/>(chat, draft, label)"| System[OpenMailBot System]
    System -->|"Responses<br/>(answers, drafts, labels)"| User
    
    Gmail[Gmail API] -->|"Email data,<br/>thread data"| System
    System -->|"Apply labels,<br/>send drafts"| Gmail
    
    LLM[LLM Providers] -->|"AI responses"| System
    System -->|"Prompts & context"| LLM
    
    VectorDB[(Vector DB)] -->|"Similar documents"| System
    System -->|"Embeddings"| VectorDB
```

### 8.2 Level 1 — System Data Flow

```mermaid
flowchart TB
    subgraph Clients["Client Layer"]
        FE[Frontend/Add-ons]
    end
    
    subgraph Backend["Backend (Node.js :3000)"]
        AUTH[Auth Middleware]
        CTRL[Controllers]
        MONGO[(MongoDB)]
    end
    
    subgraph Agent["Agent (Python :8000)"]
        EP[FastAPI Endpoints]
        SETTINGS[Settings Manager]
        
        subgraph Pipelines
            CHAT[Chat Pipeline]
            DRAFT[Draft Pipeline]
            LABEL[Label Pipeline]
            STORE[Store Pipeline]
            PREPROC[Preprocessing]
        end
        
        subgraph Services
            LLM_SVC[LLM Service]
            EMBED_SVC[Embedding Service]
            INBUILT[Inbuilt Service]
        end
        
        subgraph Storage
            SQLITE[(Per-user SQLite)]
            CHROMA[(ChromaDB)]
            NEO4J[(Neo4j)]
            DISK[(Disk: JSON/files)]
        end
    end
    
    subgraph External["External Providers"]
        OPENAI[OpenAI API]
        ANTHROPIC[Anthropic API]
        GEMINI[Google Gemini]
        OLLAMA[Ollama Server]
        FLASK_SVC[Inbuilt Flask Server]
    end
    
    FE -->|HTTP| AUTH
    AUTH --> CTRL
    CTRL -->|Read/Write| MONGO
    CTRL -->|axios HTTP| EP
    
    EP --> SETTINGS
    EP --> CHAT
    EP --> DRAFT
    EP --> LABEL
    EP --> STORE
    EP --> PREPROC
    
    CHAT --> LLM_SVC
    CHAT --> EMBED_SVC
    DRAFT --> LLM_SVC
    DRAFT --> EMBED_SVC
    LABEL --> LLM_SVC
    STORE --> EMBED_SVC
    
    LLM_SVC --> OPENAI
    LLM_SVC --> ANTHROPIC
    LLM_SVC --> GEMINI
    LLM_SVC --> OLLAMA
    LLM_SVC --> INBUILT
    INBUILT --> FLASK_SVC
    
    EMBED_SVC --> CHROMA
    SETTINGS --> SQLITE
    CHAT --> SQLITE
    LABEL --> NEO4J
    PREPROC --> DISK
```

### 8.3 Level 2 — Chat Pipeline Data Flow

```mermaid
flowchart TB
    REQ["POST /api/chat-with-thread<br/>{user_id, thread_id, question}"]
    
    REQ --> JOB["Create background job<br/>Return job_id immediately"]
    JOB --> INIT["ChatWithThreadPipeline(user_id)<br/>Load settings, init LLM + Embedding"]
    
    INIT --> LOAD["Load thread from disk<br/>data/{user_id}/log_emails/{thread_id}/"]
    LOAD --> UNPROC["Filter unprocessed messages<br/>(check per-user SQLite)"]
    
    UNPROC --> EMBED_EMAIL["For each unprocessed message:<br/>1. Generate embedding<br/>2. Store in ChromaDB<br/>3. Mark processed in SQLite"]
    
    UNPROC --> EMBED_ATT["For each unprocessed attachment:<br/>1. Extract text (PDF/CSV/PPTX)<br/>2. Chunk content<br/>3. Generate embeddings<br/>4. Store in ChromaDB"]
    
    EMBED_EMAIL --> HYBRID["Hybrid Chat"]
    EMBED_ATT --> HYBRID
    
    HYBRID --> TOOL_CALL{"Provider?"}
    TOOL_CALL -->|inbuilt| OPENAI_TC["OpenAI tool calling<br/>(gpt-5-mini)<br/>Decides: search_emails / search_attachments"]
    TOOL_CALL -->|other| LLM_TC["LLMService tool selection<br/>(text-based prompt)"]
    
    OPENAI_TC --> SEARCH["Execute semantic search<br/>on ChromaDB"]
    LLM_TC --> SEARCH
    
    SEARCH --> CONTEXT["Combine retrieved context<br/>(email results + attachment results)"]
    
    CONTEXT --> ANSWER{"Provider?"}
    ANSWER -->|inbuilt| OLLAMA_ANS["Ollama generates final answer<br/>(via Flask /chat)"]
    ANSWER -->|other| LLM_ANS["LLMService.generate()<br/>(configured provider)"]
    
    OLLAMA_ANS --> RESP["Return {success, answer, processing_info}"]
    LLM_ANS --> RESP
    
    RESP --> POLL["Client polls /api/job-status/{job_id}"]
```

### 8.4 Level 2 — Label Pipeline Data Flow

```mermaid
flowchart TB
    REQ["POST /api/label-email<br/>{user_id, thread_id, messages[]}"]
    
    REQ --> PREPROC["EmailPreprocessingPipeline.process()<br/>- Strip HTML<br/>- Remove URLs/disclaimers<br/>- Extract new content<br/>- Deduplicate nested quotes"]
    
    PREPROC --> SAVE["Save preprocessed JSON<br/>data/{user_id}/log_emails/{thread_id}/"]
    
    SAVE --> EMBED_STORE{"Parallel: asyncio.gather"}
    
    EMBED_STORE --> STORE_EMAIL["CheckAndStoreEmailPipeline.run()<br/>Embed each message → ChromaDB"]
    EMBED_STORE --> STORE_ATT["CheckAndStoreAttachmentsPipeline.run()<br/>Embed attachments → ChromaDB"]
    
    STORE_EMAIL --> LABEL_STEP["EmailLabelPipeline"]
    STORE_ATT --> LABEL_STEP
    
    LABEL_STEP --> RULES{"Rule-based matching?"}
    RULES -->|Match found| RULE_LABEL["Return rule-based label<br/>(bank, airlines, hotels, etc.)"]
    RULES -->|No match| LLM_LABEL["LLM classification<br/>(OpenAI gpt-5-mini structured output)"]
    
    RULE_LABEL --> ENRICH["LLM enrichment<br/>(category, topic, subtopic, subject_matter)"]
    LLM_LABEL --> ENRICH
    
    ENRICH --> GRAPH{"Label eligible for graph?<br/>(response, FYI, Awaiting Reply)"}
    GRAPH -->|Yes| NEO4J["StoreGraphPipeline<br/>Create nodes: Category, Topic, Thread<br/>Create links in Neo4j"]
    GRAPH -->|No| SKIP["Skip graph storage"]
    
    NEO4J --> LOCKBOOK["Log to LockBook<br/>(per-user + global metrics)"]
    SKIP --> LOCKBOOK
    
    LOCKBOOK --> RESP["Return {success, label, category,<br/>topic, subtopic, graph_status}"]
```

### 8.5 Level 2 — Draft Pipeline Data Flow

```mermaid
flowchart TB
    REQ["POST /api/draft-with-attachments<br/>{user_id, thread_id, user_preferences}"]
    
    REQ --> JOB["Create background job<br/>Return job_id immediately"]
    JOB --> INIT["DraftPipeline(user_id)<br/>Load settings, init LLM + Embedding"]
    
    INIT --> LOAD["Load thread JSON<br/>data/{user_id}/log_emails/{thread_id}/"]
    
    LOAD --> ATT_PROC["Process unprocessed attachments<br/>Extract text → Embed → ChromaDB"]
    
    ATT_PROC --> HYBRID["Hybrid Draft Generation"]
    
    HYBRID --> TOOL_CALL{"Provider?"}
    TOOL_CALL -->|inbuilt| OPENAI_TC["OpenAI tool calling<br/>Decides: get_attachments / query_attachments"]
    TOOL_CALL -->|other| LLM_TC["LLMService tool selection"]
    
    OPENAI_TC --> ATT_SEARCH["Retrieve relevant attachment context<br/>from ChromaDB"]
    LLM_TC --> ATT_SEARCH
    
    ATT_SEARCH --> DRAFT_GEN["LLMService.generate()<br/>System prompt with:<br/>- User name, position, tone<br/>- Email thread data<br/>- Attachment context<br/>- Custom instructions"]
    
    DRAFT_GEN --> RESP["Return {success, draft_content, processing_info}"]
    RESP --> POLL["Client polls /api/job-status/{job_id}"]
```

---

## 9. Activity Diagrams

### 9.1 User Chat Activity

```mermaid
flowchart TD
    START((Start)) --> USER_Q["User asks question<br/>about email thread"]
    
    USER_Q --> FE_SEND["Frontend sends<br/>POST /api/chat/thread"]
    FE_SEND --> BE_AUTH["Backend authenticates user"]
    
    BE_AUTH --> BE_VERIFY{"User exists<br/>in MongoDB?"}
    BE_VERIFY -->|No| ERR_404["Return 404: User not found"]
    BE_VERIFY -->|Yes| BE_FORWARD["Backend forwards to<br/>Agent /api/chat-with-thread"]
    
    BE_FORWARD --> AG_JOB["Agent creates background job"]
    AG_JOB --> AG_RETURN["Return job_id to Backend"]
    AG_RETURN --> FE_POLL["Frontend polls<br/>/api/job-status/{job_id}"]
    
    AG_JOB --> AG_LOAD["Load thread data from disk"]
    AG_LOAD --> AG_CHECK{"Unprocessed<br/>messages exist?"}
    
    AG_CHECK -->|Yes| AG_EMBED["Generate embeddings<br/>Store in ChromaDB"]
    AG_CHECK -->|No| AG_SKIP["Skip embedding step"]
    AG_EMBED --> AG_CHAT["Hybrid chat pipeline"]
    AG_SKIP --> AG_CHAT
    
    AG_CHAT --> AG_TOOL["LLM selects search tools"]
    AG_TOOL --> AG_SEARCH["Semantic search<br/>emails + attachments"]
    AG_SEARCH --> AG_ANSWER["Generate final answer<br/>with retrieved context"]
    
    AG_ANSWER --> AG_DONE["Job status → done"]
    AG_DONE --> FE_RECV["Frontend receives answer"]
    FE_RECV --> DISPLAY["Display answer to user"]
    DISPLAY --> END((End))
    
    ERR_404 --> END
```

### 9.2 Email Labeling Activity

```mermaid
flowchart TD
    START((Start)) --> RECV["Receive email thread<br/>(from Gmail Add-on / Background Monitor)"]
    
    RECV --> PREPROC["Preprocess emails<br/>Clean HTML, remove quotes,<br/>deduplicate content"]
    
    PREPROC --> STORE_JSON["Store preprocessed data<br/>to disk as JSON"]
    
    STORE_JSON --> PARALLEL{"Run in parallel"}
    
    PARALLEL --> EMBED_E["Embed emails → ChromaDB"]
    PARALLEL --> EMBED_A["Embed attachments → ChromaDB"]
    
    EMBED_E --> WAIT["Wait for both"]
    EMBED_A --> WAIT
    
    WAIT --> RULES{"Apply rule-based<br/>classification"}
    
    RULES -->|"Pattern matched<br/>(bank, airlines, hotel, etc.)"| RULE_HIT["Rule-based label found"]
    RULES -->|"No pattern matched"| LLM_CLASS["LLM classification<br/>(gpt-5-mini structured output)"]
    
    RULE_HIT --> ENRICH["Enrich with LLM<br/>(category, topic, subtopic)"]
    LLM_CLASS --> RESULT["Label result ready"]
    ENRICH --> RESULT
    
    RESULT --> GRAPH{"Label in<br/>[response, FYI,<br/>Awaiting Reply]?"}
    
    GRAPH -->|Yes| NEO4J["Store in Neo4j graph<br/>Create/link nodes:<br/>Category → Topic → Thread"]
    GRAPH -->|No| SKIP_G["Skip graph storage"]
    
    NEO4J --> LOG["Log metrics to LockBook"]
    SKIP_G --> LOG
    
    LOG --> GMAIL{"Access token<br/>provided?"}
    GMAIL -->|Yes| PUSH["Push label to Gmail<br/>via REST API"]
    GMAIL -->|No| DONE["Return label result"]
    PUSH --> DONE
    
    DONE --> END((End))
```

### 9.3 Draft Generation Activity

```mermaid
flowchart TD
    START((Start)) --> USER_REQ["User requests draft<br/>for email thread"]
    
    USER_REQ --> FE_SEND["Frontend sends<br/>POST /api/draft/with-attachments"]
    
    FE_SEND --> BE_FWD["Backend verifies user<br/>Forwards to Agent"]
    
    BE_FWD --> AG_JOB["Agent creates background job"]
    AG_JOB --> LOAD["Load thread JSON data"]
    
    LOAD --> ATT_CHECK{"Attachments<br/>to process?"}
    ATT_CHECK -->|Yes| ATT_PROC["Extract text from files<br/>(PDF, CSV, PPTX)<br/>Embed → ChromaDB"]
    ATT_CHECK -->|No| TOOL_PHASE["Tool calling phase"]
    ATT_PROC --> TOOL_PHASE
    
    TOOL_PHASE --> TOOL_DECIDE{"Inbuilt mode?"}
    TOOL_DECIDE -->|Yes| OPENAI_TOOL["OpenAI decides which<br/>attachment tools to call"]
    TOOL_DECIDE -->|No| LLM_TOOL["LLMService decides<br/>tool selection"]
    
    OPENAI_TOOL --> ATT_RETRIEVE["Retrieve relevant<br/>attachment context"]
    LLM_TOOL --> ATT_RETRIEVE
    
    ATT_RETRIEVE --> COMBINE["Combine:<br/>- Email thread data<br/>- Attachment context<br/>- User preferences"]
    
    COMBINE --> GEN["LLMService generates draft<br/>Using system prompt with:<br/>name, position, tone,<br/>custom instructions"]
    
    GEN --> RESULT["Draft content ready"]
    RESULT --> FE_RECV["Frontend receives draft"]
    FE_RECV --> END((End))
```

---

## 10. Process Flow Diagrams

### 10.1 End-to-End Email Processing Flow

```mermaid
flowchart LR
    subgraph Phase1["Phase 1: Email Arrival"]
        A1[Email received in Gmail] --> A2[Gmail Add-on triggers]
        A2 --> A3["POST /api/log-email"]
        A3 --> A4["Clean & store to disk"]
    end
    
    subgraph Phase2["Phase 2: Label & Classify"]
        B1["POST /api/label-email"] --> B2[Preprocess emails]
        B2 --> B3["Embed → Vector DB"]
        B3 --> B4{"Rule match?"}
        B4 -->|Yes| B5[Rule label]
        B4 -->|No| B6[LLM label]
        B5 --> B7[Enrich metadata]
        B6 --> B7
        B7 --> B8["Store in Neo4j graph"]
        B8 --> B9["Push label to Gmail"]
    end
    
    subgraph Phase3["Phase 3: User Interaction"]
        C1["User asks question<br/>or requests draft"] --> C2{"Chat or Draft?"}
        C2 -->|Chat| C3["RAG: search emails<br/>+ attachments"]
        C2 -->|Draft| C4["Retrieve attachment<br/>context"]
        C3 --> C5["LLM generates answer"]
        C4 --> C6["LLM generates draft"]
    end
    
    Phase1 --> Phase2
    Phase2 --> Phase3
```

### 10.2 LLM Provider Selection Process

```mermaid
flowchart TB
    START["Incoming LLM request"] --> SETTINGS["Load user settings<br/>(SettingsManager)"]
    
    SETTINGS --> CHECK{"effective_settings<br/>has llm_provider?"}
    CHECK -->|Yes| USER_PROV["Use user's provider"]
    CHECK -->|No| ENV{"Environment<br/>variable set?"}
    ENV -->|Yes| ENV_PROV["Use env provider"]
    ENV -->|No| DEFAULT["Use default: 'inbuilt'"]
    
    USER_PROV --> ROUTE["Route to provider"]
    ENV_PROV --> ROUTE
    DEFAULT --> ROUTE
    
    ROUTE --> OPENAI_CHECK{"Provider == openai?"}
    OPENAI_CHECK -->|Yes| MODEL_CHECK{"Model starts<br/>with gpt-5?"}
    MODEL_CHECK -->|Yes| RESPONSES["Use Responses API<br/>/v1/responses"]
    MODEL_CHECK -->|No| COMPLETIONS["Use Chat Completions<br/>/v1/chat/completions"]
    
    OPENAI_CHECK -->|No| OTHER{"Provider?"}
    OTHER -->|anthropic| CLAUDE["Anthropic Claude API"]
    OTHER -->|gemini| GEMINI_API["Google Gemini API"]
    OTHER -->|ollama| OLLAMA_API["Ollama local API"]
    OTHER -->|inbuilt| INBUILT_API["utils.call_chat_api()<br/>→ Flask /chat"]
    
    RESPONSES --> RESULT["Return response text"]
    COMPLETIONS --> RESULT
    CLAUDE --> RESULT
    GEMINI_API --> RESULT
    OLLAMA_API --> RESULT
    INBUILT_API --> RESULT
```

### 10.3 Vector Embedding & Storage Process

```mermaid
flowchart TB
    START["New email/attachment content"] --> PREP["Prepare text for embedding"]
    
    PREP --> EMBED_PROV{"Embedding<br/>provider?"}
    
    EMBED_PROV -->|openai| E1["openai.embeddings.create()"]
    EMBED_PROV -->|nomic| E2["nomic SDK"]
    EMBED_PROV -->|gemini| E3["genai.embed_content()"]
    EMBED_PROV -->|sentence-transformers| E4["SentenceTransformer.encode()"]
    EMBED_PROV -->|inbuilt| E5["POST {FLASK_URL}/embed"]
    
    E1 --> VECTOR["List[float] embedding"]
    E2 --> VECTOR
    E3 --> VECTOR
    E4 --> VECTOR
    E5 --> VECTOR
    
    VECTOR --> META["Prepare metadata<br/>{thread_id, message_id, type,<br/>subject, from, document}"]
    
    META --> VDB_PROV{"Vector DB<br/>provider?"}
    
    VDB_PROV -->|chroma| V1["ChromaDB<br/>Persistent per-user:<br/>data/{user_id}/vector_db/"]
    VDB_PROV -->|pinecone| V2["Pinecone<br/>Cloud-hosted"]
    VDB_PROV -->|weaviate| V3["Weaviate<br/>HTTP client"]
    VDB_PROV -->|inbuilt| V4["ChromaDB<br/>(inbuilt mode)"]
    
    V1 --> TRACK["Mark as processed<br/>in per-user SQLite"]
    V2 --> TRACK
    V3 --> TRACK
    V4 --> TRACK
```

### 10.4 Background Job Lifecycle

```mermaid
sequenceDiagram
    participant Client
    participant Backend
    participant Agent
    participant JobStore
    participant Pipeline
    
    Client->>Backend: POST /api/chat/thread
    Backend->>Agent: POST /api/chat-with-thread
    Agent->>JobStore: Create job (status: pending)
    Agent-->>Backend: {job_id, status: "pending"}
    Backend-->>Client: {job_id, status: "pending"}
    
    Agent->>Pipeline: Start background task
    Agent->>JobStore: Update (status: processing)
    
    loop Poll every 2-3 seconds
        Client->>Backend: GET /api/chat/job-status/{job_id}
        Backend->>Agent: GET /api/job-status/{job_id}
        Agent->>JobStore: Check status
        JobStore-->>Agent: {status: "processing"}
        Agent-->>Backend: {status: "processing"}
        Backend-->>Client: {status: "processing"}
    end
    
    Pipeline-->>Agent: Processing complete
    Agent->>JobStore: Update (status: done, result: {...})
    
    Client->>Backend: GET /api/chat/job-status/{job_id}
    Backend->>Agent: GET /api/job-status/{job_id}
    Agent->>JobStore: Check status
    JobStore-->>Agent: {status: "done", result: {...}}
    Agent-->>Backend: {status: "done", result: {...}}
    Backend-->>Client: {status: "done", answer: "..."}
```

### 10.5 Hybrid Chat RAG Process (Detailed)

```mermaid
sequenceDiagram
    participant User
    participant ChatPipeline
    participant SQLite
    participant EmbeddingService
    participant ChromaDB
    participant OpenAI_TC as OpenAI (Tool Calling)
    participant LLM as LLM (Final Answer)
    
    User->>ChatPipeline: process_and_chat(user_id, thread_id, question)
    
    Note over ChatPipeline: Phase 1: Embed unprocessed data
    ChatPipeline->>SQLite: Get processed message IDs
    SQLite-->>ChatPipeline: Set of processed IDs
    ChatPipeline->>ChatPipeline: Filter unprocessed messages
    
    loop For each unprocessed message
        ChatPipeline->>EmbeddingService: generate_embedding(text)
        EmbeddingService-->>ChatPipeline: embedding vector
        ChatPipeline->>ChromaDB: Store (id, embedding, metadata)
        ChatPipeline->>SQLite: Mark as processed
    end
    
    loop For each unprocessed attachment
        ChatPipeline->>ChatPipeline: Extract text (PDF/CSV/PPTX)
        loop For each chunk
            ChatPipeline->>EmbeddingService: generate_embedding(chunk)
            EmbeddingService-->>ChatPipeline: embedding vector
            ChatPipeline->>ChromaDB: Store (id, embedding, metadata)
        end
        ChatPipeline->>SQLite: Mark attachment processed
    end
    
    Note over ChatPipeline: Phase 2: Tool calling
    ChatPipeline->>OpenAI_TC: Bind tools + user question
    OpenAI_TC-->>ChatPipeline: Tool calls [search_emails, search_attachments]
    
    Note over ChatPipeline: Phase 3: Semantic search
    loop For each tool call
        ChatPipeline->>EmbeddingService: generate_embedding(query)
        EmbeddingService-->>ChatPipeline: query embedding
        ChatPipeline->>ChromaDB: Query(embedding, filter, limit)
        ChromaDB-->>ChatPipeline: Ranked results with metadata
    end
    
    Note over ChatPipeline: Phase 4: Generate answer
    ChatPipeline->>LLM: System prompt + user question + retrieved context
    LLM-->>ChatPipeline: Final answer
    ChatPipeline-->>User: {success, answer, processing_info}
```

---

## 11. Data Objects Reference

### Request/Response Shapes

| Boundary | Direction | Shape |
|----------|-----------|-------|
| Frontend → Backend | Request | `{ user_id, thread_id, question }` |
| Backend → Agent | Request | `{ user_id, thread_id, question }` (enriched) |
| Agent → Pipeline | Internal | Pydantic: `ChatWithThreadRequest`, `LogEmailRequest`, `DraftWithAttachmentsRequest` |
| Pipeline → Preprocessing | Internal | `List[Dict]` of `{ message_id, from, to, subject, timestamp, body }` |
| Pipeline → EmbeddingService | Internal | `str` text → `List[float]` embedding |
| Pipeline → VectorDB | Internal | `{ vector_id, embedding, metadata, namespace }` |
| Pipeline → LLMService | Internal | `messages: [{ role, content }]` → `str` response |
| Agent → Backend | Response | `{ success, answer/label/draft_content, processing_info }` |
| Backend → Frontend | Response | Formatted JSON with success/error status |

### Email Message Structure (Internal)

```json
{
    "message_id": "msg_abc123",
    "from": "sender@example.com",
    "to": ["recipient@example.com"],
    "subject": "Meeting tomorrow",
    "timestamp": "2026-02-06T10:00:00Z",
    "body": "Clean text content after preprocessing"
}
```

### Vector DB Metadata (Email)

```json
{
    "thread_id": "thread_xyz",
    "message_id": "msg_abc123",
    "timestamp": "2026-02-06T10:00:00Z",
    "type": "email_data",
    "subject": "Meeting tomorrow",
    "from": "sender@example.com",
    "to": "recipient@example.com",
    "document": "Subject: Meeting tomorrow\n\nBody: Let's meet at 3pm..."
}
```

### Vector DB Metadata (Attachment)

```json
{
    "message_id": "msg_abc123",
    "thread_id": "thread_xyz",
    "attachment_id": "report.pdf",
    "filename": "report.pdf",
    "chunk_index": "0",
    "type": "attachment_data",
    "document": "Extracted text content from the attachment..."
}
```

### Label Pipeline Output

```json
{
    "label": "meeting",
    "category": "Discussion",
    "topic": "Team Meeting",
    "subtopic": "Sprint Planning",
    "subject_matter": "Weekly sprint planning meeting for Q1 deliverables"
}
```

---

## 12. Storage Architecture

### Per-User Data Directory Layout

```
agent/data/{user_id}/
├── log_emails/
│   └── {thread_id}/
│       └── {thread_id}.json          # Preprocessed email thread
│
├── store_attachments/
│   └── {thread_id}/
│       ├── report.pdf                 # Saved attachment files
│       └── {message_id}_metadata.json # Attachment metadata
│
├── vector_db/
│   └── cdb_{user_id}/
│       └── chroma.sqlite3            # Per-user ChromaDB persistent storage
│
└── sql_data/
    ├── chat_thread_processing.db     # Tracks: email_embeddings, attachment_processing
    └── draft_processing.db           # Tracks: draft_processing, attachment_processing
```

### Database Tables

**chat_thread_processing.db / draft_processing.db:**

| Table | Primary Key | Tracks |
|-------|-------------|--------|
| `email_embeddings` | `(user_id, thread_id, message_id)` | Which messages have been embedded |
| `attachment_processing` | `(user_id, thread_id, attachment_id)` | Which attachments have been embedded |
| `draft_processing` | `(user_id, thread_id, draft_id)` | Draft generation tracking |

**Settings DB (per-user, encrypted):**

| Table | Content |
|-------|---------|
| `user_settings` | Encrypted JSON with LLM provider, API keys, model preferences |

---

## 13. Observations & Notes

1. **Async Background Pattern:** Chat and draft endpoints return a `job_id` immediately. Clients poll `/api/job-status/{job_id}` until `status == "done"` or `"error"`. The in-memory `_job_store` dict is thread-safe via `threading.Lock`.

2. **Tool Calling is OpenAI-only for Inbuilt Mode:** Even when using "inbuilt" mode (Ollama for final answers), the tool-calling step uses OpenAI (`gpt-5-mini`) because Ollama doesn't natively support tool calling via the LangChain binding. For non-inbuilt providers, a text-based tool selection prompt is used instead.

3. **Dual Chat Pipeline Files:** Both `agent/chat_pipeline.py` (top-level) and `agent/services/chat_pipeline.py` exist. The **services/** version is the one actually imported and used by `main.py`.

4. **Some Endpoints are Disabled:** `ingest`, `related-threads`, and `slack/ingest` are commented out in `main.py`, indicating they are not yet production-ready.

5. **Hardcoded Paths:** `services/llm.py` and `services/embeddings.py` contain a hardcoded `CONFIG_PATH = "/home/ubuntu/openmailbot/openmailbot/agent/config.json"` which should be made relative.

6. **Label Push to Gmail:** The `/api/label-email` endpoint can optionally accept an `access_token` to push the classified label directly to the user's Gmail mailbox via the Gmail REST API, including color-coded label creation.

7. **Graph Storage is Selective:** Only threads labeled as `response`, `FYI`, or `Awaiting Reply` are stored in the Neo4j graph database. Other labels skip graph storage.

8. **Encryption:** User settings (including API keys) are encrypted at rest using PBKDF2-derived Fernet keys, scoped per user ID.
