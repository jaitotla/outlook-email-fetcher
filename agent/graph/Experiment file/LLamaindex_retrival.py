import requests
from llama_index.core.embeddings import BaseEmbedding
import os
os.environ["OPENAI_API_KEY"] ="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"

class FastAPIEmbedding(BaseEmbedding):
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


from llama_index.core import Settings

print("✓ Step 1: Initializing embedding model...")
Settings.embed_model = FastAPIEmbedding()
print("✓ Step 2: Embedding model initialized successfully")

from llama_index.graph_stores.neo4j import Neo4jGraphStore

print("✓ Step 3: Connecting to Neo4j graph store...")
graph_store = Neo4jGraphStore(
    username="neo4j",
    password="xR15egCk9mX8Tf4Xo1Wf_Z355rINJ7iO-uyZyx_1T8k",
    url="neo4j+s://e5c7fa42.databases.neo4j.io",
    database="neo4j"
)
print("✓ Step 4: Neo4j graph store connected successfully")

import chromadb
from llama_index.vector_stores.chroma import ChromaVectorStore

print("✓ Step 5: Initializing Chroma vector store...")
chroma_client = chromadb.PersistentClient(path="./chroma_db")

try:
    collection = chroma_client.get_collection("threads")
except Exception:
    collection = chroma_client.create_collection("threads")
print(f"  - Collection created/retrieved: {collection.name}")

vector_store = ChromaVectorStore(chroma_collection=collection)
print("✓ Step 6: Vector store initialized successfully")

from llama_index.core import StorageContext

storage_context = StorageContext.from_defaults(
    vector_store=vector_store,
    graph_store=graph_store
)
print("✓ Step 7: Storage context created successfully")

from llama_index.core import Document
from llama_index.core.indices import PropertyGraphIndex

print("✓ Step 8: Creating documents...")
docs = [
    Document(
        text="""
        Hotel Appointment Booking Website
Objective
Provide a simple way for users to book a hotel appointment online.
Target Users
Hotel guests
Hotel admin/staff
Core Features
Home page with hotel details and book appointment button
Appointment booking form with name, contact, date, time, and number of guests
Booking confirmation message after submission
Admin login to view all bookings
Non-Functional Requirements
Responsive on mobile and desktop
Fast and simple user interface
Basic form validation

Out of Scope
Online payments
User accounts
Room selection
Reviews and ratings
Success Criteria
Users can complete a booking quickly
Admin can easily view booking details
        """,
        metadata={"thread_id": "T102"}
    ),
   
]
print(f"  - {len(docs)} documents created")

print("✓ Step 9: Building property graph index...")
index = PropertyGraphIndex.from_documents(
    docs,
    storage_context=storage_context,
    show_progress=True
)
print("✓ Step 10: Property graph index built successfully")

print("✓ Step 11: Creating retriever from PropertyGraphIndex...")
retriever = index.as_retriever(
    similarity_top_k=3,
    include_text=True
)
print("✓ Step 12: Retriever created successfully")

from llama_index.core.query_engine import RetrieverQueryEngine

print("✓ Step 13: Creating query engine...")
query_engine = RetrieverQueryEngine.from_args(
    retriever=retriever
)
print("✓ Step 14: Query engine created successfully")

print("\n✓ Step 15: Executing query...")
query_text = "Show finance budget"
print(f"  - Query: {query_text}")
response = query_engine.query(query_text)
print("✓ Step 16: Query completed")

print("\n" + "="*50)
print("QUERY RESULT:")
print("="*50)
print(f"\nResponse Object: {response}")
print(f"Response Type: {type(response)}")

# Try to access different possible attributes
if hasattr(response, 'response'):
    print(f"\n✓ Response.response: {response.response}")
if hasattr(response, 'source_nodes'):
    print(f"\n✓ Source Nodes Count: {len(response.source_nodes)}")
    for i, node in enumerate(response.source_nodes):
        print(f"  Node {i+1}:")
        print(f"    - Text: {node.text if hasattr(node, 'text') else 'N/A'}")
        print(f"    - Score: {node.score if hasattr(node, 'score') else 'N/A'}")
        print(f"    - Metadata: {node.metadata if hasattr(node, 'metadata') else 'N/A'}")
if hasattr(response, 'metadata'):
    print(f"\n✓ Response Metadata: {response.metadata}")

print(f"\n✓ Full Response String: {str(response)}")
print(f"✓ Response Length: {len(str(response))}")
print("="*50)
