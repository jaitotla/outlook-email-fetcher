"""
Chat Pipeline Service - RAG-based email thread chatting
Handles email and attachment processing with semantic search using ChromaDB
"""

import os
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Set
import logging
from datetime import datetime

import chromadb
import requests
import ollama
from llama_index.core import SimpleDirectoryReader
from llama_index.readers.file import PDFReader, CSVReader, PptxReader
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool

from openmailbot.agent.prompt.prompt import (
    TOOL_CALLING_SYSTEM_PROMPT,
    SEARCH_EMAILS_TOOL_DESCRIPTION,
    SEARCH_ATTACHMENTS_TOOL_DESCRIPTION,
    get_final_answer_system_prompt,
    get_final_answer_user_prompt,
    format_email_result,
    format_attachment_result,
    EMAIL_SEARCH_RESULTS_HEADER,
    ATTACHMENT_SEARCH_RESULTS_HEADER,
    NO_EMAILS_FOUND,
    NO_ATTACHMENTS_FOUND,
    EMAIL_PROCESSING_START,
    EMAIL_PROCESSING_COMPLETE,
    ATTACHMENT_PROCESSING_START,
    ATTACHMENT_PROCESSING_SKIP,
    MESSAGE_PROCESSED_SUCCESS,
    ATTACHMENT_PROCESSED_SUCCESS,
    HYBRID_CHAT_COMPLETE,
    ERROR_EMBEDDING_API,
    ERROR_LOADING_THREAD,
    ERROR_PROCESSING_MESSAGE,
    ERROR_PROCESSING_ATTACHMENT,
    ERROR_READING_METADATA,
    ERROR_THREAD_PROCESSING,
    ERROR_ATTACHMENT_PROCESSING,
    ERROR_PIPELINE,
    WARNING_EMPTY_CONTENT,
    WARNING_NO_THREAD_DATA,
    WARNING_NO_ATTACHMENTS,
    WARNING_ATTACHMENT_PATH_NOT_FOUND,
    WARNING_NO_TOOL_CALLS,
    INFO_FOUND_EXISTING_MESSAGES,
    INFO_FOUND_THREAD_MESSAGES,
    INFO_UNPROCESSED_MESSAGES,
    INFO_FOUND_ATTACHMENTS,
    INFO_SEARCHING_EMAILS,
    INFO_SEARCHING_ATTACHMENTS,
    INFO_TOOL_EXECUTION,
    INFO_CONTEXT_LENGTH,
    INFO_OLLAMA_CALLING,
    INFO_HYBRID_CHAT_START,
    INFO_OPENAI_RESPONSE,
    INFO_TOOL_CALLS_DETECTED,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from config import settings

# Constants
BASE_PATH = "./data_pipeline"
EMAIL_LOGS_PATH = os.getenv("EMAIL_LOGS_PATH", "/home/manotr/swapnil/email_logs")
EMAIL_ATTACHMENTS_PATH = os.getenv("EMAIL_ATTACHMENTS_PATH", "./email_attachments")
DB_PATH = os.path.join(BASE_PATH, "chat_thread_processing.db")

def _load_local_config():
    path = os.path.join(os.path.dirname(__file__), "config.json")
    path = os.path.abspath(path)
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

# Ollama settings
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_TEMP = float(os.getenv("OLLAMA_TEMP", "0.4"))

# File readers configuration
FILE_EXTRACTOR = {
    ".pdf": PDFReader(),
    ".csv": CSVReader(),
    ".pptx": PptxReader(),
    ".ppt": PptxReader(),
}


def call_ollama_chat_params(modelName: str, sysPrompt: str, usrPrompt: str, temp: float) -> Dict:
    """Call Ollama local model for final answer generation"""
    expand_res = ollama.chat(
        model=modelName,
        messages=[
            {"role": "system", "content": sysPrompt},
            {"role": "user", "content": usrPrompt}
        ],
        options={"temperature": temp}
    )
    return expand_res


class ChatWithThreadPipeline:
    """Pipeline for chatting with email threads using RAG"""
    
    def __init__(self):
        self.db_path = DB_PATH
        self.setup_database()
        # OpenAI for tool calling only
        local_cfg = _load_local_config()
        openai_key = local_cfg.get('OPENAI_KEY') or getattr(settings, 'OPENAI_API_KEY', None)
        self.tool_caller_llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            api_key=openai_key
        )
    
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
    
    def get_user_chroma_client(self, user_id: str):
        """Get or create ChromaDB client for a specific user"""
        user_chroma_path = os.path.join(BASE_PATH, f"cdb_{user_id}")
        os.makedirs(user_chroma_path, exist_ok=True)
        return chromadb.PersistentClient(path=user_chroma_path)
    
    def get_user_collection(self, user_id: str, collection_name: str = "email_threads"):
        """Get or create collection for a user's email threads"""
        client = self.get_user_chroma_client(user_id)
        return client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
    
    def call_embed_api(self, text: str) -> List[float]:
        """Get embedding from Flask API"""
        try:
            response = requests.post(
                FLASK_EMBED_URL,
                json={"text": text},
                timeout=30
            )
            response.raise_for_status()
            return response.json()["embedding"]
        except Exception as e:
            logger.error(ERROR_EMBEDDING_API.format(error=e))
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
            
            logger.info(INFO_FOUND_EXISTING_MESSAGES.format(count=len(existing_message_ids), thread_id=thread_id))
            return existing_message_ids
            
        except Exception as e:
            logger.error(f"Error fetching existing message IDs: {e}")
            return set()
    
    def load_thread_data(self, thread_id: str) -> Optional[Dict]:
        """Load thread data from single JSON file"""
        file_path = os.path.join(EMAIL_LOGS_PATH, thread_id, f"{thread_id}.json")
        
        try:
            if not os.path.exists(file_path):
                logger.warning(f"Thread file not found: {file_path}")
                return None
                
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(ERROR_LOADING_THREAD.format(file_path=file_path, error=e))
            return None
    
    def get_thread_messages(self, thread_id: str) -> List[Dict]:
        """Get all messages from thread JSON file"""
        thread_data = self.load_thread_data(thread_id)
        
        if not thread_data:
            logger.warning(WARNING_NO_THREAD_DATA.format(thread_id=thread_id))
            return []
        
        messages = thread_data.get('messages', [])
        logger.info(INFO_FOUND_THREAD_MESSAGES.format(count=len(messages), thread_id=thread_id))
        return messages
    
    def get_unprocessed_messages(self, user_id: str, thread_id: str) -> List[Dict]:
        """Filter out already processed messages and return unprocessed ones"""
        existing_message_ids = self.get_existing_message_ids_from_chroma(user_id, thread_id)
        all_messages = self.get_thread_messages(thread_id)
        
        unprocessed_messages = [
            msg for msg in all_messages 
            if msg.get('message_id') not in existing_message_ids
        ]
        
        logger.info(INFO_UNPROCESSED_MESSAGES.format(
            unprocessed_count=len(unprocessed_messages),
            total_count=len(all_messages)
        ))
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
            
            if not text_to_embed or text_to_embed == "Subject: \n\nBody: ":
                logger.warning(WARNING_EMPTY_CONTENT.format(message_id=message_id))
                return
            
            metadata = {
                "thread_id": thread_id,
                "message_id": message_id,
                "timestamp": timestamp,
                "type": "email_data",
                "subject": subject,
                "from": from_email,
                "to": to_email
            }
            
            embedding = self.call_embed_api(text_to_embed)
            collection = self.get_user_collection(user_id)
            doc_id = f"{user_id}_{thread_id}_{message_id}"
            
            collection.add(
                documents=[text_to_embed],
                embeddings=[embedding],
                ids=[doc_id],
                metadatas=[metadata]
            )
            
            self.mark_message_processed(user_id, thread_id, message_id)
            logger.info(MESSAGE_PROCESSED_SUCCESS.format(message_id=message_id))
            
        except Exception as e:
            logger.error(ERROR_PROCESSING_MESSAGE.format(message_id=message_id, error=e))
            raise
    
    def mark_message_processed(self, user_id: str, thread_id: str, message_id: str):
        """Mark message as processed in database"""
        conn = sqlite3.connect(self.db_path)
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
        conn = sqlite3.connect(self.db_path)
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
    
    def get_thread_attachments(self, thread_id: str) -> List[Dict]:
        """Get all attachments for a thread from the file system"""
        thread_path = os.path.join(EMAIL_ATTACHMENTS_PATH, thread_id)
        
        if not os.path.exists(thread_path):
            logger.warning(WARNING_NO_ATTACHMENTS.format(thread_id=thread_id))
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
                    logger.error(ERROR_READING_METADATA.format(metadata_file=metadata_file, error=e))
        
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
            documents = SimpleDirectoryReader(
                input_files=[attachment_path],
                file_extractor=FILE_EXTRACTOR
            ).load_data()
            
            if not documents:
                logger.warning(f"No content extracted from {attachment_path}")
                return
            
            collection = self.get_user_collection(user_id)
            
            for idx, doc in enumerate(documents):
                text = doc.text.strip()
                if not text:
                    continue
                
                metadata = {
                    "message_id": message_id,
                    "thread_id": thread_id,
                    "attachment_id": attachment_id,
                    "filename": os.path.basename(attachment_path),
                    "chunk_index": str(idx),
                    "type": "attachment_data"
                }
                
                embedding = self.call_embed_api(text)
                doc_id = f"{user_id}_{thread_id}_{attachment_id}_{idx}"
                
                collection.add(
                    documents=[text],
                    embeddings=[embedding],
                    ids=[doc_id],
                    metadatas=[metadata]
                )
                
                logger.info(f"Stored chunk {idx} for attachment {attachment_id}")
            
            self.mark_attachment_processed(user_id, thread_id, message_id, attachment_id)
            logger.info(ATTACHMENT_PROCESSED_SUCCESS.format(attachment_id=attachment_id))
            
        except Exception as e:
            logger.error(ERROR_PROCESSING_ATTACHMENT.format(attachment_path=attachment_path, error=e))
            raise
    
    def mark_attachment_processed(self, user_id: str, thread_id: str, 
                                  message_id: str, attachment_id: str):
        """Mark attachment as processed in database"""
        conn = sqlite3.connect(self.db_path)
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
        logger.info(EMAIL_PROCESSING_START.format(user_id=user_id, thread_id=thread_id))
        
        processing_info = {
            'total_messages': 0,
            'already_processed': 0,
            'newly_processed': 0,
            'errors': []
        }
        
        try:
            all_messages = self.get_thread_messages(thread_id)
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
            
            logger.info(EMAIL_PROCESSING_COMPLETE.format(processing_info=processing_info))
            return processing_info
            
        except Exception as e:
            logger.error(ERROR_THREAD_PROCESSING.format(error=e))
            processing_info['errors'].append(str(e))
            return processing_info
    
    def process_thread_attachments(self, user_id: str, thread_id: str, message_id: str = None) -> Dict:
        """Process all unprocessed attachments in a thread"""
        logger.info(ATTACHMENT_PROCESSING_START.format(thread_id=thread_id))
        
        attachment_info = {
            'attachments_found': 0,
            'attachments_processed': 0,
            'attachments_skipped': 0,
            'errors': []
        }
        
        try:
            attachments = self.get_thread_attachments(thread_id)
            attachment_info['attachments_found'] = len(attachments)
            
            logger.info(INFO_FOUND_ATTACHMENTS.format(count=len(attachments), thread_id=thread_id))
            
            for attachment in attachments:
                attachment_id = attachment.get('attachment_id') or attachment.get('filename')
                attachment_path = attachment.get('path')
                attach_message_id = attachment.get('message_id', message_id or thread_id)
                
                if not attachment_path or not os.path.exists(attachment_path):
                    logger.warning(WARNING_ATTACHMENT_PATH_NOT_FOUND.format(attachment_path=attachment_path))
                    continue
                
                if self.check_attachment_processed(user_id, thread_id, attachment_id):
                    logger.info(ATTACHMENT_PROCESSING_SKIP.format(attachment_id=attachment_id))
                    attachment_info['attachments_skipped'] += 1
                    continue
                
                try:
                    self.process_attachment(
                        user_id, thread_id, attach_message_id,
                        attachment_path, attachment_id
                    )
                    attachment_info['attachments_processed'] += 1
                except Exception as e:
                    error_msg = f"Failed to process {attachment_id}: {str(e)}"
                    logger.error(error_msg)
                    attachment_info['errors'].append(error_msg)
            
            return attachment_info
            
        except Exception as e:
            logger.error(ERROR_ATTACHMENT_PROCESSING.format(error=e))
            attachment_info['errors'].append(str(e))
            return attachment_info
    
    def _search_thread_emails_internal(self, user_id: str, thread_id: str, 
                                       query: str, k: int = 5) -> str:
        """Internal method to search email messages"""
        logger.info(INFO_SEARCHING_EMAILS.format(query=query))
        
        collection = self.get_user_collection(user_id)
        query_embedding = self.call_embed_api(query)
        
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where={
                "$and": [
                    {"thread_id": thread_id},
                    {"type": "email_data"}
                ]
            },
            include=["documents", "metadatas", "distances"]
        )
        
        docs = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        
        if not docs:
            return NO_EMAILS_FOUND
        
        response_parts = [EMAIL_SEARCH_RESULTS_HEADER]
        for idx, (doc, meta, distance) in enumerate(zip(docs, metadatas, distances), 1):
            timestamp = meta.get('timestamp', 'Unknown')
            from_email = meta.get('from', 'Unknown')
            subject = meta.get('subject', 'No subject')
            message_id = meta.get('message_id', 'Unknown')
            
            response_parts.append(
                format_email_result(
                    index=idx,
                    relevance=1-distance,
                    message_id=message_id,
                    from_email=from_email,
                    subject=subject,
                    timestamp=timestamp,
                    content=doc
                )
            )
        
        return "\n".join(response_parts)
    
    def _search_attachments_internal(self, user_id: str, thread_id: str, 
                                    query: str, k: int = 3) -> str:
        """Internal method to search attachment content"""
        logger.info(INFO_SEARCHING_ATTACHMENTS.format(query=query))
        
        collection = self.get_user_collection(user_id)
        query_embedding = self.call_embed_api(query)
        
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where={
                "$and": [
                    {"thread_id": thread_id},
                    {"type": "attachment_data"}
                ]
            },
            include=["documents", "metadatas", "distances"]
        )
        
        docs = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        
        if not docs:
            return NO_ATTACHMENTS_FOUND
        
        response_parts = [ATTACHMENT_SEARCH_RESULTS_HEADER]
        for idx, (doc, meta, distance) in enumerate(zip(docs, metadatas, distances), 1):
            filename = meta.get('filename', 'Unknown')
            chunk_index = meta.get('chunk_index', '0')
            response_parts.append(
                format_attachment_result(
                    index=idx,
                    relevance=1-distance,
                    filename=filename,
                    chunk_index=chunk_index,
                    content=doc
                )
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
        Hybrid approach: OpenAI for tool selection, Ollama for final answer
        
        Flow:
        1. OpenAI LLM decides which tools to call
        2. Execute the tools to retrieve context
        3. Pass context to Ollama for final answer generation
        """
        logger.info(INFO_HYBRID_CHAT_START.format(thread_id=thread_id, user_question=user_question))
    
        # Step 1: Tool binding
        tools = self.create_tools_for_binding()
        llm_with_tools = self.tool_caller_llm.bind_tools(tools)
    
        # Proper structured tool-calling prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", TOOL_CALLING_SYSTEM_PROMPT),
            ("human", "{question}")
        ])
    
        chain = prompt | llm_with_tools
    
        # Get tool calls from OpenAI
        ai_response = chain.invoke({
            "question": user_question
        })
    
        logger.info(INFO_OPENAI_RESPONSE.format(response=ai_response))
    
        # Step 2: Execute tool calls
        retrieved_context = []
    
        if hasattr(ai_response, "tool_calls") and ai_response.tool_calls:
            logger.info(INFO_TOOL_CALLS_DETECTED.format(tool_calls=ai_response.tool_calls))
    
            for tool_call in ai_response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call.get("args", {})
    
                logger.info(INFO_TOOL_EXECUTION.format(tool_name=tool_name, tool_args=tool_args))
    
                if tool_name == "search_thread_emails":
                    query = tool_args.get("query", user_question)
                    k = tool_args.get("k", 5)
    
                    result = self._search_thread_emails_internal(
                        user_id, thread_id, query, k
                    )
                    retrieved_context.append(result)
    
                elif tool_name == "search_attachments":
                    query = tool_args.get("query", user_question)
                    k = tool_args.get("k", 3)
    
                    result = self._search_attachments_internal(
                        user_id, thread_id, query, k
                    )
                    retrieved_context.append(result)
    
        else:
            # Fallback: search both
            logger.warning(WARNING_NO_TOOL_CALLS)
    
            email_results = self._search_thread_emails_internal(
                user_id, thread_id, user_question, 5
            )
            attachment_results = self._search_attachments_internal(
                user_id, thread_id, user_question, 3
            )
    
            retrieved_context.append(email_results)
            retrieved_context.append(attachment_results)
    
        # Step 3: Combine retrieved context
        combined_context = "\n\n".join(retrieved_context)
        logger.info(INFO_CONTEXT_LENGTH.format(length=len(combined_context)))
    
        # Step 4: Ollama final answer generation
        system_prompt = get_final_answer_system_prompt(thread_id, user_id)
        user_prompt = get_final_answer_user_prompt(user_question, combined_context)
    
        logger.info(INFO_OLLAMA_CALLING)
    
        ollama_response = call_ollama_chat_params(
            modelName=OLLAMA_MODEL,
            sysPrompt=system_prompt,
            usrPrompt=user_prompt,
            temp=OLLAMA_TEMP
        )
    
        final_answer = ollama_response["message"]["content"]
    
        logger.info(HYBRID_CHAT_COMPLETE)
    
        return final_answer
    
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
            
            logger.info(HYBRID_CHAT_COMPLETE)
            
            return {
                "success": True,
                "answer": answer,
                "processing_info": {
                    "emails": email_processing_info,
                    "attachments": attachment_processing_info
                }
            }
            
        except Exception as e:
            logger.error(ERROR_PIPELINE.format(error=e))
            return {
                'success': False,
                'error': str(e),
                'answer': None
            }
