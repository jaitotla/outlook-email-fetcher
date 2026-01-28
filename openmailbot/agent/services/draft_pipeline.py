"""
Draft Pipeline Service - Email draft generation with attachments
Handles attachment processing and AI-powered draft generation using hybrid approach
"""

import os
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional
import logging

from llama_index.core import SimpleDirectoryReader
from llama_index.readers.file import PDFReader, CSVReader, PptxReader
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool

from services.embeddings import EmbeddingService
from services.llm import LLMService
from config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
BASE_PATH = "./data_pipeline"
EMAIL_ATTACHMENTS_PATH = os.getenv("EMAIL_ATTACHMENTS_PATH", "./email_attachments")
EMAIL_LOGS_PATH = os.getenv("EMAIL_LOGS_PATH", "/home/manotr/swapnil/email_logs")
DB_PATH = os.path.join(BASE_PATH, "draft_processing.db")

# File readers configuration
FILE_EXTRACTOR = {
    ".pdf": PDFReader(),
    ".csv": CSVReader(),
    ".pptx": PptxReader(),
    ".ppt": PptxReader(),
}


class DraftWithAttachmentsPipeline:
    """Pipeline for generating email drafts with attachment context"""
    
    def __init__(self):
        self.db_path = DB_PATH
        self.setup_database()
        
        # Initialize services
        self.embedding_service = EmbeddingService()
        self.llm_service = LLMService()
        
        # OpenAI only for tool calling decisions
        self.tool_caller_llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            api_key=settings.OPENAI_API_KEY
        )
    
    def setup_database(self):
        """Initialize SQLite database with required schema"""
        os.makedirs(BASE_PATH, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS draft_processing (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                thread_id TEXT NOT NULL,
                attachment_id TEXT,
                vector_id TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                processed_status TEXT DEFAULT 'pending',
                processed_timestamp DATETIME,
                metadata TEXT,
                UNIQUE(user_id, thread_id, attachment_id)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Draft database initialized successfully")
    
    def get_namespace(self, user_id: str, thread_id: str) -> str:
        """Get namespace for user and thread"""
        return f"{user_id}_{thread_id}_draft"
    
    
    def check_attachment_processed(self, user_id: str, thread_id: str, attachment_id: str) -> bool:
        """Check if attachment is already processed"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT processed_status FROM draft_processing
            WHERE user_id = ? AND thread_id = ? AND attachment_id = ?
        ''', (user_id, thread_id, attachment_id))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return result[0] == 'completed'
        return False
    
    def get_thread_json_data(self, thread_id: str) -> Optional[Dict]:
        """Read thread JSON data from email_logs directory"""
        json_path = os.path.join(EMAIL_LOGS_PATH, thread_id, f"{thread_id}.json")
        
        if not os.path.exists(json_path):
            logger.warning(f"Thread JSON not found: {json_path}")
            return None
        
        try:
            with open(json_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading thread JSON {json_path}: {e}")
            return None
    
    def get_thread_attachments(self, thread_id: str) -> List[Dict]:
        """Get all attachments for a thread from the file system"""
        thread_path = os.path.join(EMAIL_ATTACHMENTS_PATH, thread_id)
        
        if not os.path.exists(thread_path):
            logger.warning(f"No attachments found for thread: {thread_id}")
            return []
        
        # Read metadata.json files for attachments
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
                                    'attachment_id': att.get('filename')
                                })
                except Exception as e:
                    logger.error(f"Error reading metadata file {metadata_file}: {e}")
        
        # Fallback: scan directory for files
        if not attachments:
            for file in os.listdir(thread_path):
                if not file.endswith('_metadata.json'):
                    attachments.append({
                        'filename': file,
                        'path': os.path.join(thread_path, file),
                        'attachment_id': file
                    })
        
        return attachments
    
    async def process_attachment(self, user_id: str, thread_id: str, 
                          attachment_path: str, attachment_id: str):
        """Process a single attachment and store embeddings"""
        logger.info(f"Processing attachment: {attachment_path}")
        
        try:
            # Load document
            documents = SimpleDirectoryReader(
                input_files=[attachment_path],
                file_extractor=FILE_EXTRACTOR
            ).load_data()
            
            if not documents:
                logger.warning(f"No content extracted from {attachment_path}")
                return
            
            namespace = self.get_namespace(user_id, thread_id)
            
            # Store each document chunk
            for idx, doc in enumerate(documents):
                text = doc.text.strip()
                if not text:
                    continue
                
                # Create metadata
                metadata = {
                    "thread_id": thread_id,
                    "attachment_id": attachment_id,
                    "filename": os.path.basename(attachment_path),
                    "chunk_index": idx,
                    "type": "attachment_data"
                }
                
                # Get embedding
                embedding = await self.embedding_service.generate_embedding(text)
                
                # Store in vector DB
                doc_id = f"{user_id}_{thread_id}_{attachment_id}_{idx}"
                
                vector_id = await self.embedding_service.store_embedding(
                    embedding=embedding,
                    metadata=metadata,
                    namespace=namespace,
                    vector_id=doc_id
                )
                
                logger.info(f"Stored chunk {idx} for attachment {attachment_id}")
            
            # Update database
            self.mark_attachment_processed(user_id, thread_id, attachment_id)
            logger.info(f"✅ Attachment {attachment_id} processed successfully")
            
        except Exception as e:
            logger.error(f"Error processing attachment {attachment_path}: {e}")
            raise
    
    def mark_attachment_processed(self, user_id: str, thread_id: str, attachment_id: str):
        """Mark attachment as processed in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO draft_processing 
            (user_id, thread_id, attachment_id, processed_status, processed_timestamp)
            VALUES (?, ?, ?, 'completed', CURRENT_TIMESTAMP)
        ''', (user_id, thread_id, attachment_id))
        
        conn.commit()
        conn.close()
    
    async def _get_attachments_by_id_internal(self, user_id: str, thread_id: str, 
                                       attachment_query: str) -> str:
        """Internal method to retrieve attachment content"""
        logger.info(f"🔧 Retrieving attachments for: {attachment_query}")
        
        namespace = self.get_namespace(user_id, thread_id)
        filter_dict = {"thread_id": thread_id}
        
        # Get all documents for this thread
        results = await self.embedding_service.find_similar_by_text(
            text=attachment_query,
            namespace=namespace,
            limit=10,
            filter=filter_dict
        )
        
        if not results:
            return "No attachments found for this thread."
        
        # Format response with metadata
        response_parts = []
        for result in results:
            metadata = result.get('metadata', {})
            filename = metadata.get('filename', 'Unknown')
            content = result.get('text', result.get('document', ''))
            response_parts.append(f"📎 From {filename}:\n{content}\n")
        
        result = "\n".join(response_parts)
        logger.info(f"📄 Returned {len(results)} document chunks")
        return result
    
    async def _query_attachments_internal(self, user_id: str, thread_id: str, 
                                   query: str, k: int = 3) -> str:
        """Internal method to search attachment content"""
        logger.info(f"🔍 Querying attachments: {query}")
        
        namespace = self.get_namespace(user_id, thread_id)
        filter_dict = {"thread_id": thread_id}
        
        results = await self.embedding_service.find_similar_by_text(
            text=query,
            namespace=namespace,
            limit=k,
            filter=filter_dict
        )
        
        if not results:
            return "No relevant information found in attachments."
        
        # Format with metadata
        response_parts = []
        for result in results:
            metadata = result.get('metadata', {})
            filename = metadata.get('filename', 'Unknown')
            content = result.get('text', result.get('document', ''))
            response_parts.append(f"📎 {filename}:\n{content}\n")
        
        result = "\n".join(response_parts)
        logger.info(f"📄 Query returned {len(results)} relevant chunks")
        return result
    
    def create_tools_for_binding(self):
        """Create tool definitions for LLM binding (OpenAI decides which to use)"""
        
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
        Hybrid approach: OpenAI for tool selection, LLMService for final draft
        
        Flow:
        1. OpenAI LLM decides which tools to call
        2. Execute the tools to retrieve context from attachments
        3. Pass email thread + retrieved context to LLMService for draft generation
        """
        logger.info("📝 Starting hybrid draft generation...")
        
        # Get user preferences
        prefs = user_preferences or {}
        name = prefs.get('name', 'User')
        position = prefs.get('position', 'Professional')
        tone = prefs.get('tone', 'professional and concise')
        custom_instructions = prefs.get('custom_instructions', '')
        
        # Step 1: Tool binding with OpenAI
        tools = self.create_tools_for_binding()
        llm_with_tools = self.tool_caller_llm.bind_tools(tools)
        
        # Create prompt for tool calling
        tool_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a tool-calling assistant. Your ONLY job is to decide which tools to call based on the email thread.

Analyze the email thread and determine:
- If attachments or documents are mentioned, call the appropriate tools
- Use get_attachments_by_id to retrieve all attachment content
- Use query_attachments for specific information searches

Do NOT generate email drafts. Only decide which tools to call."""),
            ("human", """Email Thread:
{email_data}

Task: Draft a professional email response.
Decide which tools (if any) are needed to retrieve attachment information.""")
        ])
        
        chain = tool_prompt | llm_with_tools
        
        # Get tool calls from OpenAI
        ai_response = chain.invoke({
            "email_data": email_data
        })
        
        logger.info(f"🤖 OpenAI tool decision response: {ai_response}")
        
        # Step 2: Execute tool calls and collect context
        retrieved_context = []
        
        if hasattr(ai_response, "tool_calls") and ai_response.tool_calls:
            logger.info(f"🛠 Tool calls detected: {ai_response.tool_calls}")
            
            for tool_call in ai_response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call.get("args", {})
                
                logger.info(f"📞 Executing tool: {tool_name} | args: {tool_args}")
                
                if tool_name == "get_attachments_by_id":
                    attachment_query = tool_args.get("attachment_query", "")
                    result = await self._get_attachments_by_id_internal(
                        user_id, thread_id, attachment_query
                    )
                    retrieved_context.append(
                        f"=== ALL ATTACHMENTS ===\n{result}"
                    )
                
                elif tool_name == "query_attachments":
                    query = tool_args.get("query", "")
                    k = tool_args.get("k", 3)
                    result = await self._query_attachments_internal(
                        user_id, thread_id, query, k
                    )
                    retrieved_context.append(
                        f"=== RELEVANT ATTACHMENT CONTENT ===\n{result}"
                    )
        else:
            logger.info("ℹ️ No tool calls needed - no attachments referenced")
        
        # Step 3: Combine all context
        combined_context = "\n\n".join(retrieved_context) if retrieved_context else "No attachment context needed."
        
        logger.info(f"📚 Retrieved context length: {len(combined_context)} characters")
        
        # Step 4: Generate draft with LLMService
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
        
        logger.info("🦙 Calling LLM for draft generation...")
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        draft_content = await self.llm_service.generate(
            messages=messages,
            provider=settings.DEFAULT_LLM_PROVIDER
        )
        
        logger.info("✅ Draft generated successfully with hybrid approach")
        
        return draft_content
    
    async def process_email_request(self, user_id: str, thread_id: str, 
                             user_preferences: Dict = None) -> Dict:
        """
        Main pipeline entry point - processes email and generates draft using hybrid approach
        
        Args:
            user_id: Unique user identifier (email or user ID)
            thread_id: Gmail thread ID
            user_preferences: User settings for draft generation
            
        Returns:
            Dict with draft_content and processing_info
        """
        logger.info(f"🚀 Starting draft pipeline for user: {user_id}, thread: {thread_id}")
        
        processing_info = {
            'attachments_found': 0,
            'attachments_processed': 0,
            'attachments_skipped': 0,
            'errors': []
        }
        
        try:
            # Step 1: Read thread JSON data
            thread_data = self.get_thread_json_data(thread_id)
            if not thread_data:
                return {
                    'success': False,
                    'error': f'Thread JSON not found for thread_id: {thread_id}',
                    'processing_info': processing_info
                }
            
            # Convert thread data to string format for email_data
            email_data = json.dumps(thread_data, indent=2)
            logger.info(f"Loaded thread data with {len(thread_data.get('messages', []))} messages")
            
            # Step 2: Get attachments for this thread
            attachments = self.get_thread_attachments(thread_id)
            processing_info['attachments_found'] = len(attachments)
            
            logger.info(f"Found {len(attachments)} attachments for thread {thread_id}")
            
            # Step 3: Process unprocessed attachments
            for attachment in attachments:
                attachment_id = attachment.get('attachment_id') or attachment.get('filename')
                attachment_path = attachment.get('path')
                
                if not attachment_path or not os.path.exists(attachment_path):
                    logger.warning(f"Attachment path not found: {attachment_path}")
                    continue
                
                # Check if already processed
                if self.check_attachment_processed(user_id, thread_id, attachment_id):
                    logger.info(f"⏭️  Skipping already processed: {attachment_id}")
                    processing_info['attachments_skipped'] += 1
                    continue
                
                # Process attachment
                try:
                    await self.process_attachment(
                        user_id, thread_id,
                        attachment_path, attachment_id
                    )
                    processing_info['attachments_processed'] += 1
                except Exception as e:
                    error_msg = f"Failed to process {attachment_id}: {str(e)}"
                    logger.error(error_msg)
                    processing_info['errors'].append(error_msg)
            
            # Step 4: Generate draft using hybrid approach (OpenAI + LLMService)
            logger.info("📝 Generating draft with hybrid approach...")
            draft_content = await self.generate_draft_hybrid(
                user_id, thread_id,
                email_data, user_preferences
            )
            
            logger.info("✅ Draft pipeline completed successfully")
            
            return {
                'success': True,
                'draft_content': draft_content,
                'processing_info': processing_info
            }
            
        except Exception as e:
            logger.error(f"Draft pipeline error: {e}")
            return {
                'success': False,
                'error': str(e),
                'processing_info': processing_info
            }
