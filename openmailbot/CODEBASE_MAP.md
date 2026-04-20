# OpenMailBot — Codebase Map

> Only important code files listed. Docs, test files, and build artifacts excluded.

---

## `/agent/` — Python FastAPI AI Agent (port 5051)

| File | Summary | Type |
|------|---------|------|
| `main.py` | Core FastAPI app — defines all agent API routes (`/api/chat-with-thread`, `/api/draft`, `/api/label-email-async`, `/api/summarize-thread`, `/api/settings`, `/api/log-email`, `/api/store-attachments`, `/api/job-status`) | Python — FastAPI entrypoint |
| `config.py` | Loads environment variables and app-wide settings (LLM provider, embedding provider, vector DB, backend URL) | Python — Config |
| `utils.py` | Shared utility helpers used across agent pipelines | Python — Utilities |

### `/agent/services/` — Core Processing Pipelines

| File | Summary | Type |
|------|---------|------|
| `chat_pipeline.py` | RAG-based chat over an email thread — retrieves embeddings, runs LLM Q&A | Python — Pipeline |
| `draft_pipeline.py` | Generates email draft replies using thread context + attachments via LLM | Python — Pipeline |
| `simple_draft_pipeline.py` | Lightweight draft generation without attachments | Python — Pipeline |
| `summarization_pipeline.py` | Summarizes an email thread using LLM; produces structured summary | Python — Pipeline |
| `label_pipeline.py` | Classifies email threads into labels (Meeting, FYI, Escalation, etc.) via rules + LLM | Python — Pipeline |
| `preprocessing_emails.py` | Cleans and deduplicates email bodies (strips HTML, quoted text, disclaimers, URLs) | Python — Preprocessing |
| `settings_manager.py` | Reads/writes user settings to per-user encrypted SQLite DB (PBKDF2 + Fernet) | Python — Settings |
| `store_pipeline.py` | Stores emails and attachments into vector DB (ChromaDB/Pinecone/Weaviate) for RAG | Python — Storage |
| `embeddings.py` | Generates embeddings via configured provider (inbuilt, OpenAI, etc.) | Python — Embeddings |
| `rag.py` | Retrieval-Augmented Generation — semantic search over stored email embeddings | Python — RAG |
| `llm.py` | LLM abstraction layer — routes requests to OpenAI / Ollama / inbuilt model | Python — LLM |
| `inbuilt.py` | Local/inbuilt LLM and embedding fallback implementation | Python — LLM |
| `label_email_lockbook.py` | Tracks per-user and global label-email metrics (requests, label counts) | Python — Metrics |
| `file_processor.py` | Extracts text from attachment files (PDF, DOCX, etc.) for embedding | Python — File Processing |
| `ingestion.py` | Email ingestion from Gmail/Outlook providers | Python — Ingestion |

### `/agent/vector/` — Vector DB Clients

| File | Summary | Type |
|------|---------|------|
| `base.py` | Abstract base class / interface for all vector DB clients | Python — Interface |
| `chroma_client.py` | ChromaDB client — default local vector store for email embeddings | Python — Vector DB |
| `pinecone_client.py` | Pinecone cloud vector store client | Python — Vector DB |
| `weaviate_client.py` | Weaviate vector store client | Python — Vector DB |

### `/agent/database/`

| File | Summary | Type |
|------|---------|------|
| `mongodb.py` | MongoDB client wrapper for agent-side DB access | Python — Database |

---

## `/addon/` — Gmail Add-on (Google Apps Script)

| File | Summary | Type |
|------|---------|------|
| `Code.gs` | Main Gmail Add-on — UI cards, button actions, calls agent endpoints for label/draft/chat | Google Apps Script |
| `BackgroundEmailMonitor.gs` | Time-triggered background monitor — polls new emails, calls `/api/label-email-async` automatically | Google Apps Script |

---

## `/agent/thunderbrid-addon/` — Thunderbird WebExtension (Manifest V2)

| File | Summary | Type |
|------|---------|------|
| `manifest.json` | Extension manifest — declares permissions, background script, popup/options pages | JSON — Extension Config |
| `background.js` | Background service worker — polls job status, syncs settings to backend, runs 1-min email monitor | JavaScript — Extension |
| `popup/popup.js` | Popup UI logic — triggers summarize/draft/chat actions on selected email thread | JavaScript — Extension |
| `options/options.js` | Settings page logic — saves backend URL + API keys, syncs user_id to backend | JavaScript — Extension |

---