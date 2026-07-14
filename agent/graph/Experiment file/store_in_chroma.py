import json
import re
from pathlib import Path
from typing import List, Dict, Any
import requests

# ============================================================================
# Step 1: Extract credentials
# ============================================================================

TEST_PY = Path(__file__).with_name("test.py")


def extract_credentials(path: Path):
    """Extract Neo4j credentials from test.py"""
    text = path.read_text()
    username = re.search(r'username\s*=\s*"([^"]+)"', text)
    password = re.search(r'password\s*=\s*"([^"]+)"', text)
    url = re.search(r'url\s*=\s*"([^"]+)"', text)
    database = re.search(r'database\s*=\s*"([^"]+)"', text)
    
    if not (username and password and url):
        raise RuntimeError(f"Could not extract credentials from {path}")
    
    return username.group(1), password.group(1), url.group(1), (database.group(1) if database else None)


# ============================================================================
# Step 2: Query Neo4j and create documents
# ============================================================================

def query_threads_and_topics(uri: str, user: str, pwd: str, database: str = None) -> List[Dict[str, Any]]:
    """Query Neo4j for all Thread nodes and their DISCUSSES relationships to Topics"""
    try:
        from neo4j import GraphDatabase
    except ImportError:
        raise RuntimeError("neo4j driver not installed. Run: pip install neo4j")
    
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    threads_data = []
    
    try:
        session = driver.session(database=database) if database else driver.session()
        
        query = """
        MATCH (t:Thread)
        OPTIONAL MATCH (t)-[:DISCUSSES]->(topic:Topic)
        RETURN t.thread_id as thread_id,
               t.subject as subject,
               t.participants as participants,
               t.updated_at as updated_at,
               collect(distinct topic.name) as topics
        ORDER BY t.thread_id
        """
        
        result = session.run(query)
        for record in result:
            threads_data.append({
                "thread_id": record["thread_id"],
                "subject": record["subject"],
                "participants": record["participants"] or [],
                "updated_at": record["updated_at"],
                "topics": [t for t in (record["topics"] or []) if t]
            })
        
        session.close()
    finally:
        driver.close()
    
    return threads_data


def create_langchain_documents(threads_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert thread data into LangChain document format"""
    documents = []
    
    for thread in threads_data:
        content_parts = [f"Thread: {thread['subject']}"]
        if thread["topics"]:
            content_parts.append(f"Discussed Topics: {', '.join(thread['topics'])}")
        
        content = "\n".join(content_parts)
        
        metadata = {
            "thread_id": thread["thread_id"]
        }
        
        documents.append({
            "page_content": content,
            "metadata": metadata
        })
    
    return documents


# ============================================================================
# Step 3: FastAPI Embedding Model
# ============================================================================

from llama_index.core.embeddings import BaseEmbedding


class FastAPIEmbedding(BaseEmbedding):
    """Custom embedding model that calls FastAPI endpoint"""
    
    def _get_text_embedding(self, text: str):
        r = requests.post(
            "https://lsdiedb39c.pagekite.me/embed",
            json={"text": text},
            timeout=30
        )
        return r.json()["embedding"]

    async def _aget_text_embedding(self, text: str):
        return self._get_text_embedding(text)

    def _get_query_embedding(self, query: str):
        r = requests.post(
            "https://lsdiedb39c.pagekite.me/embed",
            json={"text": query},
            timeout=30
        )
        return r.json()["embedding"]

    async def _aget_query_embedding(self, query: str):
        return self._get_query_embedding(query)


# ============================================================================
# Step 4: Initialize LlamaIndex Settings
# ============================================================================

from llama_index.core import Settings

print("✓ Step 1: Initializing embedding model...")
Settings.embed_model = FastAPIEmbedding()
print("✓ Step 2: Embedding model initialized successfully")


# ============================================================================
# Step 5: Initialize Chroma Vector Store
# ============================================================================

import chromadb
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core.schema import Document

print("✓ Step 3: Initializing Chroma vector store...")
chroma_client = chromadb.PersistentClient(path="./chroma_db")

try:
    collection = chroma_client.get_collection("threads")
except Exception:
    collection = chroma_client.create_collection("threads")
print(f"  - Collection created/retrieved: {collection.name}")

vector_store = ChromaVectorStore(chroma_collection=collection)
print("✓ Step 4: Vector store initialized successfully")


# ============================================================================
# Step 6: Store documents in Chroma
# ============================================================================

def store_documents_in_chroma(documents: List[Dict[str, Any]], vector_store: ChromaVectorStore):
    """Store each document in the Chroma vector store"""
    from llama_index.core import VectorStoreIndex
    
    print(f"\n✓ Step 5: Storing {len(documents)} documents in Chroma...")
    
    # Convert to LlamaIndex Document objects
    llamaindex_docs = [
        Document(
            text=doc["page_content"],
            metadata=doc["metadata"]
        )
        for doc in documents
    ]
    
    # Create index from documents (this will embed and store them)
    index = VectorStoreIndex.from_documents(
        llamaindex_docs,
        vector_store=vector_store
    )
    
    print(f"✓ Step 6: Successfully stored {len(documents)} documents in Chroma")
    return index


# ============================================================================
# Main
# ============================================================================

def main():
    print("=" * 70)
    print("LOADING THREADS AND STORING IN CHROMA VECTOR STORE")
    print("=" * 70)
    
    print("\nExtracting credentials from test.py...")
    user, pwd, uri, db = extract_credentials(TEST_PY)
    print(f"✓ Extracted: user={user}, database={db}")
    
    print(f"\nConnecting to Neo4j: {uri}")
    threads_data = query_threads_and_topics(uri, user, pwd, database=db)
    print(f"✓ Retrieved {len(threads_data)} threads")
    
    print("\nCreating LangChain documents...")
    documents = create_langchain_documents(threads_data)
    print(f"✓ Created {len(documents)} documents")
    
    if not documents:
        print("\n⚠️  No documents to store!")
        return
    
    print("\nSample document:")
    sample = documents[0]
    print(f"  Content: {sample['page_content']}")
    print(f"  Metadata: {sample['metadata']}")
    
    # Store in Chroma
    index = store_documents_in_chroma(documents, vector_store)
    
    print("\n" + "=" * 70)
    print("✓ ALL DOCUMENTS SUCCESSFULLY STORED IN CHROMA")
    print("=" * 70)
    print(f"\nChroma database location: ./chroma_db")
    print(f"Collection name: threads")
    print(f"Total documents stored: {len(documents)}")


if __name__ == "__main__":
    main()
