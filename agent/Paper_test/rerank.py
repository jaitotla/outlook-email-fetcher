
import sys
import os
import chromadb
from langchain_core.embeddings import Embeddings
from langchain_core.documents import Document
from langchain_cohere import CohereRerank
from dotenv import load_dotenv
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from agent.utils import call_embed_api


load_dotenv()


class CustomEmbeddingAPI(Embeddings):
    """Custom embedding class using call_embed_api from agent/utils.py"""
    
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed search docs."""
        embeddings = []
        for text in texts:
            embedding = call_embed_api(text)
            if isinstance(embedding, dict) and "error" in embedding:
                raise ValueError(f"Embedding error: {embedding['error']}")
            embeddings.append(embedding)
        return embeddings
    
    def embed_query(self, text: str) -> list[float]:
        """Embed query text."""
        embedding = call_embed_api(text)
        if isinstance(embedding, dict) and "error" in embedding:
            raise ValueError(f"Embedding error: {embedding['error']}")
        return embedding


# Connect to Chroma database
vector_db_path = "/home/ubuntu/openmailbot/openmailbot/agent/Paper_test/cdb_test"

# Use PersistentClient to connect/create database
chroma_client = chromadb.PersistentClient(path=vector_db_path)

# Get or create the collection
try:
    collection = chroma_client.get_collection(name="papers")
except:
    # Create new collection if it doesn't exist
    collection = chroma_client.create_collection(name="papers")

embedding_model = CustomEmbeddingAPI()

if collection:
    print(f"✓ Connected to Chroma database at: {vector_db_path}")
    print(f"✓ Collection '{collection.name}' ready for documents\n")


def clear_collection():
    """Delete all existing documents from the collection."""
    try:
        # Get all document IDs and delete them
        all_docs = collection.get()
        if all_docs['ids']:
            collection.delete(ids=all_docs['ids'])
            print(f"✓ Cleared {len(all_docs['ids'])} existing documents from collection\n")
    except Exception as e:
        print(f"✗ Error clearing collection: {str(e)}\n")


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> list[str]:
    """
    Split text into overlapping chunks.
    
    Args:
        text: Text to chunk
        chunk_size: Size of each chunk in characters
        overlap: Number of overlapping characters between chunks
    
    Returns:
        List of text chunks
    """
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        
        if chunk.strip():
            chunks.append(chunk)
        
        start = end - overlap
    
    return chunks


def load_and_store_txt_files_chunked(folder_path: str = ".", chunk_size: int = 500, overlap: int = 100):
    """
    Load all .txt files, chunk them, and store in Chroma.
    
    Args:
        folder_path: Path to folder containing txt files
        chunk_size: Size of each chunk in characters
        overlap: Overlap between chunks
    """
    txt_files = [f for f in os.listdir(folder_path) if f.endswith('.txt')]
    
    if not txt_files:
        print(f"✗ No .txt files found in {folder_path}")
        return
    
    print(f"\n{'='*60}")
    print(f"Loading and chunking {len(txt_files)} txt files")
    print(f"{'='*60}\n")
    
    chunk_counter = 0
    
    for filename in txt_files:
        filepath = os.path.join(folder_path, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            if not content:
                print(f"⚠ Skipped {filename}: Empty file")
                continue
            
            # Chunk the text
            chunks = chunk_text(content, chunk_size=chunk_size, overlap=overlap)
            
            print(f"\n📄 {filename} -> {len(chunks)} chunks")
            
            # Store each chunk
            for i, chunk in enumerate(chunks):
                chunk_id = f"{filename.replace('.txt', '')}_chunk_{i}"
                embedding = embedding_model.embed_query(chunk)
                
                collection.upsert(
                    ids=[chunk_id],
                    embeddings=[embedding],
                    metadatas={
                        "filename": filename,
                        "chunk_num": i,
                        "total_chunks": len(chunks),
                        "source": "paper_test"
                    },
                    documents=[chunk]
                )
                chunk_counter += 1
            
            print(f"   ✓ Stored {len(chunks)} chunks")
        
        except Exception as e:
            print(f"✗ Error processing {filename}: {str(e)}")
    
    print(f"\n{'='*60}")
    print(f"✓ Total chunks stored: {chunk_counter}")
    print(f"✓ Total documents in collection: {collection.count()}")
    print(f"{'='*60}\n")


def upsert_document(doc_id: str, text: str, metadata: dict = None):
    """
    Upsert a document into the Chroma collection.
    
    Args:
        doc_id: Unique document identifier
        text: Document text content
        metadata: Optional metadata dictionary for the document
    """
    if metadata is None:
        metadata = {}
    
    # Generate embedding using custom API
    embedding = embedding_model.embed_query(text)
    
    # Extract text from metadata if present, otherwise use provided text
    document = metadata.pop("text", "") if "text" in metadata else text
    
    # Upsert into collection
    collection.upsert(
        ids=[doc_id],
        embeddings=[embedding],
        metadatas=[metadata],
        documents=[document] if document else None
    )
    
    print(f"✓ Upserted document: {doc_id}")


def query_documents(query_text: str, k: int = 15):
    """
    Query the Chroma collection.
    
    Args:
        query_text: Query text
        k: Number of results to return
    
    Returns:
        List of matching documents with scores
    """
    query_embedding = embedding_model.embed_query(query_text)
    
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=k,
        include=["documents", "metadatas", "distances"]
    )
    
    return results


def rerank_results(results: dict, query_text: str, top_n: int = 5, api_key: str = None):
    """
    Rerank retrieved documents using Cohere reranker.
    
    Args:
        results: Query results from Chroma
        query_text: Original query text
        top_n: Number of top reranked results to return
        api_key: Cohere API key (optional, defaults to CO_API_KEY env var)
    
    Returns:
        List of reranked Document objects
    """
    if not results["documents"] or not results["documents"][0]:
        return []
    
    # Get API key from parameter or environment
    if api_key is None:
        api_key = os.getenv("CO_API_KEY") or os.getenv("COHERE_API_KEY")
    
    if not api_key:
        print("⚠ Warning: Cohere API key not found. Set CO_API_KEY or COHERE_API_KEY environment variable.")
        return []
    
    # Convert Chroma results to LangChain Document objects
    docs = results["documents"][0]
    ids = results.get("ids", [[]])[0] if "ids" in results else []
    metadatas = results.get("metadatas", [[]])[0] if "metadatas" in results else [{}] * len(docs)
    
    documents = []
    for doc_id, doc_text, metadata in zip(ids, docs, metadatas):
        if doc_text:
            doc = Document(
                page_content=doc_text,
                metadata={**metadata, "doc_id": doc_id}
            )
            documents.append(doc)
    
    if not documents:
        return []
    
    try:
        # Initialize Cohere reranker with API key
        reranker = CohereRerank(model="rerank-english-v3.0", top_n=top_n, cohere_api_key=api_key)
        
        # Rerank documents
        reranked_docs = reranker.compress_documents(documents, query_text)
        
        return reranked_docs
    except Exception as e:
        print(f"✗ Error during reranking: {str(e)}")
        return []


# Clear existing documents
print("STEP 0: Clearing existing documents")
print("-"*50)
clear_collection()

# Load and store chunked txt files from Paper_test folder
print("STEP 1: Loading and chunking txt files")
print("-"*50)
load_and_store_txt_files_chunked(folder_path=".", chunk_size=500, overlap=100)

# Test: Query the database
print("\n" + "="*60)
print("STEP 2: Testing query functionality")
print("="*60)

query = "what about hotel website client side code?"

print("\nVector Search Results")
print("-"*50)

results = query_documents(query, k=10)

print("\n" + "="*80)
print("INITIAL VECTOR SEARCH RESULTS (Before Reranking):")
print("="*80 + "\n")

if results["documents"] and results["documents"][0]:
    docs = results["documents"][0]
    distances = results["distances"][0]
    
    for i, (doc, distance) in enumerate(zip(docs, distances), 1):
        if doc:
            print(f"{i}. [Score: {1-distance:.4f}] {doc[:150]}...\n")
else:
    print("No documents found.")

print("\n" + "="*80)
print("RERANKED RESULTS (Top 5):")
print("="*80 + "\n")

# Rerank the retrieved documents
# NOTE: You can also add COHERE_API_KEY or CO_API_KEY to your .env file instead of hardcoding it here
cohere_api_key = "TBBNOMFg1fZvpd2fhMBw9GbhUFQCEuOQAVlis2pw"
reranked_docs = rerank_results(results, query, top_n=5, api_key=cohere_api_key)

if reranked_docs:
    for i, doc in enumerate(reranked_docs, 1):
        print(f"{i}. {doc.page_content[:200]}...")
        print(f"   Metadata: {doc.metadata}\n")
else:
    print("No documents to rerank.")