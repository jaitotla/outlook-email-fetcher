"""
GraphRAG Pipeline  –  test1.py
===============================
Architecture (refer to diagram):

  Document Knowledge Graph (DKG – green layer)
    Document → Metadata (Author, Year, …)
    Document → Chapter 1 → Chunk 1, Chunk 2
    Document → Chapter 2 → Chunk 3

  Information Knowledge Graph (IKG – blue layer)
    Chunk 1 → Keyword A
    Chunk 2 → Keyword A, Keyword B
    ...

GraphRAG Retrieval (Figure 5):
    Query ──▶ Vector DB ──▶ Top-K chunks
         ├── ICS  : chapter siblings of those chunks
         ├── IKS  : keyword-linked chunks from those chunks
         └── UKS  : chunks linked via unique keywords of retrieved chunks
    All combined ──▶ LLM ──▶ Answer

Logging:  every stage logs  ▶ IN  and  ◀ OUT clearly.
"""

import os, json, uuid, logging, textwrap
from pathlib import Path
from typing import List, Dict, Any, Tuple

# ── LangChain ──────────────────────────────────────────────────────────────
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    from langchain.text_splitter import RecursiveCharacterTextSplitter

try:
    from langchain_openai import OpenAIEmbeddings, ChatOpenAI
except ImportError:
    from langchain.embeddings.openai import OpenAIEmbeddings
    from langchain.chat_models.openai import ChatOpenAI

try:
    from langchain_core.documents import Document
except ImportError:
    from langchain.schema import Document

try:
    from langchain_core.messages import HumanMessage, SystemMessage
except ImportError:
    from langchain.schema import HumanMessage, SystemMessage

# ── ChromaDB (direct, not through LangChain) ────────────────────────────────
import chromadb
from chromadb.config import Settings as ChromaSettings

# ── Neo4j ──────────────────────────────────────────────────────────────────
from neo4j import GraphDatabase

# ── OpenAI (direct, for structured calls) ──────────────────────────────────
from openai import OpenAI


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║                         CONFIGURATION                                   ║
# ╚══════════════════════════════════════════════════════════════════════════╝

NEO4J_URI       = os.getenv("NEO4J_URI",      "neo4j+s://e5c7fa42.databases.neo4j.io")
NEO4J_USER      = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD  = os.getenv("NEO4J_PASSWORD", "xR15egCk9mX8Tf4Xo1Wf_Z355rINJ7iO-uyZyx_1T8k")

OPENAI_API_KEY  = os.getenv(
    "OPENAI_API_KEY",
    "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",
)

CHROMA_DIR   = "./chroma_db"          # persistent ChromaDB storage
CHUNK_SIZE   = 500                    # characters per chunk
CHUNK_OVERLAP= 60
TOP_K_VECTOR = 3                      # Vector DB top-k retrieval


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║                         LOGGING SETUP                                   ║
# ╚══════════════════════════════════════════════════════════════════════════╝

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("GraphRAG")


def _banner(title: str) -> None:
    line = "─" * 70
    log.info(line)
    log.info(f"  ◈  {title}")
    log.info(line)


def _in(label: str, data: Any) -> None:
    """Log what enters a stage."""
    preview = str(data)
    if len(preview) > 300:
        preview = preview[:300] + " … [truncated]"
    log.info(f"  ▶ IN  [{label}]: {preview}")


def _out(label: str, data: Any) -> None:
    """Log what exits a stage."""
    preview = str(data)
    if len(preview) > 300:
        preview = preview[:300] + " … [truncated]"
    log.info(f"  ◀ OUT [{label}]: {preview}")


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  STAGE 1 – Load text documents from a directory / list of paths         ║
# ╚══════════════════════════════════════════════════════════════════════════╝

def load_documents(paths: List[str]) -> List[Dict[str, Any]]:
    """
    Load raw text from each path.
    Returns  [{"doc_id": ..., "file_name": ..., "text": ..., "metadata": {...}}]
    """
    _banner("STAGE 1 – Document Loading")
    _in("paths", paths)

    docs = []
    for p in paths:
        path = Path(p)
        if not path.exists():
            log.warning(f"  ⚠  File not found: {p}")
            continue

        text = path.read_text(encoding="utf-8", errors="ignore")
        doc_id = str(uuid.uuid4())[:8]
        entry = {
            "doc_id":    doc_id,
            "file_name": path.name,
            "text":      text,
            "metadata": {
                "source":    str(path),
                "file_name": path.name,
                "doc_id":    doc_id,
            },
        }
        docs.append(entry)
        log.info(f"  📄  Loaded '{path.name}'  |  {len(text):,} chars  |  doc_id={doc_id}")

    _out("documents", f"{len(docs)} documents loaded")
    return docs


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  STAGE 2 – Chunking with LangChain                                      ║
# ╚══════════════════════════════════════════════════════════════════════════╝

def chunk_documents(docs: List[Dict[str, Any]]) -> List[Document]:
    """
    Split each document into overlapping chunks.
    Returns a flat list of LangChain Document objects.
    """
    _banner("STAGE 2 – Chunking")
    _in("documents", f"{len(docs)} docs, chunk_size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP}")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", " ", ""],
    )

    all_chunks: List[Document] = []
    for doc in docs:
        raw_chunks = splitter.split_text(doc["text"])
        for idx, chunk_text in enumerate(raw_chunks):
            chunk_id = f"{doc['doc_id']}_c{idx:04d}"
            lc_doc = Document(
                page_content=chunk_text,
                metadata={
                    **doc["metadata"],
                    "chunk_id":  chunk_id,
                    "chunk_idx": idx,
                },
            )
            all_chunks.append(lc_doc)
        log.info(
            f"  ✂  '{doc['file_name']}'  →  {len(raw_chunks)} chunks  "
            f"(doc_id={doc['doc_id']})"
        )

    _out("chunks", f"{len(all_chunks)} total chunks across all documents")
    return all_chunks


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  STAGE 3 – Embed & store in ChromaDB (persistent)                       ║
# ╚══════════════════════════════════════════════════════════════════════════╝

def embed_and_store(chunks: List[Document]) -> chromadb.Collection:
    """
    Embed every chunk with OpenAI text-embedding-3-small and upsert into
    a persistent ChromaDB collection called 'graphrag_chunks'.
    Returns the ChromaDB client for later queries.
    """
    _banner("STAGE 3 – Embedding & ChromaDB Storage")
    _in("chunks", f"{len(chunks)} chunks  →  persist_dir='{CHROMA_DIR}'")

    # Initialize ChromaDB persistent client
    os.makedirs(CHROMA_DIR, exist_ok=True)
    chroma_client = chromadb.PersistentClient(
        path=CHROMA_DIR,
        settings=ChromaSettings(anonymized_telemetry=False)
    )

    # Get or create collection
    collection = chroma_client.get_or_create_collection(
        name="graphrag_chunks",
        metadata={"hnsw:space": "cosine"}
    )

    # Get embeddings model
    embeddings_model = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=OPENAI_API_KEY,
    )

    # Embed and upsert in batches
    batch_size = 100
    total = len(chunks)
    for start in range(0, total, batch_size):
        batch = chunks[start : start + batch_size]
        ids   = [c.metadata["chunk_id"] for c in batch]
        texts = [c.page_content for c in batch]
        
        # Embed batch
        embeddings_list = embeddings_model.embed_documents(texts)
        
        # Prepare metadata
        metadatas = [c.metadata for c in batch]
        
        # Upsert to collection
        collection.upsert(
            ids=ids,
            embeddings=embeddings_list,
            metadatas=metadatas,
            documents=texts
        )
        log.info(f"  💾  Upserted chunks {start+1}–{min(start+batch_size, total)} / {total}")

    _out("vectordb", f"Collection 'graphrag_chunks' now contains {total} chunks")
    return collection


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  STAGE 4 – LLM: Chapter mapping + Keyword extraction per document       ║
# ╚══════════════════════════════════════════════════════════════════════════╝

CHAPTER_KEYWORD_PROMPT = """\
You are a document analysis expert.
You will receive ALL text chunks of a single document, each labeled [CHUNK_ID].
Your tasks:
1. Identify logical CHAPTERS / SECTIONS in the document.
2. Assign every chunk to exactly ONE chapter.
3. Extract 2-5 KEYWORDS from EACH chunk.

Return ONLY valid JSON – no markdown fences – in this exact schema:
{{
  "document_title": "<title or filename>",
  "chapters": [
    {{
      "chapter_id": "ch_01",
      "chapter_name": "<name>",
      "chunk_ids": ["<chunk_id>", ...]
    }}
  ],
  "chunk_keywords": {{
    "<chunk_id>": ["keyword1", "keyword2", ...]
  }}
}}
"""

def extract_chapters_and_keywords(
    doc: Dict[str, Any],
    chunks: List[Document],
) -> Dict[str, Any]:
    """
    Send all chunks of ONE document to the LLM.
    Returns chapter mapping + per-chunk keywords.
    """
    doc_chunks = [c for c in chunks if c.metadata["doc_id"] == doc["doc_id"]]

    _banner(f"STAGE 4 – Chapter & Keyword Extraction  [{doc['file_name']}]")
    _in("chunks_sent_to_llm", f"{len(doc_chunks)} chunks for doc '{doc['file_name']}'")

    # Build the message body: numbered chunk listing
    chunk_listing = ""
    for c in doc_chunks:
        chunk_listing += f"\n[{c.metadata['chunk_id']}]\n{c.page_content}\n"

    user_msg = (
        f"Document filename: {doc['file_name']}\n"
        f"Total chunks: {len(doc_chunks)}\n\n"
        + chunk_listing
    )

    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": CHAPTER_KEYWORD_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
        temperature=0.2,
    )

    raw = response.choices[0].message.content.strip()

    # Strip accidental markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    result = json.loads(raw)

    log.info(
        f"  📚  Chapters found: {len(result.get('chapters', []))}  |  "
        f"Chunks with keywords: {len(result.get('chunk_keywords', {}))}"
    )
    _out(
        "chapter_keyword_map",
        {
            "chapters": [ch["chapter_name"] for ch in result.get("chapters", [])],
            "sample_keywords": dict(
                list(result.get("chunk_keywords", {}).items())[:3]
            ),
        },
    )
    return result


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  STAGE 5 – Build Neo4j Graph (DKG + IKG)                                ║
# ╚══════════════════════════════════════════════════════════════════════════╝

def store_graph(
    doc: Dict[str, Any],
    chunks: List[Document],
    chapter_keyword_map: Dict[str, Any],
) -> None:
    """
    Persist the Document Knowledge Graph (DKG) and Information Knowledge
    Graph (IKG) into Neo4j.

    DKG nodes/edges:
        (:Document)-[:HAS_METADATA]->(:Metadata)
        (:Document)-[:HAS_CHAPTER]->(:Chapter)
        (:Chapter)-[:HAS_CHUNK]->(:Chunk)

    IKG nodes/edges:
        (:Chunk)-[:HAS_KEYWORD]->(:Keyword)
    """
    _banner(f"STAGE 5 – Neo4j Graph Storage  [{doc['file_name']}]")
    _in(
        "graph_payload",
        {
            "doc_id":    doc["doc_id"],
            "chapters":  len(chapter_keyword_map.get("chapters", [])),
            "kw_chunks": len(chapter_keyword_map.get("chunk_keywords", {})),
        },
    )

    chunk_map = {c.metadata["chunk_id"]: c for c in chunks}

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            # ── Document node ───────────────────────────────────────────
            session.run(
                """
                MERGE (d:Document {doc_id: $doc_id})
                SET d.file_name = $file_name,
                    d.title     = $title,
                    d.updated   = datetime()
                """,
                doc_id=doc["doc_id"],
                file_name=doc["file_name"],
                title=chapter_keyword_map.get("document_title", doc["file_name"]),
            )
            log.info(f"  🗂  Document node: {doc['doc_id']}")

            # ── Metadata node ───────────────────────────────────────────
            session.run(
                """
                MATCH (d:Document {doc_id: $doc_id})
                MERGE (m:Metadata {doc_id: $doc_id})
                SET m.source    = $source,
                    m.file_name = $file_name
                MERGE (d)-[:HAS_METADATA]->(m)
                """,
                doc_id=doc["doc_id"],
                source=doc["metadata"]["source"],
                file_name=doc["file_name"],
            )
            log.info("  🗂  Metadata node linked")

            # ── Chapter nodes ────────────────────────────────────────────
            for ch in chapter_keyword_map.get("chapters", []):
                session.run(
                    """
                    MATCH (d:Document {doc_id: $doc_id})
                    MERGE (c:Chapter {chapter_id: $chapter_id, doc_id: $doc_id})
                    SET c.name    = $name,
                        c.updated = datetime()
                    MERGE (d)-[:HAS_CHAPTER]->(c)
                    """,
                    doc_id=doc["doc_id"],
                    chapter_id=ch["chapter_id"],
                    name=ch["chapter_name"],
                )
                log.info(f"  📖  Chapter: '{ch['chapter_name']}'  ({len(ch['chunk_ids'])} chunks)")

                # ── Chunk nodes linked to chapter ────────────────────────
                for cid in ch["chunk_ids"]:
                    lc = chunk_map.get(cid)
                    text_preview = (lc.page_content[:120] + "…") if lc else ""
                    session.run(
                        """
                        MATCH (ch:Chapter {chapter_id: $chapter_id, doc_id: $doc_id})
                        MERGE (k:Chunk {chunk_id: $chunk_id})
                        SET k.doc_id      = $doc_id,
                            k.chapter_id  = $chapter_id,
                            k.text        = $text,
                            k.updated     = datetime()
                        MERGE (ch)-[:HAS_CHUNK]->(k)
                        """,
                        doc_id=doc["doc_id"],
                        chapter_id=ch["chapter_id"],
                        chunk_id=cid,
                        text=text_preview,
                    )

            # ── Keyword nodes (IKG) ──────────────────────────────────────
            kw_map = chapter_keyword_map.get("chunk_keywords", {})
            total_kw = 0
            for cid, keywords in kw_map.items():
                for kw in keywords:
                    session.run(
                        """
                        MATCH (c:Chunk {chunk_id: $chunk_id})
                        MERGE (k:Keyword {name: $kw})
                        MERGE (c)-[:HAS_KEYWORD]->(k)
                        """,
                        chunk_id=cid,
                        kw=kw.lower().strip(),
                    )
                    total_kw += 1

            log.info(f"  🔑  {total_kw} keyword relationships written (IKG)")

    finally:
        driver.close()

    _out("neo4j", "DKG + IKG stored successfully")


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  STAGE 6 – GraphRAG Retrieval                                           ║
# ╚══════════════════════════════════════════════════════════════════════════╝

def _vector_search(vectordb: chromadb.Collection, query: str, k: int = TOP_K_VECTOR) -> Tuple[List[str], List[str]]:
    """
    Return top-k similar chunks from ChromaDB.
    Returns (chunk_ids, texts)
    """
    # Embed the query
    embeddings_model = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=OPENAI_API_KEY,
    )
    query_embedding = embeddings_model.embed_query(query)
    
    # Query ChromaDB
    results = vectordb.query(
        query_embeddings=[query_embedding],
        n_results=k,
        include=["documents", "metadatas", "distances"]
    )
    
    chunk_ids = results["ids"][0] if results["ids"] else []
    texts = results["documents"][0] if results["documents"] else []
    
    return chunk_ids, texts


def _ics_retrieval(driver, chunk_ids: List[str]) -> List[str]:
    """
    Intra-Chapter Search (ICS):
    For each chunk, find its chapter, then return ALL chunk_ids in that chapter.
    """
    with driver.session() as s:
        result = s.run(
            """
            MATCH (ch:Chapter)-[:HAS_CHUNK]->(c:Chunk)
            WHERE c.chunk_id IN $chunk_ids
            WITH DISTINCT ch
            MATCH (ch)-[:HAS_CHUNK]->(sibling:Chunk)
            RETURN DISTINCT sibling.chunk_id AS chunk_id
            """,
            chunk_ids=chunk_ids,
        )
        return [r["chunk_id"] for r in result]


def _iks_retrieval(driver, chunk_ids: List[str]) -> List[str]:
    """
    Information Knowledge Search (IKS):
    Get keywords belonging to these chunks, then retrieve all chunks
    that share those keywords.
    """
    with driver.session() as s:
        result = s.run(
            """
            MATCH (c:Chunk)-[:HAS_KEYWORD]->(k:Keyword)<-[:HAS_KEYWORD]-(other:Chunk)
            WHERE c.chunk_id IN $chunk_ids
            RETURN DISTINCT other.chunk_id AS chunk_id
            """,
            chunk_ids=chunk_ids,
        )
        return [r["chunk_id"] for r in result]


def _uks_retrieval(driver, chunk_ids: List[str]) -> List[str]:
    """
    Unique Keyword Search (UKS):
    For each vector-retrieved chunk, find keywords that appear in only that chunk
    (unique keywords), then retrieve other chunks via those keywords.
    """
    with driver.session() as s:
        result = s.run(
            """
            MATCH (c:Chunk)-[:HAS_KEYWORD]->(k:Keyword)
            WHERE c.chunk_id IN $chunk_ids
            WITH k, count { (k)<-[:HAS_KEYWORD]-() } AS degree
            WHERE degree = 1
            MATCH (any_chunk:Chunk)-[:HAS_KEYWORD]->(k)
            RETURN DISTINCT any_chunk.chunk_id AS chunk_id
            """,
            chunk_ids=chunk_ids,
        )
        return [r["chunk_id"] for r in result]


def _fetch_chunk_texts(vectordb: chromadb.Collection, chunk_ids: List[str]) -> List[str]:
    """Retrieve chunk texts from ChromaDB by their IDs."""
    if not chunk_ids:
        return []
    result = vectordb.get(ids=chunk_ids, include=["documents"])
    return result.get("documents", [])


def graphrag_query(
    query: str,
    vectordb: chromadb.Collection,
    use_graph: bool = True,
) -> Dict[str, Any]:
    """
    Full GraphRAG retrieval + LLM answer pipeline.

    1. Vector search → top-k chunks
    2. ICS  – chapter siblings
    3. IKS  – keyword-linked chunks
    4. UKS  – unique-keyword chunks
    5. Combine & deduplicate
    6. LLM answer

    Args:
        query: The question to answer
        vectordb: ChromaDB collection
        use_graph: If True, use full GraphRAG (vector + ICS + IKS + UKS)
                   If False, use only vector DB results

    Returns:
        Dict with 'answer', 'method', 'counts', and 'context_chunks'
    """
    _banner("STAGE 6 – GraphRAG Query")
    _in("query", query)

    # ── Step 6.1  Vector retrieval ──────────────────────────────────────
    log.info("  [6.1] Vector DB similarity search …")
    vector_ids, vector_texts = _vector_search(vectordb, query, k=TOP_K_VECTOR)
    log.info(f"  ← Vector top-{TOP_K_VECTOR}: {vector_ids}")
    _out("vector_retrieval", vector_ids)

    counts = {
        "vector_db_chunks": len(vector_ids),
        "ics_chunks": 0,
        "iks_chunks": 0,
        "uks_chunks": 0,
        "total_combined": len(vector_ids),
    }

    # If using graph retrieval
    if use_graph:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        try:
            # ── Step 6.2  ICS ───────────────────────────────────────────────
            log.info("  [6.2] ICS  – Intra-Chapter Search …")
            _in("ICS/input_chunk_ids", vector_ids)
            ics_ids = _ics_retrieval(driver, vector_ids)
            ics_new = [i for i in ics_ids if i not in vector_ids]
            counts["ics_chunks"] = len(ics_new)
            log.info(f"  ← ICS: {len(ics_ids)} total, {len(ics_new)} new chunks")
            _out("ICS", ics_new)

            # ── Step 6.3  IKS ───────────────────────────────────────────────
            log.info("  [6.3] IKS  – Information Knowledge Search …")
            _in("IKS/input_chunk_ids", vector_ids)
            iks_ids = _iks_retrieval(driver, vector_ids)
            iks_new = [i for i in iks_ids if i not in vector_ids and i not in ics_ids]
            counts["iks_chunks"] = len(iks_new)
            log.info(f"  ← IKS: {len(iks_ids)} total, {len(iks_new)} new chunks")
            _out("IKS", iks_new)

            # ── Step 6.4  UKS ───────────────────────────────────────────────
            log.info("  [6.4] UKS  – Unique Keyword Search …")
            _in("UKS/input_chunk_ids", vector_ids)
            uks_ids = _uks_retrieval(driver, vector_ids)
            uks_new = [i for i in uks_ids if i not in vector_ids and i not in ics_ids and i not in iks_ids]
            counts["uks_chunks"] = len(uks_new)
            log.info(f"  ← UKS: {len(uks_ids)} total, {len(uks_new)} new chunks")
            _out("UKS", uks_new)

        finally:
            driver.close()

        # ── Step 6.5  Combine & deduplicate ────────────────────────────────
        all_ids = list(dict.fromkeys(vector_ids + ics_ids + iks_ids + uks_ids))
        counts["total_combined"] = len(all_ids)
        log.info(
            f"  [6.5] Combined unique chunk_ids: {counts['vector_db_chunks']} (vector) "
            f"+ {counts['ics_chunks']} (ICS) + {counts['iks_chunks']} (IKS) + {counts['uks_chunks']} (UKS) "
            f"= {counts['total_combined']} total"
        )
    else:
        all_ids = vector_ids
        log.info(f"  [6.5] Using ONLY vector DB results: {len(all_ids)} chunks (graph disabled)")

    # Fetch texts: build context from vector results + extra retrieval
    context_parts = []
    for vid, vtext in zip(vector_ids, vector_texts):
        context_parts.append(f"[{vid}]\n{vtext}")
    
    # Get remaining chunks
    extra_ids = [i for i in all_ids if i not in vector_ids]
    if extra_ids:
        extra_texts = _fetch_chunk_texts(vectordb, extra_ids)
        for eid, etxt in zip(extra_ids, extra_texts):
            context_parts.append(f"[{eid}]\n{etxt}")

    context = "\n\n---\n\n".join(context_parts)

    _in(
        "LLM/context",
        f"{len(context_parts)} chunks  |  {len(context):,} chars",
    )
    log.info(
        f"  [6.6] Sending {len(context_parts)} chunks ({len(context):,} chars) to LLM …"
    )

    # ── Step 6.6  LLM answer ────────────────────────────────────────────
    llm = ChatOpenAI(
        model="gpt-4",
        temperature=0.3,
        openai_api_key=OPENAI_API_KEY,
    )

    system_msg = SystemMessage(
        content=(
            "You are a knowledgeable assistant. Answer the user's question "
            "using ONLY the provided context chunks. "
            "Be concise, accurate, and cite chunk IDs where relevant."
        )
    )
    human_msg = HumanMessage(
        content=(
            f"Question:\n{query}\n\n"
            f"Context chunks:\n\n{context}"
        )
    )

    answer = llm.invoke([system_msg, human_msg]).content
    _out("LLM/answer", answer)

    return {
        "answer": answer,
        "method": "GraphRAG (Vector + Graph)" if use_graph else "Vector DB Only",
        "counts": counts,
        "context_chunks": len(context_parts),
        "context_chars": len(context),
    }


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  FULL PIPELINE ORCHESTRATOR                                             ║
# ╚══════════════════════════════════════════════════════════════════════════╝

def run_indexing_pipeline(file_paths: List[str]) -> chromadb.Collection:
    """
    Run the full indexing pipeline:
        Load → Chunk → Embed+Store → (per doc) Chapter/KW extraction → Neo4j graph
    Returns the populated ChromaDB collection handle.
    """
    log.info("")
    _banner("═  GraphRAG INDEXING PIPELINE  START  ═")

    # Stage 1 – Load
    docs = load_documents(file_paths)
    if not docs:
        raise RuntimeError("No documents loaded. Check your file paths.")

    # Stage 2 – Chunk
    chunks = chunk_documents(docs)

    # Stage 3 – Embed + ChromaDB
    vectordb = embed_and_store(chunks)

    # Stages 4 & 5 – per document
    for doc in docs:
        chapter_kw_map = extract_chapters_and_keywords(doc, chunks)
        store_graph(doc, chunks, chapter_kw_map)

    _banner("═  GraphRAG INDEXING PIPELINE  COMPLETE  ═")
    return vectordb


def run_query_pipeline(query: str, vectordb: chromadb.Collection, compare_mode: bool = False) -> None:
    """
    Run the GraphRAG retrieval + LLM answer pipeline for a single query.
    
    Args:
        query: The question to answer
        vectordb: ChromaDB collection
        compare_mode: If True, run both Vector-only and GraphRAG methods and compare
    """
    log.info("")
    
    if compare_mode:
        _banner("═  GraphRAG COMPARISON MODE  ═")
        
        # Method 1: Vector DB only
        log.info("")
        _banner("METHOD 1 – Vector DB Only")
        result_vector = graphrag_query(query, vectordb, use_graph=False)
        
        # Method 2: Full GraphRAG
        log.info("")
        _banner("METHOD 2 – GraphRAG (Vector + Graph)")
        result_graphrag = graphrag_query(query, vectordb, use_graph=True)
        
        # Comparison report
        log.info("")
        _banner("═  COMPARISON REPORT  ═")
        
        # Counts comparison
        log.info("RETRIEVAL STAGE COUNTS:")
        log.info(f"  Vector DB chunks: {result_vector['counts']['vector_db_chunks']}")
        log.info(f"  Graph additions:")
        log.info(f"    - ICS (Intra-Chapter):  {result_graphrag['counts']['ics_chunks']} new chunks")
        log.info(f"    - IKS (Info Knowledge):  {result_graphrag['counts']['iks_chunks']} new chunks")
        log.info(f"    - UKS (Unique Keyword):  {result_graphrag['counts']['uks_chunks']} new chunks")
        log.info(f"  Total Combined: {result_graphrag['counts']['total_combined']} chunks")
        log.info(f"  Graph Improvement: +{result_graphrag['counts']['total_combined'] - result_vector['counts']['vector_db_chunks']} chunks ({100 * (result_graphrag['counts']['total_combined'] - result_vector['counts']['vector_db_chunks']) / result_vector['counts']['vector_db_chunks']:.1f}% increase)")
        
        log.info("")
        log.info("CONTEXT SENT TO LLM:")
        log.info(f"  Vector-only: {result_vector['context_chunks']} chunks, {result_vector['context_chars']:,} chars")
        log.info(f"  GraphRAG:    {result_graphrag['context_chunks']} chunks, {result_graphrag['context_chars']:,} chars")
        
        # Answers
        log.info("")
        log.info("="*70)
        log.info("ANSWER (Vector DB Only):")
        log.info("="*70)
        log.info(textwrap.fill(result_vector['answer'], 70))
        
        log.info("")
        log.info("="*70)
        log.info("ANSWER (GraphRAG – Full Method):")
        log.info("="*70)
        log.info(textwrap.fill(result_graphrag['answer'], 70))
        
        log.info("")
        log.info("="*70)
        log.info("CONCLUSION:")
        log.info("="*70)
        log.info(f"Graph retrieval added {result_graphrag['counts']['total_combined'] - result_vector['counts']['vector_db_chunks']} extra chunks")
        log.info("\nCompare the answers above to see if the additional context improves quality.")
        
    else:
        # Standard mode: Full GraphRAG
        _banner("═  GraphRAG QUERY PIPELINE  START  ═")
        result = graphrag_query(query, vectordb, use_graph=True)
        _banner("═  GraphRAG QUERY PIPELINE  COMPLETE  ═")
        log.info(f"\n{'='*70}\nMETHOD: {result['method']}\nCHUNKS: {result['context_chunks']} (total {result['context_chars']:,} chars)\n")
        log.info(f"Retrieval details:")
        log.info(f"  • Vector DB:  {result['counts']['vector_db_chunks']} chunks")
        log.info(f"  • ICS graph:  +{result['counts']['ics_chunks']} chunks")
        log.info(f"  • IKS graph:  +{result['counts']['iks_chunks']} chunks")
        log.info(f"  • UKS graph:  +{result['counts']['uks_chunks']} chunks")
        log.info(f"{'='*70}\nFINAL ANSWER:\n{textwrap.fill(result['answer'], 70)}\n{'='*70}")


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  ENTRY POINT                                                            ║
# ╚══════════════════════════════════════════════════════════════════════════╝

if __name__ == "__main__":
    import sys

    # ── 1.  Resolve document paths ──────────────────────────────────────
    # Pass file paths as CLI args, e.g.
    #   python test1.py doc1.txt doc2.txt
    # Defaults to every *.txt in the same directory if no args given.
    if len(sys.argv) > 1:
        input_files = sys.argv[1:]
    else:
        here = Path(__file__).parent
        input_files = [str(p) for p in sorted(here.glob("*.txt"))]
        if not input_files:
            log.error(
                "No *.txt files found in the script directory and no CLI args given.\n"
                "Usage:  python test1.py <file1.txt> [file2.txt …]\n"
                "Or drop *.txt files next to test1.py and re-run."
            )
            sys.exit(1)

    log.info(f"Processing {len(input_files)} file(s): {[Path(f).name for f in input_files]}")

    # ── 2.  Index ───────────────────────────────────────────────────────
    vectordb = run_indexing_pipeline(input_files)

    # ── 3.  Interactive Q&A loop ────────────────────────────────────────
    print("\n" + "="*70)
    print("  GraphRAG is ready.  Type your question (or 'exit' to quit).")
    print("  Commands:")
    print("    exit/quit/q  – Exit the program")
    print("    compare      – Enter comparison mode (Vector-only vs GraphRAG)")
    print("="*70 + "\n")

    in_compare_mode = False
    
    while True:
        try:
            if in_compare_mode:
                prompt = "Compare> "
            else:
                prompt = "Question> "
            q = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break
        
        if not q:
            continue
            
        if q.lower() in {"exit", "quit", "q"}:
            print("Bye!")
            break
        
        if q.lower() == "compare":
            in_compare_mode = not in_compare_mode
            mode_status = "ON" if in_compare_mode else "OFF"
            print(f"\n✓ Comparison mode: {mode_status}\n")
            continue
        
        # Run query with current mode
        run_query_pipeline(q, vectordb, compare_mode=in_compare_mode)
        print()
