# OpenMailBot

This is the monorepo for OpenMailBot, an open-source AI email agent for Gmail. See the root README for full PRD and architecture.

## Structure
- `frontend/` — Next.js + Tailwind CSS web portal
- `backend/` — Node.js (Express) API, auth, analytics
- `agent/` — Python (FastAPI) agent for email ingestion, embeddings, RAG, LLM
- `addon/` — Google Apps Script Gmail Add-on (CardService)
- `db/` — MongoDB schema and setup
- `vector/` — Pinecone/FAISS integration
- `graph/` — Neo4j/NetworkX integration
- `docker/` — Docker & deployment scripts
- `docs/` — API documentation, setup guide

MIT License.
