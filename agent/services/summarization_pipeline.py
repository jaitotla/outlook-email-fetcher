"""
Email Thread Summarization Pipeline
Processes email threads and generates structured summaries using external LLM API
Stores summaries in ChromaDB with real-time incremental updates
"""
import os
import json
import logging
import requests
import asyncio
import chromadb
import re
import sqlite3
import concurrent.futures
from typing import Dict, List, Optional, Any, Set
from datetime import datetime

from agent.services.llm import LLMService
from agent.services.settings_manager import SettingsManager
from agent.services.embeddings import EmbeddingService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Base data directory - point to backend/data (not agent/data)
# From: openmailbot/agent/services/summarization_pipeline.py
# To: openmailbot/backend/data
BASE_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),  # openmailbot/
    "backend",
    "data"
)
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


# ═══════════════════════════════════════════════════════════════════════════════
# SIMPLE SUMMARIZATION PROMPT (for < 3 emails)
# ═══════════════════════════════════════════════════════════════════════════════

SIMPLE_SUMMARIZATION_PROMPT_TEMPLATE = """You are a professional email analyst.

Briefly summarize these {email_count} emails in a clear, point-form summary.

### Format:
- **Topic:** <main subject>
- **Participants:** <people involved>
- **Key Points:** <3-5 bullet points of main information>
- **Current Status:** <what needs to happen next>
- **Action Required:** <what is being asked or expected>

### Emails to Summarize:

{email_thread_text}

---

Provide ONLY the summary in the format above. Be concise and factual.
"""

# ═══════════════════════════════════════════════════════════════════════════════
# DETAILED SUMMARIZATION PROMPT (for >= 3 emails)
# ═══════════════════════════════════════════════════════════════════════════════

Breakdown_summarization = """
You are an expert enterprise communication analyst.

You will receive:
1. An **EXISTING SUMMARY** of previous emails
2. **NEW EMAILS** that continue the conversation

Your task: Update the existing summary by incorporating the new emails while preserving the exact structure and format.

---

## Update Instructions

### What to KEEP:
- All section headers and numbering (1️⃣, 2️⃣, 3️⃣, etc.)
- All existing timeline steps unless they need updates
- Original wording and phrasing
- Professional tone and formatting

### What to UPDATE:

**Section 1️⃣ - Conversation Overview**
- Add new participants if any
- Update Time Range end date
- Keep Topic unchanged unless major shift

**Section 2️⃣ - Chronological Timeline**
- Keep all existing steps AS-IS
- Add new steps for events in new emails
- Continue numbering (if you see Step 5, add Step 6, Step 7...)
- Mark with [UPDATED] ONLY if new emails show outcome of pending actions

**Section 3️⃣ - Current Status**
- Replace entirely based on latest email

**Section 4️⃣ - Open Questions / Pending Requests**
- Remove resolved items
- Add new questions from new emails

**Section 5️⃣ - Final Ask / Next Expected Action**
- Replace with the most recent ask

**Section 6️⃣ - Draft Response Email**
- Rewrite based on current state
- Sign as "Puja from AcmeAI"

---

## INPUT DATA

### EXISTING SUMMARY
{PREVIOUS_SUMMARY}

### NEW EMAILS
{new_email}

---

## OUTPUT FORMAT

Provide ONLY the updated summary. Do NOT include:
- Explanations of what you changed
- Meta-commentary about the update process
- Section labels like "REMOVE" or "KEEP"
- Any text outside the 6 sections

Start directly with:

#### 1️⃣ Conversation Overview
...

"""

class SummarizationPipeline:
    """Pipeline for summarizing email threads using external LLM API
    
    Features:
    - Stores summaries in ChromaDB per thread_id (no duplicates)
    - Tracks message IDs to detect new emails
    - Uses simple prompt for < 3 emails, detailed prompt for >= 3
    - Supports real-time incremental updates via breakdown_summary
    - Returns cached summary if no new emails
    """
    
    def __init__(self, user_id: Optional[str] = None):
        """
        Initialize summarization pipeline
        
        Args:
            user_id: User identifier for scoped operations
        """
        self.user_id = user_id
        self.db_path = os.path.join(BASE_DATA_DIR, "chat_thread_processing.db")
        self.setup_database()
        
        # Load user settings
        try:
            settings_manager = SettingsManager(user_id)
            # Fixed: Pass setting_type as keyword argument, not positional
            retrieved_settings = settings_manager.get_settings(setting_type="general")
            logger.info(f"Retrieved settings for user {user_id} (type: general)")
            # Ensure settings is a dict, not None
            self.effective_settings = retrieved_settings if retrieved_settings else {}
        except Exception as e:
            logger.warning(f"Failed to load settings for user {user_id}: {e}. Using defaults.")
            self.effective_settings = {}
        
        # Extract LLM provider info from settings with safe defaults
        self.llm_provider = self.effective_settings.get('llm_provider') 
        self.llm_model = self.effective_settings.get('llm_model') 
        
        # Initialize LLM service with user settings
        try:
            self.llm_service = LLMService(self.effective_settings)
            logger.info(f"✅ SummarizationPipeline initialized for user: {user_id}")
            logger.info(f"   LLM Provider: {self.llm_provider}")
            logger.info(f"   LLM Model: {self.llm_model}")
        except Exception as e:
            logger.error(f"Failed to initialize LLMService: {e}")
            raise
        
        # Initialize EmbeddingService for summary embeddings
        try:
            # Add user_id to effective_settings for EmbeddingService
            embedding_settings = self.effective_settings.copy() if self.effective_settings else {}
            embedding_settings["user_id"] = user_id
            self.embedding_service = EmbeddingService(effective_settings=embedding_settings)
            logger.info(f"✅ EmbeddingService initialized for user: {user_id}")
        except Exception as e:
            logger.warning(f"Failed to initialize EmbeddingService: {e}")
            self.embedding_service = None
    
    def setup_database(self):
        """Initialize SQLite database for tracking processed thread summaries"""
        os.makedirs(BASE_DATA_DIR, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table for tracking thread summaries
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS thread_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                thread_id TEXT NOT NULL,
                summary_id TEXT NOT NULL,
                message_ids_json TEXT,
                cached_summary TEXT,
                cached_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, thread_id)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("✅ Thread summaries database initialized")
    
    def ensure_user_db(self, user_id: str):
        """Ensure per-user sqlite DB for thread summaries exists."""
        user_db = os.path.join(BASE_DATA_DIR, user_id, "sql_data", "chat_thread_processing.db")
        os.makedirs(os.path.dirname(user_db), exist_ok=True)
        conn = sqlite3.connect(user_db)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS thread_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                thread_id TEXT NOT NULL,
                summary_id TEXT NOT NULL,
                message_ids_json TEXT,
                cached_summary TEXT,
                cached_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, thread_id)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"✅ Initialized per-user summary DB at {user_db}")
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # ChromaDB Methods (Vector Store for Summaries)
    # ═══════════════════════════════════════════════════════════════════════════════
    
    def get_user_chroma_client(self, user_id: str):
        """Get or create ChromaDB client for a specific user"""
        user_vector_path = os.path.join(BASE_DATA_DIR, user_id, "vector_db")
        os.makedirs(user_vector_path, exist_ok=True)
        user_chroma_path = os.path.join(user_vector_path, f"cdb_{user_id}")
        os.makedirs(user_chroma_path, exist_ok=True)
        return chromadb.PersistentClient(path=user_chroma_path)
    
    def get_summary_collection(self, user_id: str, collection_name: str = "thread_summaries"):
        """Get or create ChromaDB collection for storing thread summaries"""
        client = self.get_user_chroma_client(user_id)
        try:
            return client.get_collection(name=collection_name)
        except Exception:
            return client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
    
    def get_existing_message_ids_from_thread(self, thread_data: Dict) -> Set[str]:
        """Extract all message IDs from thread JSON data"""
        messages = thread_data.get('messages', [])
        message_ids = {msg.get('message_id') for msg in messages if msg.get('message_id')}
        logger.info(f"📬 Found {len(message_ids)} message IDs in thread data")
        return message_ids
    
    def get_cached_summary(self, user_id: str, thread_id: str) -> Optional[Dict]:
        """
        Retrieve cached summary from ChromaDB for a thread
        
        Returns: Dict with summary_text, message_ids_set, or None if not found
        """
        try:
            collection = self.get_summary_collection(user_id)
            summary_id = f"{user_id}_{thread_id}_summary"
            
            # Query ChromaDB for this thread's summary
            results = collection.get(ids=[summary_id])
            
            if not results or not results['ids']:
                logger.info(f"📭 No cached summary found for thread {thread_id}")
                return None
            
            # Extract metadata and document
            metadata = results['metadatas'][0] if results['metadatas'] else {}
            summary_text = results['documents'][0] if results['documents'] else None
            
            if not summary_text:
                logger.warning(f"⚠️  Summary document is empty for thread {thread_id}")
                return None
            
            # Parse message IDs from metadata
            message_ids_str = metadata.get('message_ids', '[]')
            try:
                message_ids_set = set(json.loads(message_ids_str))
            except:
                message_ids_set = set()
            
            logger.info(f"✅ Retrieved cached summary for thread {thread_id}")
            logger.info(f"   Cached message count: {len(message_ids_set)}")
            
            return {
                'summary_text': summary_text,
                'message_ids_set': message_ids_set,
                'metadata': metadata
            }
            
        except Exception as e:
            logger.error(f"❌ Error retrieving cached summary: {e}")
            return None
    
    def store_summary_in_chromadb(self, user_id: str, thread_id: str, summary_text: str, 
                                  message_ids: Set[str], all_message_ids_count: int):
        """
        Store or update summary in ChromaDB
        
        Always updates existing summary (no duplicates per thread_id)
        """
        try:
            if not self.embedding_service:
                logger.warning("⚠️  EmbeddingService not available, skipping ChromaDB storage")
                return
            
            collection = self.get_summary_collection(user_id)
            summary_id = f"{user_id}_{thread_id}_summary"
            
            # Generate embedding for summary
            embedding = self._get_embedding_sync(summary_text)
            
            metadata = {
                "type": "summary",
                "thread_id": thread_id,
                "message_ids": json.dumps(list(message_ids)),
                "message_count": str(all_message_ids_count),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Update or create in ChromaDB (always overwrites existing)
            collection.upsert(
                ids=[summary_id],
                embeddings=[embedding],
                documents=[summary_text],
                metadatas=[metadata]
            )
            
            logger.info(f"✅ Stored summary in ChromaDB for thread {thread_id}")
            logger.info(f"   Summary ID: {summary_id}")
            logger.info(f"   Message IDs tracked: {len(message_ids)}")
            logger.info(f"   Total emails in thread: {all_message_ids_count}")
            
        except Exception as e:
            logger.error(f"❌ Error storing summary in ChromaDB: {e}")
            import traceback
            traceback.print_exc()
    
    def _get_embedding_sync(self, text: str) -> List[float]:
        """Synchronous wrapper for async embedding generation"""
        try:
            coro = self.embedding_service.generate_embedding(text)
            return self._run_async_task(coro)
        except Exception as e:
            logger.error(f"❌ Error generating embedding: {e}")
            # Return dummy embedding on error
            return [0.0] * 1536
    
    def _run_async_task(self, coro):
        """Run async coroutine from sync context in a new thread"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(self._run_in_new_loop, coro).result()
    
    def _run_in_new_loop(self, coro):
        """Run coroutine in a brand-new event loop (called from worker thread)"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    
    def get_thread_json_data(self, user_id: str, thread_id: str) -> Optional[Dict]:
        """
        Load thread data from JSON file
        Path: data/{user_id}/log_emails/{thread_id}/{thread_id}.json
        
        Args:
            user_id: User identifier
            thread_id: Gmail thread ID
            
        Returns:
            Thread data dict or None if not found
        """
        file_path = os.path.join(
            BASE_DATA_DIR, 
            user_id, 
            "log_emails", 
            thread_id, 
            f"{thread_id}.json"
        )
        
        try:
            if not os.path.exists(file_path):
                logger.warning(f"❌ Thread file not found: {file_path}")
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                thread_data = json.load(f)
                logger.info(f"✅ Loaded thread data from: {file_path}")
                logger.info(f"   Messages found: {len(thread_data.get('messages', []))}")
                return thread_data
                
        except Exception as e:
            logger.error(f"❌ Error loading thread JSON {file_path}: {e}")
            return None
    
    def detect_new_messages(self, current_message_ids: Set[str], cached_message_ids: Set[str]) -> Set[str]:
        """
        Detect new messages that arrived since last summary
        
        Args:
            current_message_ids: Message IDs from current thread JSON
            cached_message_ids: Message IDs from cached summary in ChromaDB
            
        Returns:
            Set of NEW message IDs (not in cached summary)
        """
        new_messages = current_message_ids - cached_message_ids
        logger.info(f"🔍 New message detection:")
        logger.info(f"   Current messages: {len(current_message_ids)}")
        logger.info(f"   Cached messages: {len(cached_message_ids)}")
        logger.info(f"   New messages: {len(new_messages)}")
        return new_messages
    
    def get_new_emails_text(self, thread_data: Dict, new_message_ids: Set[str]) -> str:
        """
        Extract only the new emails from thread data
        
        Args:
            thread_data: Full thread data
            new_message_ids: Set of message IDs to extract
            
        Returns:
            Formatted text of new emails
        """
        messages = thread_data.get('messages', [])
        new_emails = [msg for msg in messages if msg.get('message_id') in new_message_ids]
        
        logger.info(f"📧 Formatting {len(new_emails)} new emails for breakdown update...")
        
        formatted_emails = []
        for idx, msg in enumerate(new_emails, 1):
            from_addr = msg.get('from', 'Unknown')
            subject = msg.get('subject', '(No Subject)')
            timestamp = msg.get('timestamp', 'Unknown')
            body = msg.get('body', '(No Content)')
            
            email_block = f"""
--- NEW EMAIL #{idx} ---
From: {from_addr}
Subject: {subject}
Date: {timestamp}

{body}
"""
            formatted_emails.append(email_block)
        
        return "\n".join(formatted_emails)

    
    def format_email_thread_for_analysis(self, thread_data: Dict) -> str:
        """
        Format thread data into readable email format for LLM analysis
        
        Args:
            thread_data: Thread data dict from JSON
            
        Returns:
            Formatted email text
        """
        if not thread_data:
            return ""
        
        messages = thread_data.get('messages', [])
        formatted_emails = []
        
        logger.info(f"📧 Formatting {len(messages)} emails for analysis...")
        
        for idx, msg in enumerate(messages, 1):
            # Extract message fields
            from_addr = msg.get('from', 'Unknown')
            to_addrs = msg.get('to', [])
            subject = msg.get('subject', '(No Subject)')
            timestamp = msg.get('timestamp', 'Unknown')
            body = msg.get('body', '(No Content)')
            
            # Format email block
            email_block = f"""
--- EMAIL #{idx} ---
From: {from_addr}
To: {', '.join(to_addrs) if isinstance(to_addrs, list) else to_addrs}
Subject: {subject}
Date: {timestamp}

{body}
"""
            formatted_emails.append(email_block)
        
        full_thread = "\n".join(formatted_emails)
        logger.info(f"✅ Formatted {len(formatted_emails)} emails ({len(full_thread)} chars total)")
        return full_thread
    
    def create_summarization_prompt(self, email_thread_text: str, email_count: int) -> str:
        """
        Create the summarization prompt - simple for < 3 emails, detailed for >= 3
        
        Args:
            email_thread_text: Formatted email thread text
            email_count: Number of emails in the thread
            
        Returns:
            Complete prompt for LLM
        """
        if email_count < 3:
            # Use simple prompt for < 3 emails
            logger.info(f"📝 Using SIMPLE summarization prompt ({email_count} emails)")
            prompt = SIMPLE_SUMMARIZATION_PROMPT_TEMPLATE.format(
                email_count=email_count,
                email_thread_text=email_thread_text
            )
        else:
            # Use detailed prompt for >= 3 emails
            logger.info(f"📝 Using DETAILED summarization prompt ({email_count} emails)")
            prompt = f"""You are an expert enterprise communication analyst.

You will be given a batch of related email threads that belong to the same conversation.

Your task is to analyze ALL emails carefully and produce a **chronological, structured summary**.

### Instructions
1. Read every email in full.
2. Identify the **true chronological order** based on timestamps and context.
3. Merge replies and forwards logically (do not repeat content).
4. Ignore greetings, signatures, and disclaimers unless they add meaning.
5. Focus on decisions, requests, approvals, blockers, and commitments.

---

### Output Format (STRICT)

#### 1️⃣ Conversation Overview
- **Topic:** <one-line summary of what this email thread is about>
- **Participants:** <key people and their roles>
- **Time Range:** <first email date → last email date>

---

#### 2️⃣ Chronological Timeline of Events
(List in exact order — earliest to latest)

**Step 1 – <Short Title>**
- What happened: <one concise line>
- Outcome / Decision: <if any>
- Expectation / Ask at this stage: <what was requested or expected next>

**Step 2 – <Short Title>**
- What happened: <one concise line>
- Outcome / Decision: <if any>
- Expectation / Ask at this stage: <what was requested or expected next>

(Repeat for all major events. Use **2 lines only** if the event is large or critical.)

---

#### 3️⃣ Current Status (As of Last Email)
- **Current State:** <e.g., Awaiting approval / In progress / Blocked / Completed>
- **Owner:** <person responsible now>
- **Pending Actions:** <bullet list if multiple>

---

#### 4️⃣ Open Questions / Pending Requests
(List anything that is still unanswered or waiting)

- <Question or request>
- <Who needs to respond>

---

#### 5️⃣ Final Ask / Next Expected Action
(Clearly state what the sender expects next)

- **Action Required:** <clear action>
- **From Whom:** <person/team>
- **Deadline (if mentioned):** <date or "Not specified">

---

### Rules
- Be factual and neutral.
- DO NOT invent information.
- DO NOT summarize per email — summarize per **event**.
- Keep language professional and concise.
- Prefer clarity over verbosity.

---

## EMAIL THREAD TO ANALYZE:

{email_thread_text}

---

Please provide the structured summary following the exact format above.
"""
        
        logger.info(f"✅ Created summarization prompt ({len(prompt)} chars)")
        return prompt
    
    
    async def breakdown_summary_with_new_emails(self, previous_summary: str, new_emails_text: str) -> Optional[str]:
        """
        Update existing summary with new emails using breakdown_summary prompt
        
        This is called when new emails arrive and we want to incrementally update
        rather than re-summarizing the entire thread from scratch.
        
        Args:
            previous_summary: The cached summary from ChromaDB
            new_emails_text: Formatted text of newly arrived emails
            
        Returns:
            Updated summary text or None on failure
        """
        logger.info("🔄 Performing real-time summary update with new emails...")
        logger.info(f"   Previous summary length: {len(previous_summary)} chars")
        logger.info(f"   New emails length: {len(new_emails_text)} chars")
        
        # Use the breakdown summarization prompt template to update
        breakdown_prompt = f"""You are an expert enterprise communication analyst.

You will receive:
1. An **EXISTING SUMMARY** of previous emails
2. **NEW EMAILS** that continue the conversation

Your task: Update the existing summary by incorporating the new emails while preserving the exact structure and format.

---

## Update Instructions

### What to KEEP:
- All section headers and numbering (1️⃣, 2️⃣, 3️⃣, etc.)
- All existing timeline steps unless they need updates
- Original wording and phrasing
- Professional tone and formatting

### What to UPDATE:

**Section 1️⃣ - Conversation Overview**
- Add new participants if any
- Update Time Range end date
- Keep Topic unchanged unless major shift

**Section 2️⃣ - Chronological Timeline**
- Keep all existing steps AS-IS
- Add new steps for events in new emails
- Continue numbering (if you see Step 5, add Step 6, Step 7...)
- Mark with [UPDATED] ONLY if new emails show outcome of pending actions

**Section 3️⃣ - Current Status**
- Replace entirely based on latest email

**Section 4️⃣ - Open Questions / Pending Requests**
- Remove resolved items
- Add new questions from new emails

**Section 5️⃣ - Final Ask / Next Expected Action**
- Replace with the most recent ask

**Section 6️⃣ - Draft Response Email** (if present)
- Rewrite based on current state

---

## INPUT DATA

### EXISTING SUMMARY
{previous_summary}

### NEW EMAILS
{new_emails_text}

---

## OUTPUT FORMAT

Provide ONLY the updated summary. Do NOT include:
- Explanations of what you changed
- Meta-commentary about the update process
- Section labels like "REMOVE" or "KEEP"
- Any text outside the existing sections

Start directly with the updated content (1️⃣ Conversation Overview, etc.)

---
"""
        
        try:
            messages = [
                {"role": "system", "content": "You are an expert at updating email summaries with new information while maintaining structure and context."},
                {"role": "user", "content": breakdown_prompt}
            ]
            
            updated_summary = await self.llm_service.generate(
                messages,
                provider=self.llm_provider,
                model=self.llm_model,
                temperature=0.7,
                max_tokens=4000
            )
            
            logger.info(f"✅ Summary update successful")
            logger.info(f"✅ Updated summary length: {len(updated_summary)} characters")
            
            return updated_summary
            
        except Exception as e:
            logger.error(f"❌ Breakdown summary failed: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def call_llm_api_async(self, prompt: str) -> Optional[str]:
        """
        Call LLM service with the summarization prompt
        
        Args:
            prompt: Complete prompt for summarization
            
        Returns:
            LLM response text or None on failure
        """
        # Determine the actual model that will be used
        # Manotr/inbuilt provider uses hardcoded llama3.2 in utils.py, ignoring configured model
        actual_model = self.llm_model
        if self.llm_provider in ("manotr", "inbuilt"):
            actual_model = "llama3.2"  # Hardcoded in utils.py call_chat_api()
            logger.info(f"🚀 Calling LLM via {self.llm_provider}")
            logger.info(f"   Configured Model: {self.llm_model} (ignored for {self.llm_provider})")
            logger.info(f"   Actual Model: {actual_model}")
        else:
            logger.info(f"🚀 Calling LLM via {self.llm_provider}")
            logger.info(f"   Model: {actual_model}")
        logger.info(f"   Prompt size: {len(prompt)} characters")
        
        try:
            # Build messages for LLM
            messages = [
                {"role": "system", "content": "You are an expert enterprise communication analyst specializing in email summarization."},
                {"role": "user", "content": prompt}
            ]
            
            # Call LLM service
            summary_text = await self.llm_service.generate(
                messages,
                provider=self.llm_provider,
                model=self.llm_model,
                temperature=0.7,
                max_tokens=4000
            )
            
            logger.info(f"✅ LLM call successful")
            logger.info(f"✅ Summary generated: {len(summary_text)} characters")
            
            return summary_text
            
        except Exception as e:
            logger.error(f"❌ LLM call failed: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def process_and_summarize(self, user_id: str, thread_id: str) -> Dict[str, Any]:
        """
        Main pipeline with intelligent caching and real-time updates
        
        Flow:
        1. Load thread data from JSON
        2. Check for cached summary in ChromaDB
        3. If cached exists:
           a. Compare message IDs to detect new emails
           b. If NO new emails: Return cached summary (requirement #5)
           c. If NEW emails: Use breakdown_summary to update (requirement #4)
        4. If no cached: Create full summary (first-time)
        5. Store/update summary in ChromaDB (requirement #3)
        
        Args:
            user_id: User identifier
            thread_id: Gmail thread ID
            
        Returns:
            Dict with success status, summary, and metadata
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"🚀 SUMMARIZATION PIPELINE START (v2 - with caching)")
        logger.info(f"{'='*80}")
        logger.info(f"User ID:    {user_id}")
        logger.info(f"Thread ID:  {thread_id}")
        logger.info(f"{'='*80}\n")
        
        result = {
            'success': False,
            'thread_id': thread_id,
            'user_id': user_id,
            'summary': None,
            'error': None,
            'processing_mode': None,  # 'cached', 'breakdown', or 'full'
            'metadata': {
                'timestamp': datetime.utcnow().isoformat(),
                'messages_processed': 0,
                'api_call_time': 0,
                'new_messages_detected': 0
            }
        }
        
        try:
            # ═══════════════════════════════════════════════════════════════════════════
            # STEP 1: Load thread data
            # ═══════════════════════════════════════════════════════════════════════════
            logger.info("📂 STEP 1: Loading thread data from JSON...")
            thread_data = self.get_thread_json_data(user_id, thread_id)
            
            if not thread_data:
                raise ValueError(f"Could not load thread data for thread_id={thread_id}")
            
            # Get all current message IDs from the thread
            current_message_ids = self.get_existing_message_ids_from_thread(thread_data)
            num_messages = len(thread_data.get('messages', []))
            result['metadata']['messages_processed'] = num_messages
            
            logger.info(f"✅ Loaded {num_messages} messages from thread")
            
            # ═══════════════════════════════════════════════════════════════════════════
            # STEP 2: Check for cached summary in ChromaDB
            # ═══════════════════════════════════════════════════════════════════════════
            logger.info("\n🔍 STEP 2: Checking for cached summary in ChromaDB...")
            cached_result = self.get_cached_summary(user_id, thread_id)
            
            if cached_result:
                # ══════════════════════════════════════════════════════════════════════
                # STEP 3A: Cached summary exists - detect new emails
                # ══════════════════════════════════════════════════════════════════════
                logger.info("✅ Cached summary found!")
                
                cached_message_ids = cached_result['message_ids_set']
                new_message_ids = self.detect_new_messages(current_message_ids, cached_message_ids)
                result['metadata']['new_messages_detected'] = len(new_message_ids)
                
                if not new_message_ids:
                    # ════════════════════════════════════════════════════════════════
                    # REQUIREMENT #5: No new emails - return cached summary
                    # ════════════════════════════════════════════════════════════════
                    logger.info("\n⚡ REQUIREMENT #5: No new emails detected!")
                    logger.info("   Returning cached summary without reprocessing...")
                    logger.info(f"{'='*80}")
                    logger.info(f"✅ SUMMARIZATION PIPELINE SUCCESS (CACHED)")
                    logger.info(f"{'='*80}\n")
                    
                    result['success'] = True
                    result['summary'] = cached_result['summary_text']
                    result['processing_mode'] = 'cached'
                    return result
                
                else:
                    # ════════════════════════════════════════════════════════════════
                    # REQUIREMENT #4: New emails detected - breakdown summary update
                    # ════════════════════════════════════════════════════════════════
                    logger.info(f"\n🔄 REQUIREMENT #4: {len(new_message_ids)} new email(s) detected!")
                    logger.info("   Using real-time breakdown_summary to update...")
                    
                    # Extract new emails as text
                    new_emails_text = self.get_new_emails_text(thread_data, new_message_ids)
                    
                    # Call breakdown_summary to update
                    logger.info("\n🤖 STEP 3B: Updating summary via breakdown_summary...")
                    start_time = datetime.utcnow()
                    updated_summary = asyncio.run(self.breakdown_summary_with_new_emails(
                        cached_result['summary_text'],
                        new_emails_text
                    ))
                    end_time = datetime.utcnow()
                    
                    api_call_time = (end_time - start_time).total_seconds()
                    result['metadata']['api_call_time'] = api_call_time
                    
                    if not updated_summary:
                        raise ValueError("breakdown_summary returned empty response")
                    
                    summary = updated_summary
                    result['processing_mode'] = 'breakdown'
                    
            else:
                # ══════════════════════════════════════════════════════════════════════
                # STEP 3B: No cached summary - create full summary (first-time)
                # ══════════════════════════════════════════════════════════════════════
                logger.info("📭 No cached summary found - creating full summary...")
                logger.info(f"\n📧 STEP 3B: Formatting email thread ({num_messages} emails)...")
                email_thread_text = self.format_email_thread_for_analysis(thread_data)
                
                if not email_thread_text:
                    raise ValueError("Failed to format email thread")
                
                # Create prompt based on email count (requirement #2)
                logger.info(f"\n📝 STEP 3C: Creating summarization prompt...")
                prompt = self.create_summarization_prompt(email_thread_text, num_messages)
                
                # Call LLM
                logger.info(f"\n🤖 STEP 3D: Calling LLM API...")
                start_time = datetime.utcnow()
                summary = asyncio.run(self.call_llm_api_async(prompt))
                end_time = datetime.utcnow()
                
                api_call_time = (end_time - start_time).total_seconds()
                result['metadata']['api_call_time'] = api_call_time
                
                if not summary:
                    raise ValueError("LLM API returned empty response")
                
                result['processing_mode'] = 'full'
            
            # ═══════════════════════════════════════════════════════════════════════════
            # STEP 4: Store/update summary in ChromaDB (requirement #3)
            # ═══════════════════════════════════════════════════════════════════════════
            logger.info(f"\n💾 STEP 4: Storing summary in ChromaDB...")
            self.store_summary_in_chromadb(
                user_id=user_id,
                thread_id=thread_id,
                summary_text=summary,
                message_ids=current_message_ids,
                all_message_ids_count=num_messages
            )
            
            # ═══════════════════════════════════════════════════════════════════════════
            # STEP 5: Return results
            # ═══════════════════════════════════════════════════════════════════════════
            logger.info(f"\n✅ STEP 5: Processing complete (took {api_call_time:.2f}s)")
            logger.info(f"   Processing Mode: {result['processing_mode']}")
            logger.info(f"{'='*80}")
            logger.info(f"✅ SUMMARIZATION PIPELINE SUCCESS")
            logger.info(f"{'='*80}\n")
            
            result['success'] = True
            result['summary'] = summary
            
            return result
            
        except Exception as e:
            logger.error(f"\n❌ SUMMARIZATION PIPELINE FAILED")
            logger.error(f"Error: {str(e)}")
            logger.error(f"{'='*80}\n")
            import traceback
            traceback.print_exc()
            
            result['success'] = False
            result['error'] = str(e)
            
            return result
    
    async def process_and_summarize_async(self, user_id: str, thread_id: str) -> Dict[str, Any]:
        """
        Async wrapper for pipeline (for FastAPI integration)
        
        Args:
            user_id: User identifier
            thread_id: Gmail thread ID
            
        Returns:
            Dict with summary and metadata
        """
        # Run sync method in thread pool
        import asyncio
        import concurrent.futures
        
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(
                pool,
                self.process_and_summarize,
                user_id,
                thread_id
            )
        return result
