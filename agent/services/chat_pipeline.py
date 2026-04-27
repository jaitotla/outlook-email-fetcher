import os
import json
import sqlite3
from pathlib import Path
import chromadb
from llama_index.core import SimpleDirectoryReader
from llama_index.readers.file import PDFReader, CSVReader, PptxReader
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
import requests
from typing import Dict, List, Optional, Set
import logging
from datetime import datetime
import ollama
import asyncio
import traceback
import re
from services.embeddings import EmbeddingService
from services.llm import LLMService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration
def _load_config() -> dict:
    """Load config from relative path, fall back to empty dict gracefully."""
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "config.json"),
        os.path.join(os.path.dirname(__file__), "config.json"),
        os.getenv("OPENMAILBOT_CONFIG_PATH", ""),
    ]
    for path in candidates:
        path = os.path.abspath(path)
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}

CONFIG = _load_config()

# Import settings manager for encrypted DB-based settings
from services.settings_manager import SettingsManager


# Constants
# Base data directory under the agent package: agent/data/{user_id}/...
BASE_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
# Backwards-compatible alias
# Backwards-compatible alias
BASE_PATH = BASE_DATA_DIR
FLASK_EMBED_URL = CONFIG.get('FLASK_EMBED_URL', 'https://lsdiedb39c.pagekite.me/embed')
OPENAI_KEY = CONFIG.get('OPENAI_KEY')

# Ollama / Flask API settings
FLASK_URL = CONFIG.get('FLASK_URL', 'https://lsdiedb39c.pagekite.me/')
OLLAMA_MODEL = "llama3.2"
OLLAMA_TEMP = 0.4

# File readers configuration
FILE_EXTRACTOR = {
    ".pdf": PDFReader(),
    ".csv": CSVReader(),

}


def sanitize_namespace(namespace: str) -> str:
    """Sanitize namespace to be ChromaDB-compliant.
    
    ChromaDB only allows: [a-zA-Z0-9._-]
    Replaces invalid characters with underscores.
    """
    # Replace @ with . and : with _
    sanitized = namespace.replace('@', '.').replace(':', '_')
    # Remove any other invalid characters
    sanitized = re.sub(r'[^a-zA-Z0-9._\-]', '_', sanitized)
    return sanitized


def call_ollama_chat_params(modelName=None, sysPrompt=None, usrPrompt=None, temp=None, timeout_seconds: int = 300):
    """Call the configured Flask Ollama `/chat` endpoint.

    Returns a dict matching the previous shape so callers can read
    `resp["message"]["content"]`.
    """
    # Build prompt from system + user prompts when provided
    if sysPrompt or usrPrompt:
        prompt = (sysPrompt or "") + "\n\n" + (usrPrompt or "")
    else:
        prompt = ""

    url = FLASK_URL.rstrip('/') + '/chat'
    try:
        res = requests.post(url, json={"prompt": prompt}, timeout=timeout_seconds)
        res.raise_for_status()
        data = res.json()
        # If the Flask service returns a `response` field, map it to the old structure
        if isinstance(data, dict) and "response" in data:
            return {"message": {"content": data["response"]}}
        # Otherwise wrap the whole payload
        return {"message": {"content": data}}
    except Exception as e:
        # Preserve expected return shape on error
        return {"message": {"content": str(e)}}


class ChatWithThreadPipeline:
    """Pipeline for chatting with email threads using RAG"""
    
    def __init__(self, user_id: Optional[str] = None, effective_settings: Optional[Dict] = None):
        # Optionally accept a user_id to scope operations; many methods still accept user_id
        self.user_id = user_id
        # keep a global fallback DB under BASE_DATA_DIR
        self.db_path = os.path.join(BASE_DATA_DIR, "chat_thread_processing.db")
        self.setup_database()
        
        # Load effective settings - either from parameter or retrieve from encrypted DB
        if effective_settings:
            self.effective_settings = effective_settings
        elif user_id:
            # Load from encrypted DB storage
            settings_manager = SettingsManager(user_id)
            retrieved_settings = settings_manager.get_settings(setting_type="general")
            logger.info(f" these are setttings {retrieved_settings}")
            self.effective_settings = retrieved_settings if retrieved_settings else {}
        else:
            # Fallback to empty dict
            self.effective_settings = {}

        # Apply inbuilt defaults for any critical fields that are missing/empty.
        # This ensures the pipeline works even if the user hasn't completed onboarding
        # or the settings sync to the backend failed for some reason.
        _INBUILT_DEFAULTS = {
            "vector_provider"    : "inbuilt",
            "embedding_provider" : "inbuilt",
            "llm_provider"       : "inbuilt",
            "embedding_model"    : "text-embedding-3-small",
            "llm_model"          : "gpt-4o-mini",
        }
        for _key, _default in _INBUILT_DEFAULTS.items():
            if not self.effective_settings.get(_key):
                self.effective_settings[_key] = _default
                logger.info(f"Settings default applied: {_key}={_default}")

        self.llm_provider = self.effective_settings.get("llm_provider", "inbuilt")
        self.llm_model = self.effective_settings.get("llm_model", "gpt-4o-mini")
        
        # Initialize LLMService for all LLM operations
        try:
            # Pass effective_settings to LLMService constructor
            self.llm_service = LLMService(effective_settings=self.effective_settings)
            logger.info("✅ LLMService initialized successfully")
            logger.info(f"   LLM Provider: {self.llm_provider}")
            logger.info(f"   LLM Model: {self.llm_model}")
        except Exception as e:
            logger.error(f"Failed to initialize LLMService: {e}")
            raise
        
        # Keep OpenAI tool caller for inbuilt mode (tool calling requires OpenAI)
        # For other providers, we'll use LLMService with appropriate fallback
        if self.llm_provider == "inbuilt":
            self.tool_caller_llm = ChatOpenAI(
                model="gpt-5-mini",
            
                api_key=OPENAI_KEY
            )
            logger.info("✅ OpenAI tool caller initialized for inbuilt mode")
        else:
            self.tool_caller_llm = None
            logger.info(f"✅ Using {self.llm_provider} for all operations (including tool calling)")
        
        # Initialize EmbeddingService for embeddings and vector operations
        try:
            self.embedding_service = EmbeddingService({
                        **(self.effective_settings or {}),
                        "user_id": user_id
                    })
            logger.info("✅ EmbeddingService initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize EmbeddingService: {e}")
            raise
    
    def setup_database(self):
        """Initialize SQLite database for tracking processed emails and attachments"""
        os.makedirs(BASE_PATH, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table for email embeddings
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                thread_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                processed_status TEXT DEFAULT 'completed',
                chroma_collection TEXT,
                UNIQUE(user_id, thread_id, message_id)
            )
        ''')
        
        # Table for attachment processing
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attachment_processing (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                thread_id TEXT NOT NULL,
                message_id TEXT,
                attachment_id TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                processed_status TEXT DEFAULT 'pending',
                processed_timestamp DATETIME,
                chroma_collection TEXT,
                metadata TEXT,
                UNIQUE(user_id, thread_id, attachment_id)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")

    def ensure_user_db(self, user_id: str):
        """Ensure per-user sqlite DB and tables exist."""
        user_db = os.path.join(BASE_DATA_DIR, user_id, "sql_data", "chat_thread_processing.db")
        os.makedirs(os.path.dirname(user_db), exist_ok=True)
        conn = sqlite3.connect(user_db)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                thread_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                processed_status TEXT DEFAULT 'completed',
                chroma_collection TEXT,
                UNIQUE(user_id, thread_id, message_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attachment_processing (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                thread_id TEXT NOT NULL,
                message_id TEXT,
                attachment_id TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                processed_status TEXT DEFAULT 'pending',
                processed_timestamp DATETIME,
                chroma_collection TEXT,
                metadata TEXT,
                UNIQUE(user_id, thread_id, attachment_id)
            )
        ''')

        conn.commit()
        conn.close()
        logger.info(f"Initialized per-user DB at {user_db}")

    def clear_thread_embeddings(self, user_id: str, thread_id: str):
        """Clear per-user DB records and remove vector entries for a thread."""
        logger.info(f"🧹 Clearing embeddings for thread {thread_id} (user: {user_id})")
        # Ensure DB exists
        self.ensure_user_db(user_id)

        user_db = os.path.join(BASE_DATA_DIR, user_id, "sql_data", "chat_thread_processing.db")
        conn = sqlite3.connect(user_db)
        cursor = conn.cursor()

        cursor.execute('''
            DELETE FROM email_embeddings
            WHERE user_id = ? AND thread_id = ?
        ''', (user_id, thread_id))
        deleted_emails = cursor.rowcount

        cursor.execute('''
            DELETE FROM attachment_processing
            WHERE user_id = ? AND thread_id = ?
        ''', (user_id, thread_id))
        deleted_attachments = cursor.rowcount

        conn.commit()
        conn.close()

        # Try to delete vectors from Chroma collection
        try:
            collection = self.get_user_collection(user_id)
            # Chroma client delete API may vary; use where filter if supported
            collection.delete(where={"thread_id": thread_id})
        except Exception as e:
            logger.warning(f"Could not delete vectors from Chroma for thread {thread_id}: {e}")

        logger.info(f"✅ Cleared {deleted_emails} emails and {deleted_attachments} attachments for thread {thread_id}")
        return {"emails_cleared": deleted_emails, "attachments_cleared": deleted_attachments}
    
    def get_user_chroma_client(self, user_id: str):
        """Get or create ChromaDB client for a specific user"""
        # Use per-user vector DB directory: data/{user_id}/vector_db/
        user_vector_path = os.path.join(BASE_DATA_DIR, user_id, "vector_db")
        logger.info(f"look where is datais stored {user_vector_path}")
        os.makedirs(user_vector_path, exist_ok=True)
        # keep a consistent folder name inside the user's vector_db
        user_chroma_path = os.path.join(user_vector_path, f"cdb_{user_id}")
        os.makedirs(user_chroma_path, exist_ok=True)
        return chromadb.PersistentClient(path=user_chroma_path)
    
    def get_user_collection(self, user_id: str, collection_name: str = "email_threads"):
        """Get or create collection for a user's email threads"""
        client = self.get_user_chroma_client(user_id)
        return client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
    
    def _run_async_task(self, coro):
        """
        Run an async coroutine from sync context safely.
        Always runs in a fresh event loop in a new thread to avoid
        conflicts with FastAPI's running event loop.
        """
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self._run_in_new_loop, coro)
            return future.result()  # blocks calling thread, not event loop

    def _run_in_new_loop(self, coro):
        """Run coroutine in a brand-new event loop (called from worker thread)."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
            asyncio.set_event_loop(None)
    
    def _get_embedding_sync(self, text: str) -> List[float]:
        """Synchronous wrapper for async embedding generation"""
        try:
            embedding = self._run_async_task(self.embedding_service.generate_embedding(text))
            return embedding
        except Exception as e:
            logger.error(f"Embedding generation error: {e}")
            raise
    
    def get_existing_message_ids_from_chroma(self, user_id: str, thread_id: str) -> Set[str]:
        """Get all existing message IDs for a thread from ChromaDB"""
        try:
            collection = self.get_user_collection(user_id)
            
            results = collection.get(
                where={
                    "$and": [
                        {"thread_id": thread_id},
                        {"type": "email_data"}
                    ]
                },
                include=["metadatas"]
            )
            
            existing_message_ids = {
                meta["message_id"]
                for meta in results.get("metadatas", [])
                if "message_id" in meta
            }
            
            logger.info(f"Found {len(existing_message_ids)} existing messages in ChromaDB for thread {thread_id}")
            return existing_message_ids
            
        except Exception as e:
            logger.error(f"Error fetching existing message IDs: {e}")
            return set()
    
    def load_thread_data(self, user_id: str, thread_id: str) -> Optional[Dict]:
        """Load thread data from single JSON file under user's `log_emails` directory"""
        file_path = os.path.join(BASE_DATA_DIR, user_id, "log_emails", thread_id, f"{thread_id}.json")

        try:
            if not os.path.exists(file_path):
                logger.warning(f"Thread file not found: {file_path}")
                return None

            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading thread JSON {file_path}: {e}")
            return None
    
    def get_thread_messages(self, user_id: str, thread_id: str) -> List[Dict]:
        """Get all messages from thread JSON file (user-scoped)"""
        thread_data = self.load_thread_data(user_id, thread_id)

        if not thread_data:
            logger.warning(f"No thread data found for thread {thread_id}")
            return []

        messages = thread_data.get('messages', [])
        logger.info(f"Found {len(messages)} messages in thread {thread_id}")
        return messages
    
    def get_existing_message_ids_from_db(self, user_id: str, thread_id: str) -> Set[str]:
        """Get all already-processed message IDs for a thread from the SQLite DB."""
        self.ensure_user_db(user_id)
        user_db = os.path.join(BASE_DATA_DIR, user_id, "sql_data", "chat_thread_processing.db")
        conn = sqlite3.connect(user_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT message_id FROM email_embeddings WHERE user_id = ? AND thread_id = ? AND processed_status = 'completed'",
            (user_id, thread_id)
        )
        rows = cursor.fetchall()
        conn.close()
        ids = {row[0] for row in rows}
        logger.info(f"Found {len(ids)} already-processed messages in DB for thread {thread_id}")
        return ids

    def get_unprocessed_messages(self, user_id: str, thread_id: str) -> List[Dict]:
        """Filter out already processed messages and return unprocessed ones"""
        existing_message_ids = self.get_existing_message_ids_from_db(user_id, thread_id)
        all_messages = self.get_thread_messages(user_id, thread_id)
        
        unprocessed_messages = [
            msg for msg in all_messages 
            if msg.get('message_id') not in existing_message_ids
        ]
        
        logger.info(f"Unprocessed messages: {len(unprocessed_messages)} out of {len(all_messages)}")
        return unprocessed_messages
    
    def process_email_message(self, user_id: str, thread_id: str, message_data: Dict):
        """Process a single email message and store embeddings"""
        message_id = message_data.get('message_id', 'unknown')
        logger.info(f"Processing email message: {message_id}")
        
        try:
            subject = message_data.get('subject', '')
            body = message_data.get('body', '')
            timestamp = message_data.get('timestamp', '')
            from_email = message_data.get('from', '')
            
            to_email = message_data.get('to', '')
            if isinstance(to_email, list):
                to_email = ', '.join(to_email) if to_email else ''
            elif not isinstance(to_email, str):
                to_email = str(to_email)
            
            text_to_embed = f"Subject: {subject}\n\nBody: {body}".strip()
            
            # Debug logs
            logger.debug(f"  Subject: {subject}")
            logger.debug(f"  Body: {body}")
            logger.debug(f"  Text to embed length: {len(text_to_embed)} chars")
            
            if not text_to_embed or text_to_embed == "Subject: \n\nBody: ":
                logger.warning(f"Empty content for message {message_id}")
                return
            
            metadata = {
                "thread_id": thread_id,
                "message_id": message_id,
                "timestamp": timestamp,
                "type": "email_data",
                "subject": subject,
                "from": from_email,
                "to": to_email,
                "document": text_to_embed
            }
            
            logger.debug(f"  Metadata document field: {text_to_embed[:200]}...")
            
            # Generate embedding using EmbeddingService
            embedding = self._get_embedding_sync(text_to_embed)
            doc_id = f"{user_id}_{thread_id}_{message_id}"
            
            # Store embedding in vector database via EmbeddingService
            namespace = sanitize_namespace(f"{user_id}_email_threads")
            self._run_async_task(self.embedding_service.store_embedding(
                embedding=embedding,
                metadata=metadata,
                namespace=namespace,
                vector_id=doc_id
            ))
            
            self.mark_message_processed(user_id, thread_id, message_id)
            logger.info(f"✅ Message {message_id} processed and stored successfully")
            
        except Exception as e:
            logger.error(f"Error processing message {message_id}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    def mark_message_processed(self, user_id: str, thread_id: str, message_id: str):
        """Mark message as processed in database"""
        # Ensure per-user DB has required tables
        self.ensure_user_db(user_id)
        # Use per-user sqlite DB under data/{user_id}/sql_data/
        user_db = os.path.join(BASE_DATA_DIR, user_id, "sql_data", "chat_thread_processing.db")
        os.makedirs(os.path.dirname(user_db), exist_ok=True)
        conn = sqlite3.connect(user_db)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO email_embeddings 
            (user_id, thread_id, message_id, processed_status, chroma_collection)
            VALUES (?, ?, ?, 'completed', 'email_threads')
        ''', (user_id, thread_id, message_id))
        
        conn.commit()
        conn.close()
    
    def check_attachment_processed(self, user_id: str, thread_id: str, attachment_id: str) -> bool:
        """Check if attachment is already processed"""
        # Ensure per-user DB has required tables
        self.ensure_user_db(user_id)
        user_db = os.path.join(BASE_DATA_DIR, user_id, "sql_data", "chat_thread_processing.db")
        os.makedirs(os.path.dirname(user_db), exist_ok=True)
        conn = sqlite3.connect(user_db)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT processed_status FROM attachment_processing
            WHERE user_id = ? AND thread_id = ? AND attachment_id = ?
        ''', (user_id, thread_id, attachment_id))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return result[0] == 'completed'
        return False
    
    def get_thread_attachments(self, user_id: str, thread_id: str) -> List[Dict]:
        """Get all attachments for a thread from the user's `store_attachments` directory"""
        thread_path = os.path.join(BASE_DATA_DIR, user_id, "store_attachments", thread_id)
        
        if not os.path.exists(thread_path):
            logger.warning(f"No attachments found for thread: {thread_id}")
            return []
        
        attachments = []
        for file in os.listdir(thread_path):
            if file.endswith('_metadata.json'):
                metadata_file = os.path.join(thread_path, file)
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                        for att in metadata.get('attachments', []):
                            if 'error' not in att:
                                attachments.append({
                                    'filename': att.get('filename'),
                                    'path': att.get('filepath'),
                                    'attachment_id': att.get('filename'),
                                    'message_id': metadata.get('message_id')
                                })
                except Exception as e:
                    logger.error(f"Error reading metadata file {metadata_file}: {e}")
        
        if not attachments:
            for file in os.listdir(thread_path):
                if not file.endswith('_metadata.json'):
                    attachments.append({
                        'filename': file,
                        'path': os.path.join(thread_path, file),
                        'attachment_id': file
                    })
        
        return attachments
    
    def process_attachment(self, user_id: str, thread_id: str, message_id: str, 
                          attachment_path: str, attachment_id: str):
        """Process a single attachment and store embeddings"""
        logger.info(f"Processing attachment: {attachment_path}")
        
        try:
            # Step 1: Extract content from attachment
            logger.info(f"  📖 Extracting content from {os.path.basename(attachment_path)}")
            documents = SimpleDirectoryReader(
                input_files=[attachment_path],
                file_extractor=FILE_EXTRACTOR
            ).load_data()
            
            if not documents:
                logger.warning(f"⚠️  No content extracted from {attachment_path}")
                return
            
            logger.info(f"  ✓ Extracted {len(documents)} documents from attachment")
            
            collection = self.get_user_collection(user_id)
            chunk_count = 0
            
            # Step 2: Process each extracted document/chunk
            for idx, doc in enumerate(documents):
                text = doc.text.strip() if doc.text else ""
                
                if not text:
                    logger.debug(f"  ⚠️  Document {idx} has empty text, skipping...")
                    continue
                
                logger.debug(f"  📝 Processing chunk {idx}: {len(text)} chars")
                
                metadata = {
                    "message_id": message_id,
                    "thread_id": thread_id,
                    "attachment_id": attachment_id,
                    "filename": os.path.basename(attachment_path),
                    "chunk_index": str(idx),
                    "type": "attachment_data",
                    "document": text
                }
                
                # Step 3: Generate embedding using EmbeddingService
                try:
                    embedding = self._get_embedding_sync(text)
                    doc_id = f"{user_id}_{thread_id}_{attachment_id}_{idx}"
                    
                    # Step 4: Store in vector database via EmbeddingService
                    namespace = sanitize_namespace(f"{user_id}_email_threads")
                    self._run_async_task(self.embedding_service.store_embedding(
                        embedding=embedding,
                        metadata=metadata,
                        namespace=namespace,
                        vector_id=doc_id
                    ))
                    
                    chunk_count += 1
                    logger.info(f"  ✓ Stored chunk {idx} (id: {doc_id})")
                    
                except Exception as embed_error:
                    logger.error(f"  ✗ Failed to embed chunk {idx}: {embed_error}")
                    raise
            
            if chunk_count == 0:
                logger.warning(f"⚠️  No chunks stored for attachment {attachment_id}")
                return
            
            # Step 5: Mark as processed
            self.mark_attachment_processed(user_id, thread_id, message_id, attachment_id)
            logger.info(f"✅ Attachment {attachment_id} processed: {chunk_count} chunks stored")
            
        except Exception as e:
            logger.error(f"❌ Error processing attachment {attachment_path}: {e}")
            import traceback
            logger.error(f"  Traceback: {traceback.format_exc()}")
            raise
    
    def mark_attachment_processed(self, user_id: str, thread_id: str, 
                                  message_id: str, attachment_id: str):
        """Mark attachment as processed in database"""
        # Ensure per-user DB has required tables
        self.ensure_user_db(user_id)
        user_db = os.path.join(BASE_DATA_DIR, user_id, "sql_data", "chat_thread_processing.db")
        os.makedirs(os.path.dirname(user_db), exist_ok=True)
        conn = sqlite3.connect(user_db)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO attachment_processing 
            (user_id, thread_id, message_id, attachment_id, processed_status, processed_timestamp)
            VALUES (?, ?, ?, ?, 'completed', CURRENT_TIMESTAMP)
        ''', (user_id, thread_id, message_id, attachment_id))
        
        conn.commit()
        conn.close()
    
    def process_thread_emails(self, user_id: str, thread_id: str) -> Dict:
        """Process all unprocessed emails in a thread"""
        logger.info(f"🚀 Processing thread emails for user: {user_id}, thread: {thread_id}")
        
        processing_info = {
            'total_messages': 0,
            'already_processed': 0,
            'newly_processed': 0,
            'errors': []
        }
        
        try:
            all_messages = self.get_thread_messages(user_id, thread_id)
            processing_info['total_messages'] = len(all_messages)
            
            unprocessed_messages = self.get_unprocessed_messages(user_id, thread_id)
            processing_info['already_processed'] = len(all_messages) - len(unprocessed_messages)
            
            for message_data in unprocessed_messages:
                try:
                    self.process_email_message(user_id, thread_id, message_data)
                    processing_info['newly_processed'] += 1
                except Exception as e:
                    message_id = message_data.get('message_id', 'unknown')
                    error_msg = f"Failed to process message {message_id}: {str(e)}"
                    logger.error(error_msg)
                    processing_info['errors'].append(error_msg)
            
            logger.info(f"✅ Thread processing completed: {processing_info}")
            return processing_info
            
        except Exception as e:
            logger.error(f"Thread processing error: {e}")
            processing_info['errors'].append(str(e))
            return processing_info
    
    def process_thread_attachments(self, user_id: str, thread_id: str, message_id: str = None) -> Dict:
        """Process all unprocessed attachments in a thread"""
        logger.info(f"📎 Processing attachments for thread {thread_id}")
        
        attachment_info = {
            'attachments_found': 0,
            'attachments_processed': 0,
            'attachments_skipped': 0,
            'chunks_stored': 0,
            'errors': []
        }
        
        try:
            attachments = self.get_thread_attachments(user_id, thread_id)
            attachment_info['attachments_found'] = len(attachments)
            
            logger.info(f"Found {len(attachments)} attachments for thread {thread_id}")
            
            for attachment in attachments:
                attachment_id = attachment.get('attachment_id') or attachment.get('filename')
                attachment_path = attachment.get('path')
                attach_message_id = attachment.get('message_id', message_id or thread_id)
                
                logger.info(f"\n  Processing: {attachment_id}")
                logger.info(f"  Path: {attachment_path}")
                
                # Validate path
                if not attachment_path:
                    logger.warning(f"  ⚠️  No path provided for {attachment_id}")
                    continue
                
                if not os.path.exists(attachment_path):
                    logger.warning(f"  ⚠️  File not found: {attachment_path}")
                    continue
                
                # Check if already processed
                if self.check_attachment_processed(user_id, thread_id, attachment_id):
                    logger.info(f"  ⏭️  Already processed, skipping")
                    attachment_info['attachments_skipped'] += 1
                    continue
                
                # Process attachment
                try:
                    logger.info(f"  🔄 Processing {attachment_id}...")
                    self.process_attachment(
                        user_id, thread_id, attach_message_id,
                        attachment_path, attachment_id
                    )
                    attachment_info['attachments_processed'] += 1
                    
                except Exception as e:
                    error_msg = f"Failed to process {attachment_id}: {str(e)}"
                    logger.error(f"  ✗ {error_msg}")
                    attachment_info['errors'].append(error_msg)
                    continue
            
            logger.info(f"\n✅ Attachment processing completed:")
            logger.info(f"  - Found: {attachment_info['attachments_found']}")
            logger.info(f"  - Processed: {attachment_info['attachments_processed']}")
            logger.info(f"  - Skipped: {attachment_info['attachments_skipped']}")
            logger.info(f"  - Errors: {len(attachment_info['errors'])}")
            
            return attachment_info
            
        except Exception as e:
            logger.error(f"❌ Attachment processing error: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            attachment_info['errors'].append(str(e))
            return attachment_info
    
    def _search_thread_emails_internal(self, user_id: str, thread_id: str, 
                                       query: str, k: int = 5) -> str:
        """Internal method to search email messages"""
        logger.info(f"🔍 Searching emails: {query}")
        
        try:
            # Generate query embedding using EmbeddingService
            query_embedding = self._get_embedding_sync(query)
            namespace = sanitize_namespace(f"{user_id}_email_threads")
            
            # Search for similar embeddings
            filter_condition = {
                "$and": [
                    {"thread_id": thread_id},
                    {"type": "email_data"}
                ]
            }
            
            results = self._run_async_task(self.embedding_service.find_similar(
                embedding=query_embedding,
                namespace=namespace,
                limit=k,
                filter=filter_condition
            ))
            
            # Extract results in expected format
            # Note: "document" is stored in metadata, not at top level
            docs = [r.get("metadata", {}).get("document", r.get("text", r.get("document", ""))) for r in results]
            metadatas = [r.get("metadata", {}) for r in results]
            distances = [r.get("distance", 0) for r in results]
            
            logger.debug(f"📊 Search results: {len(results)} documents found")
            for idx, r in enumerate(results):
                logger.debug(f"  Result {idx}: {r}")
        except Exception as e:
            logger.error(f"Search error: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return "Error searching emails. Please try again."
        
        if not docs:
            return "No relevant emails found for your query."
        
        response_parts = []
        for idx, (doc, meta, distance) in enumerate(zip(docs, metadatas, distances), 1):
            timestamp = meta.get('timestamp', 'Unknown')
            from_email = meta.get('from', 'Unknown')
            subject = meta.get('subject', 'No subject')
            message_id = meta.get('message_id', 'Unknown')
            
            # Debug log for content
            logger.debug(f"  Email {idx} content length: {len(doc)} chars (content: {doc[:100] if doc else 'EMPTY'}...)")
            
            response_parts.append(
                f"📧 Email {idx} (Relevance: {1-distance:.2f})\n"
                f"Message ID: {message_id}\n"
                f"From: {from_email}\n"
                f"Subject: {subject}\n"
                f"Time: {timestamp}\n"
                f"Content:\n{doc}\n"
                f"{'-'*80}\n"
            )
        
        return "\n".join(response_parts)
    
    def _search_attachments_internal(self, user_id: str, thread_id: str, 
                                    query: str, k: int = 3) -> str:
        """Internal method to search attachment content"""
        logger.info(f"🔍 Searching attachments: {query}")
        
        try:
            # Generate query embedding using EmbeddingService
            query_embedding = self._get_embedding_sync(query)
            namespace = sanitize_namespace(f"{user_id}_email_threads")
            
            # Search for similar embeddings
            filter_condition = {
                "$and": [
                    {"thread_id": thread_id},
                    {"type": "attachment_data"}
                ]
            }
            
            results = self._run_async_task(self.embedding_service.find_similar(
                embedding=query_embedding,
                namespace=namespace,
                limit=k,
                filter=filter_condition
            ))
            
            # Extract results in expected format
            # Note: "document" is stored in metadata, not at top level
            docs = [r.get("metadata", {}).get("document", r.get("text", r.get("document", ""))) for r in results]
            metadatas = [r.get("metadata", {}) for r in results]
            distances = [r.get("distance", 0) for r in results]
            
            logger.debug(f"📊 Attachment search results: {len(results)} documents found")
            for idx, r in enumerate(results):
                logger.debug(f"  Result {idx}: {r}")
        except Exception as e:
            logger.error(f"Search error: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return "Error searching attachments. Please try again."
        
        if not docs:
            return "No relevant information found in attachments."
        
        response_parts = []
        for idx, (doc, meta, distance) in enumerate(zip(docs, metadatas, distances), 1):
            filename = meta.get('filename', 'Unknown')
            chunk_index = meta.get('chunk_index', '0')
            
            # Debug log for content
            logger.debug(f"  Document {idx} content length: {len(doc)} chars (content: {doc[:100] if doc else 'EMPTY'}...)")
            
            response_parts.append(
                f"📎 Document {idx} (Relevance: {1-distance:.2f})\n"
                f"From: {filename} (chunk {chunk_index})\n"
                f"Content:\n{doc}\n"
                f"{'-'*80}\n"
            )
        
        return "\n".join(response_parts)
    
    def create_tools_for_binding(self):
        """Create tool definitions for LLM binding"""
        
        @tool
        def search_thread_emails(query: str, k: int = 5) -> str:
            """
            Search email messages in the thread using semantic search.
            Use this when you need to find specific information or emails.
            
            Args:
                query: What you're searching for in the emails
                k: Number of relevant emails to retrieve (default: 5)
            """
            return "Tool placeholder - will be executed separately"
        
        @tool
        def search_attachments(query: str, k: int = 3) -> str:
            """
            Search attachment content using semantic search.
            Use this when you need specific information from documents.
            
            Args:
                query: What information you're looking for in attachments
                k: Number of relevant chunks to retrieve (default: 3)
            """
            return "Tool placeholder - will be executed separately"
        
        return [search_thread_emails, search_attachments]
    
    def chat_with_thread_hybrid(self, user_id: str, thread_id: str, 
                           user_question: str) -> str:
        """
        Hybrid approach: LLM for tool selection, configured LLM for final answer
        
        Flow:
        1. Tool calling LLM decides which tools to call (OpenAI for inbuilt, or configured provider)
        2. Execute the tools to retrieve context
        3. Pass context to final response LLM for answer generation
        
        Provider Logic:
        - inbuilt: Uses OpenAI for tool calling, Ollama for response
        - other: Uses same provider for both tool calling and response
        """
        logger.info(f"💬 Hybrid chat for thread {thread_id}: {user_question}")
        logger.info(f"🔧 Using provider: {self.llm_provider}")
    
        # Step 1: Tool binding based on provider
        if self.llm_provider == "inbuilt":
            retrieved_context = self._tool_calling_with_openai(user_id, thread_id, user_question)
        else:
            retrieved_context = self._tool_calling_with_llm_service(user_id, thread_id, user_question)
        
        # Step 2: Combine retrieved context
        combined_context = "\n\n".join(retrieved_context)
        logger.info(f"📚 Retrieved context length: {len(combined_context)} characters")
    
        # Step 3: Generate final answer
        system_prompt = f"""You are an AI email assistant helping users understand their email threads.

Answer ONLY using the retrieved context.

Rules:
- Be precise and factual
- Mention sender, timestamp, document name when relevant
- If answer is missing, say so clearly
- Keep responses concise and professional

Thread ID: {thread_id}
User: {user_id}"""
    
        user_prompt = f"""QUESTION:
{user_question}

RETRIEVED CONTEXT:
{combined_context}

Provide a clear and accurate answer based only on this data."""
    
        logger.info(f"🤖 Generating response using {self.llm_provider}...")
        logger.info(f"\n{'='*80}\n📋 FINAL SYSTEM PROMPT:\n{'='*80}\n{system_prompt}\n{'='*80}\n")
        logger.info(f"\n{'='*80}\n📝 FINAL USER PROMPT:\n{'='*80}\n{user_prompt}\n{'='*80}\n")
        final_answer = self._generate_response(system_prompt, user_prompt)
    
        logger.info("✅ Final answer generated successfully")
        return final_answer
    
    def _tool_calling_with_openai(self, user_id: str, thread_id: str, user_question: str) -> List[str]:
        """Handle tool calling using OpenAI (for inbuilt mode)"""
        logger.info("🔧 Using OpenAI for tool calling (inbuilt mode)")
        
        tools = self.create_tools_for_binding()
        
        # Bind tools with tool_choice="auto" to encourage tool calling
        llm_with_tools = self.tool_caller_llm.bind_tools(
            tools,
            tool_choice="auto"
        )
    
        # Strong system prompt that guides tool usage
        system_prompt = """You are an AI email assistant. Your task is to help users find information in email threads.

For EVERY user question:
1. ALWAYS use the available tools to search for relevant information
2. Use search_thread_emails to find information in email messages
3. Use search_attachments to find information in document attachments
4. You MUST call at least one tool for every query

Tools available:
- search_thread_emails: Search email messages for specific information
- search_attachments: Search document attachments for specific information

After using tools, you will receive the search results. Then you will generate a final answer.

Remember: ALWAYS use tools. Do not answer without searching first."""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{question}")
        ])
    
        chain = prompt | llm_with_tools
        ai_response = chain.invoke({"question": user_question})
        logger.info(f"🤖 OpenAI raw response: {ai_response}")
    
        retrieved_context = []
    
        # Check if tool_calls attribute exists and has actual calls
        has_tool_calls = (
            hasattr(ai_response, "tool_calls") 
            and ai_response.tool_calls 
            and len(ai_response.tool_calls) > 0
        )
        
        if has_tool_calls:
            logger.info(f"🛠 Tool calls detected: {ai_response.tool_calls}")
    
            for tool_call in ai_response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call.get("args", {})
    
                logger.info(f"📞 Executing tool: {tool_name} | args: {tool_args}")
    
                if tool_name == "search_thread_emails":
                    query = tool_args.get("query", user_question)
                    k = tool_args.get("k", 5)
    
                    result = self._search_thread_emails_internal(
                        user_id, thread_id, query, k
                    )
                    retrieved_context.append(
                        f"=== EMAIL SEARCH RESULTS ===\n{result}"
                    )
    
                elif tool_name == "search_attachments":
                    query = tool_args.get("query", user_question)
                    k = tool_args.get("k", 3)
    
                    result = self._search_attachments_internal(
                        user_id, thread_id, query, k
                    )
                    retrieved_context.append(
                        f"=== ATTACHMENT SEARCH RESULTS ===\n{result}"
                    )
    
        else:
            logger.warning("⚠️ No tool calls detected — fallback search activated")
            logger.warning(f"   Response content: {ai_response.content if hasattr(ai_response, 'content') else 'N/A'}")
    
            email_results = self._search_thread_emails_internal(
                user_id, thread_id, user_question, 5
            )
            attachment_results = self._search_attachments_internal(
                user_id, thread_id, user_question, 3
            )
    
            retrieved_context.append(f"=== EMAIL SEARCH RESULTS ===\n{email_results}")
            retrieved_context.append(f"=== ATTACHMENT SEARCH RESULTS ===\n{attachment_results}")
        
        return retrieved_context
    
    def _tool_calling_with_llm_service(self, user_id: str, thread_id: str, user_question: str) -> List[str]:
        """
        Handle tool calling using LLMService (for non-inbuilt providers)
        
        Note: This uses a text-based tool selection approach since not all models 
        support native function/tool calling:
        - OpenAI GPT-4/GPT-3.5: ✅ Full tool calling support
        - Anthropic Claude 3+: ✅ Full tool calling support  
        - Groq (Llama, Mixtral): ⚠️  Limited/experimental support
        - Ollama (most models): ❌ No native tool calling (uses text fallback)
        
        If tool selection fails (model unavailable, doesn't support tool calling, etc.),
        automatically falls back to searching both emails and attachments.
        """
        logger.info(f"🔧 Using LLMService ({self.llm_provider}) for tool calling")
        
        retrieved_context = []
        
        try:
            # For non-inbuilt providers, we'll execute a simpler tool selection prompt
            # since not all providers support tool calling natively
            system_prompt = """You are an email assistant. Based on the user's question, decide which tools to use:
1. search_thread_emails - to find specific information in emails
2. search_attachments - to find information in document attachments
3. both - if you need to search both

Respond with ONLY the tool name(s), one per line."""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_question}
            ]
            
            # Get tool selection from LLM with timeout
            tool_selection = self._run_async_task(self.llm_service.generate(
                messages,
                provider=self.llm_provider,
                model=self.llm_model,
                temperature=0
            ))
            
            logger.info(f"🛠 Tool selection: {tool_selection}")
            
            tool_selection_lower = tool_selection.lower()
            
            # Execute tools based on selection
            if "search_thread_emails" in tool_selection_lower or "both" in tool_selection_lower:
                email_results = self._search_thread_emails_internal(
                    user_id, thread_id, user_question, 5
                )
                retrieved_context.append(f"=== EMAIL SEARCH RESULTS ===\n{email_results}")
            
            if "search_attachments" in tool_selection_lower or "both" in tool_selection_lower:
                attachment_results = self._search_attachments_internal(
                    user_id, thread_id, user_question, 3
                )
                retrieved_context.append(f"=== ATTACHMENT SEARCH RESULTS ===\n{attachment_results}")
            
            # Fallback to both if nothing matched
            if not retrieved_context:
                logger.warning("⚠️ Tool selection unclear — fallback search activated")
                email_results = self._search_thread_emails_internal(
                    user_id, thread_id, user_question, 5
                )
                attachment_results = self._search_thread_emails_internal(
                    user_id, thread_id, user_question, 3
                )
                retrieved_context.append(f"=== EMAIL SEARCH RESULTS ===\n{email_results}")
                retrieved_context.append(f"=== ATTACHMENT SEARCH RESULTS ===\n{attachment_results}")
        
        except Exception as e:
            # If tool calling fails (model unavailable, connection error, etc.),
            # fall back to searching both sources automatically
            logger.error(f"❌ Tool calling failed: {e}")
            logger.warning("⚠️ Falling back to searching both emails and attachments")
            
            email_results = self._search_thread_emails_internal(
                user_id, thread_id, user_question, 5
            )
            attachment_results = self._search_attachments_internal(
                user_id, thread_id, user_question, 3
            )
            retrieved_context.append(f"=== EMAIL SEARCH RESULTS ===\n{email_results}")
            retrieved_context.append(f"=== ATTACHMENT SEARCH RESULTS ===\n{attachment_results}")
        
        return retrieved_context
    
    def _generate_response(self, system_prompt: str, user_prompt: str) -> str:
        """
        Generate final response using configured LLM
        
        Handles errors gracefully and provides informative fallback messages.
        """
        try:
            if self.llm_provider == "inbuilt":
                # Use Ollama for inbuilt mode
                logger.info("🦙 Using Ollama for response generation (inbuilt mode)")
                logger.info(f"\n{'='*80}\n🦙 OLLAMA REQUEST DETAILS:\n{'='*80}")
                logger.info(f"Model: {OLLAMA_MODEL}")
                logger.info(f"Temperature: {OLLAMA_TEMP}")
                logger.info(f"System Prompt:\n{system_prompt}")
                logger.info(f"User Prompt:\n{user_prompt}")
                logger.info(f"{'='*80}\n")
                
                ollama_response = call_ollama_chat_params(
                    modelName=OLLAMA_MODEL,
                    sysPrompt=system_prompt,
                    usrPrompt=user_prompt,
                    temp=OLLAMA_TEMP
                )
                return ollama_response["message"]["content"]
            else:
                # Use LLMService for other providers
                logger.info(f"🤖 Using LLMService ({self.llm_provider}) for response generation")
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
                
                logger.info(f"\n{'='*80}\n🤖 LLM SERVICE REQUEST DETAILS:\n{'='*80}")
                logger.info(f"Provider: {self.llm_provider}")
                logger.info(f"Model: {self.llm_model}")
                logger.info(f"Messages:")
                for msg in messages:
                    logger.info(f"  Role: {msg['role']}")
                    logger.info(f"  Content:\n{msg['content']}\n")
                logger.info(f"{'='*80}\n")
                
                response = self._run_async_task(self.llm_service.generate(
                    messages,
                    provider=self.llm_provider,
                    model=self.llm_model
                ))
                return response
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Response generation failed: {error_msg}")
            
            # Provide helpful error messages based on the error type
            if "connection" in error_msg.lower() or "timeout" in error_msg.lower():
                if self.llm_provider == "ollama" or self.llm_provider == "inbuilt":
                    return (
                        "⚠️ Unable to connect to the LLM service (Ollama). "
                        "Please ensure:\n"
                        "1. Ollama is running locally (ollama serve)\n"
                        "2. The correct URL is configured in settings\n"
                        "3. The model is pulled (ollama pull llama3.3)\n\n"
                        f"Error: {error_msg}"
                    )
                else:
                    return (
                        f"⚠️ Unable to connect to {self.llm_provider}. "
                        f"Please check your API key and network connection.\n\n"
                        f"Error: {error_msg}"
                    )
            elif "401" in error_msg or "403" in error_msg or "unauthorized" in error_msg.lower():
                return (
                    f"⚠️ Authentication failed for {self.llm_provider}. "
                    "Please check your API key in settings.\n\n"
                    f"Error: {error_msg}"
                )
            elif "404" in error_msg:
                return (
                    f"⚠️ Model or endpoint not found for {self.llm_provider}. "
                    f"Please verify:\n"
                    f"1. Model name: {self.llm_model}\n"
                    f"2. Provider URL in settings\n\n"
                    f"Error: {error_msg}"
                )
            else:
                return (
                    f"⚠️ Failed to generate response using {self.llm_provider}.\n\n"
                    f"Error: {error_msg}"
                )
    
    def process_and_chat(self, user_id: str, thread_id: str, 
                        user_question: str) -> Dict:
        """
        Main entry point: Process thread and answer question using hybrid approach
        
        Args:
            user_id: User email ID
            thread_id: Gmail thread ID
            user_question: User's question
            
        Returns:
            Dict with answer and processing info
        """
        logger.info(f"🎯 Starting hybrid chat pipeline for user: {user_id}, thread: {thread_id}")
        
        try:
            # Step 1: Process unprocessed emails
            logger.info("📥 Processing thread emails...")
            email_processing_info = self.process_thread_emails(user_id, thread_id)
            
            # Step 2: Process unprocessed attachments
            logger.info("📎 Processing thread attachments...")
            attachment_processing_info = self.process_thread_attachments(user_id, thread_id)
            
            # Step 3: Chat with thread using hybrid approach
            logger.info("💬 Generating response with hybrid approach...")
            answer = self.chat_with_thread_hybrid(user_id, thread_id, user_question)
            
            logger.info("✅ Hybrid chat pipeline completed successfully")
            
            return {
                "success": True,
                "answer": answer,
                "processing_info": {
                    "emails": email_processing_info,
                    "attachments": attachment_processing_info
                }
            }
            
        except Exception as e:
            logger.error(f"Hybrid chat pipeline error: {e}")
            return {
                'success': False,
                'error': str(e),
                'answer': None
            }