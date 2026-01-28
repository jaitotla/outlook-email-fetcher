# Changelog

All notable changes to OpenMailBot are documented in this file.

---

## [Unreleased] - January 2026

### 🔧 Multi-Tenant Configuration System

Major refactoring to support per-user provider configuration with a "one agent per tenant" deployment model.

#### Added
- **Settings UI in Gmail Add-on** ([gmail_summariser.gs](addon/gmail_summariser.gs))
  - ⚙️ Settings button on main card
  - `showSettingsCard()` with mode selector (Inbuilt/Custom)
  - LLM provider dropdown: OpenAI, Anthropic, Gemini, Ollama, Inbuilt
  - Embedding provider dropdown: OpenAI, Nomic, Gemini, Sentence-Transformers, Inbuilt
  - Vector DB dropdown: Pinecone, ChromaDB, Weaviate, Inbuilt
  - User profile fields: name, position, tone, custom system prompt
  - `saveSettings()` with backend sync
  - `fetchSettingsFromBackend()` for hybrid settings flow
  - `resetSettings()` to clear custom settings
  - `getEffectiveSettings()` for API calls

- **Backend Settings API** ([routes/settings.js](backend/routes/settings.js))
  - `GET /api/settings?user_id=email` - Fetch user settings (for add-on)
  - `POST /api/settings` - Save settings with validation
  - Input sanitization for all settings fields
  - Auto-creates user on first settings save (upsert)
  - Returns defaults for unknown users

- **Agent Configuration Updates** ([config.py](agent/config.py))
  - `LLM_PROVIDER`, `EMBEDDING_PROVIDER`, `VECTOR_PROVIDER` settings
  - Inbuilt mode URLs: `INBUILT_FLASK_URL`, `INBUILT_OLLAMA_URL`, `INBUILT_CHROMA_URL`
  - ChromaDB HTTP settings: `CHROMA_HOST`, `CHROMA_PORT`
  - Weaviate settings: `WEAVIATE_URL`, `WEAVIATE_API_KEY`
  - Nomic settings: `NOMIC_API_KEY`, `NOMIC_MODEL`

- **Detailed Health Check** ([main.py](agent/main.py))
  - `GET /health/detailed` endpoint
  - Optional `user_id` and `tenant_id` parameters
  - Returns status for each provider (LLM, embedding, vector)
  - Reports "degraded" status if any provider fails

- **Weaviate Vector Client** ([weaviate_client.py](agent/vector/weaviate_client.py))
  - HTTP-only client implementing BaseVectorStore
  - `_get_class_name()` converts namespace to PascalCase
  - `_ensure_collection()` creates schema
  - Full CRUD operations

- **Inbuilt Service Wrapper** ([inbuilt.py](agent/services/inbuilt.py))
  - `InbuiltLLMService`, `InbuiltEmbeddingService`, `InbuiltVectorClient`
  - Factory functions for zero-config mode
  - Wraps utils.py functions

- **LLM Service Updates** ([llm.py](agent/services/llm.py))
  - `ProviderError` exception class for clear error propagation
  - `_call_gemini()` using google-generativeai SDK
  - `_call_openai_responses()` for gpt-5 models (Responses API)
  - `_call_inbuilt()` wrapping utils.py
  - `effective_settings` parameter for per-request config

- **Embedding Service Updates** ([embeddings.py](agent/services/embeddings.py))
  - `_embed_nomic()` - Nomic embeddings
  - `_embed_gemini()` - Gemini embeddings
  - `_embed_sentence_transformers()` - Local embeddings
  - `_embed_inbuilt()` - Central server embeddings
  - `effective_settings` parameter

- **Vector Client Factory** ([vector/__init__.py](agent/vector/__init__.py))
  - `get_vector_client(provider, settings)` factory function
  - Supports: pinecone, chroma, weaviate, inbuilt

- **Documentation**
  - [FUTURE_WORK.md](FUTURE_WORK.md) - Roadmap for pending features

#### Changed
- **ChromaDB Client** ([chroma_client.py](agent/vector/chroma_client.py))
  - Rewritten for HTTP-only remote connections
  - Uses `chromadb.HttpClient(host, port)` instead of `PersistentClient`
  - Removed all local storage (`os.makedirs`, path logic)
  - Added `health_check()` method

- **Utils.py** ([utils.py](agent/utils.py))
  - Added comprehensive documentation for inbuilt mode
  - URLs configurable via env vars (`INBUILT_FLASK_URL`, `INBUILT_OLLAMA_URL`)

- **Requirements** ([requirements.txt](agent/requirements.txt))
  - Added: `google-generativeai==0.3.2`, `nomic==2.0.0`, `weaviate-client==4.4.0`
  - Removed: `faiss-cpu` (FAISS deprecated)
  - Fixed duplicate entries

- **.gitignore**
  - Added: `agent/.env`, `agent/config.json`, `**/.ipynb_checkpoints/`

#### Removed
- `agent/vector/faiss_client.py` - FAISS is inherently local, not suitable for remote-only architecture
- `agent/.ipynb_checkpoints/` directories
- `agent/services/.ipynb_checkpoints/` directories

#### Fixed
- Commented out duplicate `draftWithAttachments` function in gmail_summariser.gs

---

## [1.1.0] - Draft Pipeline Integration

### Added
- **Draft with Attachments Pipeline** ([draft_pipeline.py](agent/services/draft_pipeline.py))
  - `DraftWithAttachmentsPipeline` class
  - Attachment processing (PDF, CSV, PPTX)
  - ChromaDB integration for semantic search
  - SQLite tracking for processed attachments
  - Hybrid OpenAI + Ollama approach
  - User preference support (name, position, tone, custom instructions)

- **Backend Draft API**
  - [draftController.js](backend/controllers/draftController.js) - Request handlers
  - [draft.js](backend/routes/draft.js) - API routes
  - `POST /api/draft/with-attachments` - Generate draft
  - `GET /api/draft/preferences` - Get preferences
  - `POST /api/draft/preferences` - Save preferences
  - `GET /api/draft/health` - Health check

- **FastAPI Endpoint**
  - `POST /draft-with-attachments` in main.py
  - `DraftWithAttachmentsRequest` model

### Data Flow
```
User Request → Express (/api/draft/with-attachments)
    → Draft Controller → FastAPI (/draft-with-attachments)
    → Draft Pipeline → OpenAI (tools) + Ollama (generation)
    → Response (Draft Email)
```

---

## [1.0.0] - Chat Pipeline Integration

### Added
- **Chat with Thread Pipeline** ([chat_pipeline.py](agent/services/chat_pipeline.py))
  - `ChatWithThreadPipeline` class - Main RAG orchestrator
  - Email processing from JSON files
  - Attachment handling (PDF, CSV, PPTX)
  - ChromaDB integration for semantic search
  - SQLite tracking for processed items
  - Hybrid approach: OpenAI (tool calling) + Ollama (answer generation)

- **Prompt Management** ([prompt/](agent/prompt/))
  - `prompt.py` - Centralized prompt templates
  - System prompts for OpenAI and Ollama
  - Tool descriptions
  - Result formatting templates

- **Backend Chat API**
  - [chatController.js](backend/controllers/chatController.js) - Request handlers
  - [chat.js](backend/routes/chat.js) - API routes
  - `POST /api/chat/thread` - Chat with thread
  - `POST /api/chat/search` - Search within thread
  - `GET /api/chat/thread/:threadId` - Get chat history
  - `GET /api/chat/health` - Health check

- **FastAPI Endpoint**
  - `POST /chat-with-thread` in main.py
  - `ChatWithThreadRequest` model

- **Dependencies**
  - `ollama` - Local LLM integration
  - `langchain-openai` - OpenAI integration
  - `llama-index` - Document indexing
  - `llama-index-readers-file` - File readers
  - `pypdf` - PDF processing

### Architecture
```
Frontend (Next.js)
    ↓
Express Backend (/api/chat/*)
    ↓
FastAPI Agent (/chat-with-thread)
    ↓
Chat Pipeline Service
    ├─ OpenAI GPT-4o (Tool calling)
    ├─ Ollama llama3.2 (Answer generation)
    └─ ChromaDB (Semantic search)
```

---

## [0.9.0] - Initial Build

### Added
- **Frontend (Next.js 14)** ([frontend/](frontend/))
  - Landing page with feature showcase
  - User authentication (Google OAuth via NextAuth.js)
  - Dashboard with email statistics
  - AI Chat interface
  - Analytics page with charts
  - Settings page
  - Responsive design with Tailwind CSS

- **Backend (Node.js + Express)** ([backend/](backend/))
  - Google and Microsoft OAuth authentication
  - Multi-tenant architecture
  - RESTful API endpoints
  - JWT session management
  - Email metadata management

- **Python Agent (FastAPI)** ([agent/](agent/))
  - Email ingestion from Gmail/Outlook
  - Embedding generation
  - RAG pipeline
  - LLM integration (OpenAI/Anthropic/Ollama)
  - Vector database integration

- **Gmail Add-on** ([addon/](addon/))
  - Email summarization
  - Smart reply generation
  - Natural language queries
  - Settings management

- **Thunderbird Add-on** ([thunderbird-addon/](thunderbird-addon/))
  - WebExtension-based modern add-on
  - Email summarization
  - AI-powered reply generation
  - Semantic search
  - Sentiment analysis

- **Docker Configuration** ([docker/](docker/))
  - `docker-compose.yml` - Service orchestration
  - Dockerfiles for all services

---

## Breaking Changes

### None in Recent Updates
All changes are backward compatible:
- ✅ Existing FastAPI endpoints unchanged
- ✅ Existing Express routes unchanged
- ✅ Database schemas extended, not modified
- ✅ Authentication logic preserved
- ✅ Only additions to codebase
