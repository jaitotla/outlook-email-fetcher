"""
RAG Pipeline: Topic Vector Search → Neo4j Graph Retrieval

Flow:
    User Query
        ↓
    ChromaDB — similarity search on topic names
    (stores: topic_name, thread_id, node_type ONLY)
        ↓
    Extract matched: topic_name + thread_id
        ↓
    Neo4j — MATCH (thread {thread_id})-[d:DISCUSSES]->(topic {name: topic_name})
        ↓
    Return d.message_id from the relationship  ← always from graph, never stored in Chroma
        ↓
    Final: thread_id + message_id + metadata

ChromaDB doc format (lean — only what's needed for graph lookup):
{
    "page_content": "Request for Status Update",
    "metadata": {
        "topic_name": "Request for Status Update",
        "thread_id":  "197bff9f065278dc",
        "node_type":  "Topic"              # or "Subtopic"
    }
}
"""

import os
import requests
import chromadb
import json
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
from neo4j import GraphDatabase


# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────

CHROMA_COLLECTION_NAME = "email_topics"
NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
TOP_K = 5


# ─────────────────────────────────────────────
# Custom Embedding Function
# ─────────────────────────────────────────────

class FastAPIEmbedding(EmbeddingFunction):
    """Custom embedding via FastAPI endpoint."""
    
    def __init__(self):
        pass
    
    def __call__(self, input: Documents) -> Embeddings:
        """Generate embeddings for documents."""
        embeddings = []
        for text in input:
            r = requests.post(
                "https://lsdiedb39c.pagekite.me/embed",
                json={"text": text},
                timeout=30
            )
            embeddings.append(r.json()["embedding"])
        return embeddings


# ─────────────────────────────────────────────
# 1. ChromaDB — Lean Topic Collection
# ─────────────────────────────────────────────

def get_chroma_collection(persist_directory: str = "./chroma_db"):
    client = chromadb.PersistentClient(path=persist_directory)
    ef = FastAPIEmbedding()
    
    # Delete existing collection if it exists to avoid embedding function conflict
    try:
        client.delete_collection(name=CHROMA_COLLECTION_NAME)
        print(f"Deleted existing '{CHROMA_COLLECTION_NAME}' collection to use new embedding function")
    except:
        pass  # Collection doesn't exist yet
    
    try:
        return client.get_collection(name=CHROMA_COLLECTION_NAME)
    except Exception:
        return client.create_collection(
            name=CHROMA_COLLECTION_NAME,
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"}
        )


def ingest_topic_documents(collection, topic_docs: list[dict]):
    """
    Ingest topic-level docs — NO message_id stored here.

    Each doc:
    {
        "page_content": "Request for Status Update",   ← gets embedded
        "metadata": {
            "topic_name": "Request for Status Update",
            "thread_id":  "197bff9f065278dc",
            "node_type":  "Topic"                      ← or "Subtopic"
        }
    }
    """
    texts     = [doc["page_content"] for doc in topic_docs]
    metadatas = [doc["metadata"]     for doc in topic_docs]
    # Unique ID per (topic, thread) combination
    ids = [
        f"{doc['metadata']['topic_name']}::{doc['metadata']['thread_id']}"
        for doc in topic_docs
    ]

    collection.upsert(documents=texts, metadatas=metadatas, ids=ids)
    print(f"✅ Ingested {len(topic_docs)} topic documents into ChromaDB")


# ─────────────────────────────────────────────
# 2. Vector Search
# ─────────────────────────────────────────────

def vector_search(collection, query: str, top_k: int = TOP_K) -> list[dict]:
    """
    Returns matched topics with only: topic_name, thread_id, node_type, relevance.
    No message_id — that comes from the graph.
    """
    results = collection.query(
        query_texts=[query],
        n_results=top_k,
        include=["documents", "metadatas", "distances"]
    )

    hits = []
    for i in range(len(results["ids"][0])):
        meta = results["metadatas"][0][i]
        hits.append({
            "topic_name": meta.get("topic_name"),
            "thread_id":  meta.get("thread_id"),
            "node_type":  meta.get("node_type"),
            "relevance":  round(1 - results["distances"][0][i], 4),
        })

    print(f"\n🔍 Vector search → {len(hits)} hits for: '{query}'")
    for h in hits:
        print(f"   topic='{h['topic_name']}' | thread={h['thread_id']} | score={h['relevance']}")
    return hits


# ─────────────────────────────────────────────
# 3. Neo4j — message_id lives HERE only
# ─────────────────────────────────────────────

class GraphRetriever:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def get_message_ids(self, hits: list[dict]) -> list[dict]:
        """
        For each (thread_id, topic_name) pair from vector search,
        traverse the graph and pull message_id from the DISCUSSES relationship.

        Cypher (Topic):
            MATCH (t:Thread {thread_id: $thread_id})
                  -[d:DISCUSSES]->
                  (topic:Topic {name: $topic_name})
            RETURN t.thread_id, t.subject, d.message_id, d.timestamp

        Cypher (Subtopic):
            MATCH (t:Thread {thread_id: $thread_id})
                  -[d:DISCUSSES]->
                  (sub:Subtopic {name: $topic_name})
            RETURN t.thread_id, t.subject, d.message_id, d.timestamp
        """
        topics    = [h for h in hits if h.get("node_type") != "Subtopic"]
        subtopics = [h for h in hits if h.get("node_type") == "Subtopic"]

        records = []

        with self.driver.session() as session:

            # ── Topics ────────────────────────────────────────────────────
            if topics:
                cypher = """
                UNWIND $pairs AS pair
                MATCH (t:Thread {thread_id: pair.thread_id})
                      -[d:DISCUSSES]->
                      (topic:Topic {name: pair.topic_name})
                OPTIONAL MATCH (t)-[:BELONGS_TO]->(cat:Category)
                RETURN
                    t.thread_id    AS thread_id,
                    t.subject      AS subject,
                    t.participants AS participants,
                    t.updated_at   AS updated_at,
                    cat.name       AS category,
                    topic.name     AS topic_name,
                    d.message_id   AS message_id,
                    d.timestamp    AS timestamp,
                    'Topic'        AS node_type
                """
                pairs = [{"thread_id": h["thread_id"], "topic_name": h["topic_name"]} for h in topics]
                for r in session.run(cypher, pairs=pairs):
                    records.append(dict(r))

            # ── Subtopics ─────────────────────────────────────────────────
            if subtopics:
                cypher = """
                UNWIND $pairs AS pair
                MATCH (t:Thread {thread_id: pair.thread_id})
                      -[d:DISCUSSES]->
                      (sub:Subtopic {name: pair.topic_name})
                OPTIONAL MATCH (t)-[:BELONGS_TO]->(cat:Category)
                RETURN
                    t.thread_id    AS thread_id,
                    t.subject      AS subject,
                    t.participants AS participants,
                    t.updated_at   AS updated_at,
                    cat.name       AS category,
                    sub.name       AS topic_name,
                    d.message_id   AS message_id,
                    d.timestamp    AS timestamp,
                    'Subtopic'     AS node_type
                """
                pairs = [{"thread_id": h["thread_id"], "topic_name": h["topic_name"]} for h in subtopics]
                for r in session.run(cypher, pairs=pairs):
                    records.append(dict(r))

        print(f"🕸️  Graph → {len(records)} records with message_ids retrieved")
        return records


# ─────────────────────────────────────────────
# 4. Result Formatter
# ─────────────────────────────────────────────

def format_results(hits: list[dict], graph_records: list[dict]) -> list[dict]:
    """
    Attach relevance scores from vector search to graph results.
    Deduplicate on (thread_id, message_id). Sort by relevance.
    """
    # Build lookup: (topic_name, thread_id) → relevance
    relevance_map = {(h["topic_name"], h["thread_id"]): h["relevance"] for h in hits}

    seen, merged = set(), []
    for r in graph_records:
        key = (r["thread_id"], r["message_id"])
        if key in seen:
            continue
        seen.add(key)

        merged.append({
            "thread_id":      r["thread_id"],
            "message_id":     r["message_id"],   # ← always from Neo4j
            "subject":        r.get("subject"),
            "timestamp":      r.get("timestamp"),
            "topic_name":     r.get("topic_name"),
            "node_type":      r.get("node_type"),
            "category":       r.get("category"),
            "participants":   r.get("participants"),
            "relevance_score": relevance_map.get(
                (r.get("topic_name"), r.get("thread_id")), 0.0
            ),
        })

    merged.sort(key=lambda x: x["relevance_score"], reverse=True)
    return merged


# ─────────────────────────────────────────────
# 5. Main Pipeline
# ─────────────────────────────────────────────

class EmailRAGPipeline:
    def __init__(
        self,
        chroma_persist_dir: str = "./chroma_db",
        neo4j_uri:          str = NEO4J_URI,
        neo4j_user:         str = NEO4J_USER,
        neo4j_password:     str = NEO4J_PASSWORD,
        top_k:              int = TOP_K,
    ):
        print("🚀 Initializing Email RAG Pipeline...")
        self.collection = get_chroma_collection(chroma_persist_dir)
        self.graph      = GraphRetriever(neo4j_uri, neo4j_user, neo4j_password)
        self.top_k      = top_k
        print("✅ Pipeline ready\n")

    def ingest(self, topic_docs: list[dict]):
        """Ingest lean topic docs (no message_id) into ChromaDB."""
        ingest_topic_documents(self.collection, topic_docs)

    def query(self, user_question: str) -> dict:
        """
        1. ChromaDB → matched (topic_name, thread_id) pairs
        2. Neo4j    → message_id from DISCUSSES relationship
        3. Return merged, ranked results
        """
        print(f"📨 Query: '{user_question}'")

        # Step 1 — vector search (no message_id here)
        hits = vector_search(self.collection, user_question, self.top_k)
        if not hits:
            return {"query": user_question, "results": []}

        # Step 2 — graph retrieval (message_id lives here)
        graph_records = self.graph.get_message_ids(hits)

        # Step 3 — merge & rank
        results = format_results(hits, graph_records)

        print(f"✅ Returning {len(results)} results\n")
        return {
            "query":   user_question,
            "results": results,
        }

    def close(self):
        self.graph.close()


# ─────────────────────────────────────────────
# 6. Bootstrap Helper: Pull topic docs FROM Neo4j
# ─────────────────────────────────────────────

def build_topic_docs_from_graph(graph_retriever: GraphRetriever) -> list[dict]:
    """
    One-time bootstrap: read all Thread→DISCUSSES→Topic/Subtopic edges
    from Neo4j and produce lean ChromaDB docs (no message_id stored).
    """
    cypher = """
    MATCH (thread:Thread)-[:DISCUSSES]->(node)
    WHERE node:Topic OR node:Subtopic
    RETURN
        thread.thread_id AS thread_id,
        node.name        AS topic_name,
        labels(node)[0]  AS node_type
    """
    docs = []
    with graph_retriever.driver.session() as session:
        for r in session.run(cypher):
            docs.append({
                "page_content": r["topic_name"],
                "metadata": {
                    "topic_name": r["topic_name"],
                    "thread_id":  r["thread_id"],
                    "node_type":  r["node_type"],
                    # ← no message_id here
                }
            })
    print(f"📦 Built {len(docs)} topic docs from graph")
    return docs


# ─────────────────────────────────────────────
# 7. Demo
# ─────────────────────────────────────────────

if __name__ == "__main__":

    # Lean docs — topic_name + thread_id + node_type only
    json_path = os.path.join(os.path.dirname(__file__), "langchain_docs_ankit2.json")
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            sample_topic_docs = json.load(f)
    except Exception as e:
        print(f"Failed to load sample_topic_docs from {json_path}: {e}")
        sample_topic_docs = []

    pipeline = EmailRAGPipeline(
        chroma_persist_dir="./chroma_db",
        neo4j_uri="neo4j+s://49d30f90.databases.neo4j.io",
        neo4j_user="neo4j",
        neo4j_password="FIdaz6r8IFSIb9yIELw--5lhHT_M4MRxD80ChOuF2Cg",
        top_k=3
    )
    

    pipeline.ingest(sample_topic_docs)

    result = pipeline.query("whats update on Voyager report")

    print("=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    for r in result["results"]:
        print(f"\n  thread_id  : {r['thread_id']}")
        print(f"  message_id : {r['message_id']}")   # ← from Neo4j only
        print(f"  topic      : {r['topic_name']} ({r['node_type']})")
        print(f"  subject    : {r['subject']}")
        print(f"  relevance  : {r['relevance_score']}")

    pipeline.close()