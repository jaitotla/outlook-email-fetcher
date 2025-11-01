# Vector Database Integration

This directory contains vector database clients for semantic search over email embeddings.

## Supported Vector Databases

### 1. Pinecone (Cloud)
- **Location**: `agent/vector/pinecone_client.py`
- **Features**: 
  - Managed cloud vector database
  - Automatic scaling
  - High availability
  - Fast queries (<100ms)
- **Setup**: Requires Pinecone API key and environment
- **Best for**: Production deployments, large scale

### 2. FAISS (Local)
- **Location**: `agent/vector/faiss_client.py`
- **Features**:
  - Local file-based storage
  - No external dependencies
  - CPU-optimized
  - Persistence to disk
- **Setup**: No API keys required
- **Best for**: Self-hosted, development, privacy-focused

## Node.js Wrappers

The `vector/pinecone.js` file provides a lightweight Node.js wrapper that communicates with the Python agent. The backend can use these if needed, but the primary implementation is in Python.

## Usage

The vector databases store email embeddings with metadata:
- User ID
- Tenant ID
- Thread ID
- Subject
- From/To addresses
- Timestamp
- Content preview

Namespaces are used for tenant isolation: `{tenantId}_{userId}`

## Configuration

See `agent/.env.example` for vector DB configuration options.
