import os
import json
import sqlite3
import asyncio
import re
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
import traceback

from services.embeddings import EmbeddingService
from services.llm import LLMService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration
CONFIG_PATH = "/home/ubuntu/openmailbot/openmailbot/agent/config.json"
with open(CONFIG_PATH, 'r') as f:
    CONFIG = json.load(f)

# Import settings manager for encrypted DB-based settings
from services.settings_manager import SettingsManager

# Constants
# Base data directory under the agent package: agent/data/{user_id}/...
BASE_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
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


class DraftPipeline:
    """Pipeline for generating email drafts using attachment context and hybrid approach"""
    
    def __init__(self, user_id: Optional[str] = None, effective_settings: Optional[Dict] = None):
        # Optionally accept a user_id to scope operations; many methods still accept user_id
        self.user_id = user_id
        # keep a global fallback DB under BASE_DATA_DIR
        self.db_path = os.path.join(BASE_DATA_DIR, "draft_processing.db")
        self.setup_database()
        
        # Load effective settings - either from parameter or retrieve from encrypted DB
        if effective_settings:
            self.effective_settings = effective_settings
        elif user_id:
            # Load from encrypted DB storage
            settings_manager = SettingsManager(user_id)
            retrieved_settings = settings_manager.get_settings(user_id, "general")
            self.effective_settings = retrieved_settings if retrieved_settings else {}
        else:
            # Fallback to empty dict
            self.effective_settings = {}
        
        self.llm_provider = self.effective_settings.get("llm_provider", "inbuilt")
        self.llm_model = self.effective_settings.get("llm_model", "gpt-4o-mini")
        
        # Initialize LLMService for all LLM operations
        try:
            self.llm_service = LLMService()
            # Override with user-specific settings if available
            if self.effective_settings:
                self.llm_service.effective_settings = self.effective_settings
                self.llm_service.default_provider = self.llm_provider
                self.llm_service.default_model = self.llm_model
                self.llm_service._init_clients()
            logger.info("✅ LLMService initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize LLMService: {e}")
            raise
        
        # Keep OpenAI tool caller for inbuilt mode (tool calling requires OpenAI)
        # For other providers, we'll use LLMService with appropriate fallback
        if self.llm_provider == "inbuilt":
            self.tool_caller_llm = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0,
                api_key=CONFIG.get('OPENAI_KEY')
            )
            logger.info("✅ OpenAI tool caller initialized for inbuilt mode")
        else:
            self.tool_caller_llm = None
            logger.info(f"✅ Using {self.llm_provider} for all operations (including tool calling)")
        
        # Initialize EmbeddingService for embeddings and vector operations
        try:
            self.embedding_service = EmbeddingService()
            logger.info("✅ EmbeddingService initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize EmbeddingService: {e}")
            raise
    
    def setup_database(self):
        """Initialize SQLite database for tracking processed drafts and attachments"""
        os.makedirs(BASE_PATH, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table for draft processing
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS draft_processing (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                thread_id TEXT NOT NULL,
                draft_id TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                processed_status TEXT DEFAULT 'pending',
                processed_timestamp DATETIME,
                chroma_collection TEXT,
                metadata TEXT,
                UNIQUE(user_id, thread_id, draft_id)
            )
        ''')
        
        # Table for attachment processing (shared with draft context)
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
        logger.info("Draft database initialized successfully")

    def ensure_user_db(self, user_id: str):
        """Ensure per-user sqlite DB and tables exist."""
        user_db = os.path.join(BASE_DATA_DIR, user_id, "sql_data", "draft_processing.db")
        os.makedirs(os.path.dirname(user_db), exist_ok=True)
        conn = sqlite3.connect(user_db)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS draft_processing (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                thread_id TEXT NOT NULL,
                draft_id TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                processed_status TEXT DEFAULT 'pending',
                processed_timestamp DATETIME,
                chroma_collection TEXT,
                metadata TEXT,
                UNIQUE(user_id, thread_id, draft_id)
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
        logger.info(f"Initialized per-user draft DB at {user_db}")

    def get_user_chroma_client(self, user_id: str):
        """Get or create ChromaDB client for a specific user"""
        # Use per-user vector DB directory: data/{user_id}/vector_db/
        user_vector_path = os.path.join(BASE_DATA_DIR, user_id, "vector_db")
        os.makedirs(user_vector_path, exist_ok=True)
        # keep a consistent folder name inside the user's vector_db
        user_chroma_path = os.path.join(user_vector_path, f"cdb_{user_id}")
        os.makedirs(user_chroma_path, exist_ok=True)
        return chromadb.PersistentClient(path=user_chroma_path)
    
    def get_user_collection(self, user_id: str, collection_name: str = "documents"):
        """Get or create collection for a user's documents"""
        client = self.get_user_chroma_client(user_id)
        return client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
    
    def _run_async_task(self, coro):
        """Helper to run async code safely, handling running event loops"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running, schedule in thread pool
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return loop.run_in_executor(pool, lambda: self._run_in_new_loop(coro))
            else:
                return loop.run_until_complete(coro)
        except RuntimeError:
            # No event loop exists, create one
            return asyncio.run(coro)
    
    def _run_in_new_loop(self, coro):
        """Run coroutine in a new event loop (for thread pool)"""
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()
    
    def _get_embedding_sync(self, text: str) -> List[float]:
        """Synchronous wrapper for async embedding generation"""
        try:
            embedding = self._run_async_task(self.embedding_service.generate_embedding(text))
            return embedding
        except Exception as e:
            logger.error(f"Embedding generation error: {e}")
            raise
    
    def check_attachment_processed(self, user_id: str, thread_id: str, attachment_id: str) -> bool:
        """Check if attachment is already processed"""
        # Ensure per-user DB has required tables
        self.ensure_user_db(user_id)
        user_db = os.path.join(BASE_DATA_DIR, user_id, "sql_data", "draft_processing.db")
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
    
    def get_thread_json_data(self, user_id: str, thread_id: str) -> Optional[Dict]:
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
    
    async def process_attachment(self, user_id: str, thread_id: str, message_id: str,
                                attachment_path: str, attachment_id: str):
        """Process a single attachment and store embeddings (async)"""
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
                    embedding = await self.embedding_service.generate_embedding(text)
                    doc_id = f"{user_id}_{thread_id}_{attachment_id}_{idx}"
                    
                    # Step 4: Store in ChromaDB via EmbeddingService
                    namespace = sanitize_namespace(f"{user_id}_drafts")
                    await self.embedding_service.store_embedding(
                        embedding=embedding,
                        metadata=metadata,
                        namespace=namespace,
                        vector_id=doc_id
                    )
                    
                    chunk_count += 1
                    logger.info(f"  ✓ Stored chunk {idx} (id: {doc_id})")
                    
                except Exception as embed_error:
                    logger.error(f"  ✗ Failed to embed chunk {idx}: {embed_error}")
                    raise
            
            if chunk_count == 0:
                logger.warning(f"⚠️  No chunks stored for attachment {attachment_id}")
                return
            
            # Step 5: Mark as processed
            await self.mark_attachment_processed(user_id, thread_id, message_id, attachment_id)
            logger.info(f"✅ Attachment {attachment_id} processed: {chunk_count} chunks stored")
            
        except Exception as e:
            logger.error(f"❌ Error processing attachment {attachment_path}: {e}")
            logger.error(f"  Traceback: {traceback.format_exc()}")
            raise
    
    async def mark_attachment_processed(self, user_id: str, thread_id: str,
                                       message_id: str, attachment_id: str):
        """Mark attachment as processed in database (async)"""
        # Ensure per-user DB has required tables
        self.ensure_user_db(user_id)
        user_db = os.path.join(BASE_DATA_DIR, user_id, "sql_data", "draft_processing.db")
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
    
    async def process_thread_attachments(self, user_id: str, thread_id: str, message_id: str = None) -> Dict:
        """Process all unprocessed attachments in a thread (async)"""
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
            
            # Create tasks for parallel processing
            tasks = []
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
                
                # Create task for parallel processing
                task = self._process_attachment_with_info(
                    user_id, thread_id, attach_message_id,
                    attachment_path, attachment_id,
                    attachment_info
                )
                tasks.append(task)
            
            # Execute all attachment processing tasks in parallel
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            
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
    
    async def _process_attachment_with_info(self, user_id: str, thread_id: str, message_id: str,
                                           attachment_path: str, attachment_id: str,
                                           attachment_info: Dict):
        """Helper to process attachment and update info dict"""
        try:
            await self.process_attachment(
                user_id, thread_id, message_id,
                attachment_path, attachment_id
            )
            attachment_info['attachments_processed'] += 1
        except Exception as e:
            error_msg = f"Failed to process {attachment_id}: {str(e)}"
            logger.error(f"  ✗ {error_msg}")
            attachment_info['errors'].append(error_msg)
    
    async def _get_attachments_by_id_internal(self, user_id: str, thread_id: str,
                                             attachment_query: str) -> str:
        """Internal method to retrieve attachment content (async)"""
        logger.info(f"🔧 Retrieving attachments for: {attachment_query}")
        
        collection = self.get_user_collection(user_id)
        
        # Get all documents for this thread
        results = collection.get(
            where={"thread_id": thread_id}
        )
        
        docs = results.get("documents", [])
        metadatas = results.get("metadatas", [])
        
        if not docs:
            return "No attachments found for this thread."
        
        # Format response with metadata
        response_parts = []
        for doc, meta in zip(docs, metadatas):
            filename = meta.get('filename', 'Unknown')
            response_parts.append(f"📎 From {filename}:\n{doc}\n")
        
        result = "\n".join(response_parts)
        logger.info(f"📄 Returned {len(docs)} document chunks")
        return result
    
    async def _query_attachments_internal(self, user_id: str, thread_id: str,
                                         query: str, k: int = 3) -> str:
        """Internal method to search attachment content (async)"""
        logger.info(f"🔍 Querying attachments: {query}")
        
        try:
            # Generate query embedding using EmbeddingService
            query_embedding = await self.embedding_service.generate_embedding(query)
            
            # Search for similar documents
            docs, metadatas, distances = await self.embedding_service.search_similar(
                query_embedding=query_embedding,
                namespace=sanitize_namespace(f"{user_id}_drafts"),
                k=k,
                where={"thread_id": thread_id}
            )
            
            if not docs:
                return "No relevant information found in attachments."
            
            # Format with metadata
            response_parts = []
            for idx, (doc, meta, distance) in enumerate(zip(docs, metadatas, distances), 1):
                filename = meta.get('filename', 'Unknown')
                response_parts.append(
                    f"{idx}. 📎 {filename}:\n{doc}\n   (Relevance: {1 - distance:.2%})\n"
                )
            
            result = "\n".join(response_parts)
            logger.info(f"📄 Query returned {len(docs)} relevant chunks")
            return result
            
        except Exception as e:
            logger.error(f"Attachment query error: {e}")
            return f"Error querying attachments: {str(e)}"
    
    def create_tools_for_binding(self):
        """Create tool definitions for LLM binding"""
        
        @tool
        def get_attachments_by_id(attachment_query: str) -> str:
            """
            Get attachment content based on query.
            Use this to retrieve specific document content.
            
            Args:
                attachment_query: What you're looking for in the attachments
            """
            return "Tool placeholder - will be executed separately"
        
        @tool
        def query_attachments(query: str, k: int = 3) -> str:
            """
            Search attachment content using semantic search.
            Use this when you need specific information from documents.
            
            Args:
                query: What information you're looking for
                k: Number of relevant chunks to retrieve (default: 3)
            """
            return "Tool placeholder - will be executed separately"
        
        return [get_attachments_by_id, query_attachments]
    
    async def generate_draft_hybrid(self, user_id: str, thread_id: str,
                                   email_data: str, user_preferences: Dict = None) -> str:
        """
        Hybrid approach: OpenAI for tool selection, LLMService for final draft (async)
        
        Flow:
        1. Tool calling LLM decides which tools to call (OpenAI for inbuilt, or configured provider)
        2. Execute the tools to retrieve context from attachments
        3. Pass email thread + retrieved context to LLMService for draft generation
        """
        logger.info("📝 Starting hybrid draft generation...")
        logger.info(f"🔧 Using provider: {self.llm_provider}")
        
        # Get user preferences
        prefs = user_preferences or {}
        name = prefs.get('name', 'User')
        position = prefs.get('position', 'Professional')
        tone = prefs.get('tone', 'professional and concise')
        custom_instructions = prefs.get('custom_instructions', '')
        
        # Step 1: Tool binding based on provider
        if self.llm_provider == "inbuilt":
            logger.info("🔧 Using OpenAI for tool calling (inbuilt mode)")
            retrieved_context = await self._tool_calling_with_openai_draft(user_id, thread_id, email_data)
        else:
            logger.info(f"🔧 Using LLMService ({self.llm_provider}) for tool calling")
            retrieved_context = await self._tool_calling_with_llm_service_draft(user_id, thread_id, email_data)
        
        # Step 2: Combine all context
        combined_context = "\n\n".join(retrieved_context) if retrieved_context else "No attachment context needed."
        logger.info(f"📚 Retrieved context length: {len(combined_context)} characters")
        
        # Step 3: Generate draft with LLMService
        system_prompt = f"""You are an AI email assistant helping {name}, a {position}, to draft professional email responses.

Your responsibilities:
- Analyze the full email thread for background and continuity
- Focus primarily on the MOST RECENT 4–5 emails to determine current topic and intent
- Draft a professional reply that directly addresses the latest email

Thread Information:
- Current thread_id: {thread_id}

Guidelines:
- Tone: {tone}
- Additional Instructions: {custom_instructions}
- Be accurate and context-aware
- Use the full thread ONLY as historical reference
- DO NOT repeat or summarize early-stage discussion unless required
- The response should reflect the *current state of the conversation*
- If attachment content is provided, incorporate relevant information naturally

Important Rules:
1. Prioritize the last 4–5 emails when drafting
2. Use older emails only for continuity and context
3. The draft must sound like a natural continuation of the latest exchange
4. Do NOT recap the entire thread
5. If attachment data is provided, use it appropriately in the response

Output: A professional, concise, context-aware email reply addressing the latest discussion."""
        
        user_prompt = f"""EMAIL THREAD:
{email_data}

ATTACHMENT CONTEXT (if any):
{combined_context}

Please draft a professional email response that:
1. Addresses the most recent email in the thread
2. Incorporates relevant attachment information if provided
3. Maintains the conversation's current context and tone
4. Is ready to send without further editing"""
        
        logger.info(f"🤖 Generating response using {self.llm_provider}...")
        logger.info(f"\n{'='*80}\n📋 FINAL SYSTEM PROMPT:\n{'='*80}\n{system_prompt}\n{'='*80}\n")
        logger.info(f"\n{'='*80}\n📝 FINAL USER PROMPT:\n{'='*80}\n{user_prompt}\n{'='*80}\n")
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        draft_content = await self.llm_service.generate(
            messages,
            provider=self.llm_provider,
            model=self.llm_model,
            temperature=0.7
        )
        
        logger.info("✅ Draft generated successfully with hybrid approach")
        return draft_content
    
    async def _tool_calling_with_openai_draft(self, user_id: str, thread_id: str, email_data: str) -> List[str]:
        """Handle tool calling using OpenAI for draft generation (inbuilt mode)"""
        logger.info("🔧 Using OpenAI for tool calling (inbuilt mode)")
        
        tools = self.create_tools_for_binding()
        llm_with_tools = self.tool_caller_llm.bind_tools(tools)
        
        system_prompt = """You are a tool-calling assistant. Your ONLY job is to decide which tools to call based on the email thread.

Analyze the email thread and determine:
- If attachments or documents are mentioned, call the appropriate tools
- Use get_attachments_by_id to retrieve all attachment content
- Use query_attachments for specific information searches

Do NOT generate email drafts. Only decide which tools to call."""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", """Email Thread:
{email_data}

Task: Draft a professional email response.
Decide which tools (if any) are needed to retrieve attachment information.""")
        ])
        
        chain = prompt | llm_with_tools
        ai_response = chain.invoke({"email_data": email_data})
        
        logger.info(f"🤖 OpenAI tool decision response: {ai_response}")
        
        retrieved_context = []
        
        if hasattr(ai_response, "tool_calls") and ai_response.tool_calls:
            logger.info(f"🛠 Tool calls detected: {ai_response.tool_calls}")
            
            for tool_call in ai_response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call.get("args", {})
                
                logger.info(f"📞 Executing tool: {tool_name} | args: {tool_args}")
                
                if tool_name == "get_attachments_by_id":
                    attachment_query = tool_args.get("attachment_query", "")
                    result = await self._get_attachments_by_id_internal(user_id, thread_id, attachment_query)
                    retrieved_context.append(f"=== ALL ATTACHMENTS ===\n{result}")
                
                elif tool_name == "query_attachments":
                    query = tool_args.get("query", "")
                    k = tool_args.get("k", 3)
                    result = await self._query_attachments_internal(user_id, thread_id, query, k)
                    retrieved_context.append(f"=== RELEVANT ATTACHMENT CONTENT ===\n{result}")
        else:
            logger.info("ℹ️ No tool calls needed - no attachments referenced")
        
        return retrieved_context
    
    async def _tool_calling_with_llm_service_draft(self, user_id: str, thread_id: str, email_data: str) -> List[str]:
        """Handle tool calling using LLMService for draft generation (non-inbuilt providers)"""
        logger.info(f"🔧 Using LLMService ({self.llm_provider}) for tool calling")
        
        system_prompt = """You are an email assistant. Based on the email thread, decide which tools to use:
1. get_attachments_by_id - to retrieve all attachment content
2. query_attachments - to find specific information in documents
3. none - if no attachments are needed

Respond with ONLY the tool name(s), one per line."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Email thread:\n{email_data}"}
        ]
        
        tool_selection = await self.llm_service.generate(
            messages,
            provider=self.llm_provider,
            model=self.llm_model,
            temperature=0
        )
        
        logger.info(f"🛠 Tool selection: {tool_selection}")
        
        retrieved_context = []
        tool_selection_lower = tool_selection.lower()
        
        if "get_attachments_by_id" in tool_selection_lower:
            result = await self._get_attachments_by_id_internal(user_id, thread_id, "all")
            retrieved_context.append(f"=== ALL ATTACHMENTS ===\n{result}")
        
        if "query_attachments" in tool_selection_lower:
            result = await self._query_attachments_internal(user_id, thread_id, "relevant content", 3)
            retrieved_context.append(f"=== RELEVANT ATTACHMENT CONTENT ===\n{result}")
        
        if not retrieved_context:
            logger.info("ℹ️ No attachment tools selected")
        
        return retrieved_context
    
    async def process_email_request(self, user_id: str, thread_id: str,
                                   user_preferences: Dict = None) -> Dict:
        """
        Main pipeline entry point - processes email and generates draft using hybrid approach (async)
        
        Args:
            user_id: Unique user identifier (email or user ID)
            thread_id: Gmail thread ID
            user_preferences: User settings for draft generation
            
        Returns:
            Dict with draft_content and processing_info
        """
        logger.info(f"🚀 Starting hybrid draft pipeline for user: {user_id}, thread: {thread_id}")
        
        processing_info = {
            'attachments_found': 0,
            'attachments_processed': 0,
            'attachments_skipped': 0,
            'errors': []
        }
        
        try:
            # Step 1: Read thread JSON data
            thread_data = self.get_thread_json_data(user_id, thread_id)
            if not thread_data:
                return {
                    'success': False,
                    'error': f'Thread JSON not found for thread_id: {thread_id}',
                    'processing_info': processing_info
                }
            
            # Convert thread data to string format for email_data
            email_data = json.dumps(thread_data, indent=2)
            logger.info(f"Loaded thread data with {len(thread_data.get('messages', []))} messages")
            
            # Step 2: Process attachments (async)
            logger.info("📎 Processing thread attachments...")
            attachment_processing_info = await self.process_thread_attachments(user_id, thread_id)
            processing_info = attachment_processing_info
            
            # Step 3: Generate draft using hybrid approach (OpenAI/LLMService + LLMService)
            logger.info("📝 Generating draft with hybrid approach...")
            draft_content = await self.generate_draft_hybrid(
                user_id, thread_id,
                email_data, user_preferences
            )
            
            logger.info("✅ Hybrid draft pipeline completed successfully")
            
            return {
                'success': True,
                'draft_content': draft_content,
                'processing_info': processing_info
            }
            
        except Exception as e:
            logger.error(f"Hybrid draft pipeline error: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                'success': False,
                'error': str(e),
                'processing_info': processing_info
            }
