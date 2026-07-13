"""
Email Label Pipeline
Uses rule-based system first, falls back to LLM for complex cases
Integrates with SQLite storage for label persistence
"""
import re
import os
import sys
import logging
import sqlite3
import json
from typing import Dict, Any, List, Literal, Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_groq import ChatGroq
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from datetime import datetime

# Import Ollama for native structured output
try:
    from ollama import chat as ollama_chat
except ImportError:
    ollama_chat = None

# Import settings manager
from agent.services.settings_manager import SettingsManager

# Import from the same services directory
# from .store_graph_pipeline import StoreGraphPipeline, ThreadGraphData  # Removed: label storage
from .ollama_lable_pipline import EmailLabelPipeline as OllamaEmailLabelPipeline

# Base data directory - point to backend/data (same as chat_pipeline.py)
BASE_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),  # openmailbot/
    "backend",
    "data"
)

logger = logging.getLogger(__name__)

# Define allowed labels using Literal
EmailLabel = Literal[
    "response",
    "FYI",
    "Notification",
    "meeting",
    "Escalation",
    "hotels",
    "airlines",
    "travel",
    "restaurant",
    "booking",
    "bank",
    "Insurance",
    "Recruitment",
    "Other"

]


class EmailLabelOutput(BaseModel):
    """Structured output for email classification with graph DB metadata"""
    label: EmailLabel = Field(description="The category label for the email")
    category: str = Field(description="Category or context of the email")
    topic: str = Field(description="Primary topic being discussed")
    subtopic: Optional[str] = Field(default=None, description="Subtopic if applicable")
    subject_matter: str = Field(description="One-line concise summary of the main subject/topic of the email")


def normalize_thread_id(thread_id: str) -> str:
    """Normalize thread_id to lowercase and strip whitespace for consistent storage"""
    return str(thread_id).lower().strip() if thread_id else thread_id
  


class EmailLabelPipeline:
    """
    Pipeline for labeling emails using rule-based system and LLM fallback
    Supports multiple LLM providers with structured output
    Stores labels in SQLite database for persistence
    """
    
    def __init__(self, user_id: Optional[str] = None, effective_settings: Optional[Dict] = None):
        """
        Initialize the label pipeline
        
        Args:
            user_id: User identifier for loading settings
            effective_settings: Optional pre-loaded settings dict

        """
        self.user_id = user_id
        
        # Load user settings
        if effective_settings:
            self.effective_settings = effective_settings
        elif user_id:
            settings_manager = SettingsManager(user_id)
            retrieved = settings_manager.get_settings(setting_type="general")
            self.effective_settings = retrieved if retrieved else {}
        else:
            self.effective_settings = {}
        
        # Extract LLM configuration from settings
        self.llm_provider = self.effective_settings.get("llm_provider", "manotr")
        self.llm_model = self.effective_settings.get("llm_model", "gpt-4o-mini")
        self.llm_api_key = self.effective_settings.get("llm_api_key", "")
        self.llm_base_url = self.effective_settings.get("llm_base_url", "http://localhost:11434")
        
        self.llm = None
        self.parser = None
        self.use_ollama_native = False
        
        # Initialize LLM based on provider
        if self.llm_provider != "manotr":
            try:
                self._init_llm()
                logger.info(f"✅ Label pipeline initialized with {self.llm_provider} / {self.llm_model}")
            except Exception as e:
                logger.warning(f"⚠️  Failed to initialize LLM: {str(e)}")
                self.llm = None
                self.parser = None
    
    def ensure_user_db(self, user_id: str):
        """Ensure per-user SQLite DB and label table exist with schema migration."""
        user_db = os.path.join(BASE_DATA_DIR, user_id, "sql_data", "chat_thread_processing.db")
        os.makedirs(os.path.dirname(user_db), exist_ok=True)
        conn = sqlite3.connect(user_db)
        cursor = conn.cursor()

        # Create labels table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_labels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                thread_id TEXT NOT NULL,
                label TEXT NOT NULL,
                last_process_message_id TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, thread_id)
            )
        ''')
        
        # Schema migration: Add last_process_message_id column if it doesn't exist
        cursor.execute("PRAGMA table_info(email_labels)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'last_process_message_id' not in columns:
            logger.info("🔧 Migrating schema: Adding last_process_message_id column...")
            cursor.execute('''
                ALTER TABLE email_labels
                ADD COLUMN last_process_message_id TEXT
            ''')
            logger.info("✅ Schema migration complete: last_process_message_id column added")

        conn.commit()
        conn.close()
        logger.info(f"✅ Initialized per-user label table at {user_db}")
    
    def store_label(self, user_id: str, thread_id: str, label_data: Dict[str, Any]) -> bool:
        """
        Store or update label in SQLite database with message_id tracking.
        
        If (user_id, thread_id) exists: UPDATE the label
        If (user_id, thread_id) doesn't exist: INSERT new record
        
        Args:
            user_id: User email ID
            thread_id: Gmail thread ID (will be normalized)
            label_data: Dict with keys: label, last_process_message_id
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Normalize thread_id
            thread_id = normalize_thread_id(thread_id)
            
            # Ensure per-user DB exists
            self.ensure_user_db(user_id)
            
            user_db = os.path.join(BASE_DATA_DIR, user_id, "sql_data", "chat_thread_processing.db")
            conn = sqlite3.connect(user_db)
            cursor = conn.cursor()
            
            # Extract label data with defaults
            label = label_data.get('label', 'Other')
            last_process_message_id = label_data.get('last_process_message_id', '')
            
            # Check if label already exists for this thread
            cursor.execute('''
                SELECT id FROM email_labels
                WHERE user_id = ? AND thread_id = ?
            ''', (user_id, thread_id))
            
            existing = cursor.fetchone()
            
            if existing:
                # UPDATE existing label
                cursor.execute('''
                    UPDATE email_labels
                    SET label = ?, last_process_message_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND thread_id = ?
                ''', (label, last_process_message_id, user_id, thread_id))
                
                logger.info(f"📝 Updated label for thread {thread_id} (user: {user_id})")
                logger.info(f"   Label: {label} | Last Message ID: {last_process_message_id}")
            else:
                # INSERT new label
                cursor.execute('''
                    INSERT INTO email_labels 
                    (user_id, thread_id, label, last_process_message_id)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, thread_id, label, last_process_message_id))
                
                logger.info(f"✅ Stored new label for thread {thread_id} (user: {user_id})")
                logger.info(f"   Label: {label} | Last Message ID: {last_process_message_id}")
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"❌ Error storing label: {e}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")
            return False
    
    def get_label(self, user_id: str, thread_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve label for a thread from SQLite database.
        
        Args:
            user_id: User email ID
            thread_id: Gmail thread ID (will be normalized)
            
        Returns:
            Dict with label data if found, None otherwise
        """
        try:
            # Normalize thread_id
            thread_id = normalize_thread_id(thread_id)
            
            # Ensure per-user DB exists
            self.ensure_user_db(user_id)
            
            user_db = os.path.join(BASE_DATA_DIR, user_id, "sql_data", "chat_thread_processing.db")
            conn = sqlite3.connect(user_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT label, last_process_message_id, created_at, updated_at
                FROM email_labels
                WHERE user_id = ? AND thread_id = ?
            ''', (user_id, thread_id))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                label_data = {
                    'label': row[0],
                    'last_process_message_id': row[1],
                    'created_at': row[2],
                    'updated_at': row[3]
                }
                logger.info(f"✅ Retrieved label for thread {thread_id}: {label_data['label']}")
                return label_data
            else:
                logger.info(f"ℹ️  No label found for thread {thread_id}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error retrieving label: {e}")
            return None
    
    def get_all_thread_labels(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all labels for a user.
        
        Args:
            user_id: User email ID
            
        Returns:
            List of label records
        """
        try:
            # Ensure per-user DB exists
            self.ensure_user_db(user_id)
            
            user_db = os.path.join(BASE_DATA_DIR, user_id, "sql_data", "chat_thread_processing.db")
            conn = sqlite3.connect(user_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT thread_id, label, last_process_message_id, created_at, updated_at
                FROM email_labels
                WHERE user_id = ?
                ORDER BY updated_at DESC
            ''', (user_id,))
            
            rows = cursor.fetchall()
            conn.close()
            
            labels = [
                {
                    'thread_id': row[0],
                    'label': row[1],
                    'last_process_message_id': row[2],
                    'created_at': row[3],
                    'updated_at': row[4]
                }
                for row in rows
            ]
            
            logger.info(f"✅ Retrieved {len(labels)} labels for user {user_id}")
            return labels
            
        except Exception as e:
            logger.error(f"❌ Error retrieving labels: {e}")
            return []
    
    def delete_label(self, user_id: str, thread_id: str) -> bool:
        """
        Delete label for a thread.
        
        Args:
            user_id: User email ID
            thread_id: Gmail thread ID (will be normalized)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Normalize thread_id
            thread_id = normalize_thread_id(thread_id)
            
            # Ensure per-user DB exists
            self.ensure_user_db(user_id)
            
            user_db = os.path.join(BASE_DATA_DIR, user_id, "sql_data", "chat_thread_processing.db")
            conn = sqlite3.connect(user_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM email_labels
                WHERE user_id = ? AND thread_id = ?
            ''', (user_id, thread_id))
            
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            
            if deleted > 0:
                logger.info(f"✅ Deleted label for thread {thread_id}")
                return True
            else:
                logger.info(f"ℹ️  No label found to delete for thread {thread_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error deleting label: {e}")
            return False
    
    def get_cached_label_if_exists(self, user_id: str, thread_id: str, 
                                   last_message_id: str) -> Optional[Dict[str, Any]]:
        """
        Cache lookup: Check if label exists for thread with matching last_process_message_id
        
        This optimizes the pipeline by returning cached labels if:
        1. Thread exists in database
        2. Last processed message ID matches the one being processed
        
        If the message_id doesn't match (new message in thread), returns None and 
        triggers full re-processing through the pipeline.
        
        Args:
            user_id: User email ID
            thread_id: Gmail thread ID (will be normalized)
            last_message_id: Last message ID being processed
            
        Returns:
            Dict with cached label if found and message_id matches, None otherwise
        """
        try:
            # Normalize thread_id
            thread_id = normalize_thread_id(thread_id)
            
            # Ensure per-user DB exists
            self.ensure_user_db(user_id)
            
            user_db = os.path.join(BASE_DATA_DIR, user_id, "sql_data", "chat_thread_processing.db")
            conn = sqlite3.connect(user_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT label, last_process_message_id, created_at, updated_at
                FROM email_labels
                WHERE user_id = ? AND thread_id = ?
            ''', (user_id, thread_id))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                stored_label = row[0]
                stored_message_id = row[1]
                created_at = row[2]
                updated_at = row[3]
                
                # Check if the last_process_message_id matches
                if stored_message_id == last_message_id:
                    logger.info(f"✅ CACHE HIT: Found cached label for thread {thread_id}")
                    logger.info(f"   Message ID matched: {last_message_id}")
                    logger.info(f"   Returning cached label: {stored_label}")
                    
                    return {
                        'label': stored_label,
                        'last_process_message_id': stored_message_id,
                        'created_at': created_at,
                        'updated_at': updated_at,
                        'cached': True
                    }
                else:
                    logger.info(f"⚠️  CACHE MISS: Message ID mismatch for thread {thread_id}")
                    logger.info(f"   Stored message ID: {stored_message_id}")
                    logger.info(f"   Current message ID: {last_message_id}")
                    logger.info(f"   Requires full re-processing")
                    return None
            else:
                logger.info(f"ℹ️  No cached label found for thread {thread_id}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error checking cache: {e}")
            return None
    
    def _get_fallback_label(self, email_data: Dict[str, Any]) -> EmailLabelOutput:
        """
        Fallback label when both rule-based and LLM classification fail.
        Returns a sensible default with "Other" label.
        """
        subject = email_data.get('subject', 'Unclassified Email')
        return EmailLabelOutput(
            label="Other",
            category="Unclassified",
            topic="Review Needed",
            subtopic=None,
            subject_matter=f"Please review: {subject[:40]}"
        )
    
    def _init_llm(self):
        """Initialize LLM client based on provider settings"""
        
        if self.llm_provider == "ollama":
            # Use Ollama native structured output if available
            if ollama_chat is not None:
                self.use_ollama_native = True
                logger.info(f"Using Ollama native structured output at {self.llm_base_url}")
            else:
                logger.warning("Ollama library not installed. Install with: pip install ollama")
                self.llm = None
                
        elif self.llm_provider == "openai":
            if not self.llm_api_key:
                raise ValueError("OpenAI API key required")
            
            # Sanitize API key
            api_key = str(self.llm_api_key).strip()
            
            self.llm = ChatOpenAI(
                model=self.llm_model or "gpt-4o-mini",
                temperature=0,
                api_key=api_key
            )
            self.parser = PydanticOutputParser(pydantic_object=EmailLabelOutput)
            
        elif self.llm_provider == "anthropic":
            if not self.llm_api_key:
                raise ValueError("Anthropic API key required")
            
            api_key = str(self.llm_api_key).strip()
            
            self.llm = ChatAnthropic(
                model=self.llm_model or "claude-3-5-sonnet-20241022",
                temperature=0,
                api_key=api_key
            )
            self.parser = PydanticOutputParser(pydantic_object=EmailLabelOutput)
            
        elif self.llm_provider == "groq":
            if not self.llm_api_key:
                raise ValueError("Groq API key required")
            
            api_key = str(self.llm_api_key).strip()
            
            self.llm = ChatGroq(
                model=self.llm_model or "llama-3.3-70b-versatile",
                temperature=0,
                api_key=api_key
            )
            self.parser = PydanticOutputParser(pydantic_object=EmailLabelOutput)
        
        else:
            logger.warning(f"Unsupported LLM provider: {self.llm_provider}")
            self.llm = None
        
        # Create prompt template
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """
You are a precise email classification and analysis assistant.

Your task is to analyze an email and extract:
1. LABEL - EXACTLY ONE labels from the allowed labels
2. CATEGORY - Select ONE from: Issue, Update, Discussion, Request, Question, Confirmation, Complaint, Approval. If it doesn't fit any of these, choose "General"
3. TOPIC - Primary topic being discussed
4. SUBTOPIC - Subtopic if applicable (optional)
5. SUBJECT_MATTER - A simple, concise one-line summary (10-15 words max) describing the main subject of the email

Choose the label that BEST represents the MAIN intent of the email with respect to the user.
Consider the user's context and priorities when selecting the label.
If multiple labels seem possible, select the most dominant purpose.

----------------------
EMAIL LABEL DEFINITIONS
----------------------

Response
- Direct answers to questions asked in previous emails
- Confirmations of requests or actions
- Provides information that was specifically requested
- Examples: "Yes, I can attend the meeting", "Here's the report you asked for", "The answer to your question is..."

FYI (For Your Information)
- Informational updates with no action or reply needed
- Announcements, notifications, or status updates
- Sharing knowledge, articles, or resources
- Examples: "Just keeping you in the loop", "FYI - the office will be closed", "Sharing this article for your awareness"

Escalation
- Raises unresolved issues to management or higher authority
- Expresses urgency, complaints, or critical problems
- Indicates failures, delays, or blocked progress requiring intervention
- Contains phrases like "need immediate attention", "this is urgent", "not resolved yet"
- Examples: "This has been pending for 3 weeks", "Escalating to your manager", "Critical issue needs executive approval"


Notification — Automated/system-generated update or alert  
meeting — Scheduling or discussing a meeting  
hotels — Hotel-related communication  
airlines — Flight-related communication  
travel — General travel discussion  
restaurant — Restaurant reservations or inquiries  
booking — Non-travel reservations or appointments  
bank — Banking or financial matters  
recruitment — Hiring, interviews, or job applications
Other - other types of emails that don't fit the above categories

{format_instructions}"""),
            ("user", """Classify and analyze this email for User: {user_id}

From: {from_address}
To: {to_addresses}
Subject: {subject}
Body: {body}

Provide the label, category, topic, and subtopic for this email based on the user's context and priorities.""")
        ])
    


    def apply_rules(self, email_data: Dict[str, Any]) -> Optional[str]:

        subject = email_data.get("subject", "").lower()
        body = email_data.get("body", "").lower()
        from_address = email_data.get("from", "").lower()

        text = f"{subject} {body}"

        # -------------------------
        # HELPERS
        # -------------------------

        def contains(words, source=text):
            return any(w in source for w in words)

        def regex(pattern):
            return re.search(pattern, text) is not None

        def domain_contains(words):
            return any(w in from_address for w in words)

   

        # -------------------------
        # 2. BANK
        # -------------------------
        if domain_contains([
            "hdfc", "icici", "sbi", "axis", "kotak",
            "yesbank", "bankof", "amex", "paypal"
        ]) or contains([
            "account statement", "transaction alert",
            "credited", "debited", "net banking",
            "upi", "ifsc", "balance"
        ]):
            return "bank"
        
        

        # -------------------------
        # 3. AIRLINES
        # -------------------------
        if domain_contains([
            "airindia", "indigo", "spicejet",
            "vistara", "emirates", "qatarairways",
            "lufthansa"
        ]) or contains([
            "flight", "pnr", "boarding pass",
            "gate number", "departure",
            "arrival", "web check-in"
        ]):
            return "airlines"

        # -------------------------
        # 4. HOTELS
        # -------------------------
        if domain_contains([
            "booking.com", "agoda", "oyo",
            "airbnb", "trivago", "marriott",
            "hyatt"
        ]) or contains([
            "hotel booking", "check-in",
            "check-out", "room reserved",
            "stay details"
        ]):
            return "hotels"

        # -------------------------
        # 5. RESTAURANT
        # -------------------------
        if contains([
            "restaurant reservation",
            "table booked",
            "zomato", "swiggy",
            "dining", "food order"
        ]):
            return "restaurant"

        # -------------------------
        # 6. RECRUITMENT
        # -------------------------
        if domain_contains([
            "linkedin", "naukri", "indeed",
            "wellfound", "monster", "glassdoor"
        ]) or contains([
            "interview", "resume", "cv",
            "job opening", "we are hiring",
            "application shortlisted",
            "talent acquisition"
        ]):
            return "Recruitment"

        # -------------------------
        # 7. BOOKING
        # -------------------------
        if contains([
            "booking confirmed",
            "reservation confirmed",
            "confirmation number",
            "ticket booked",
            "your itinerary"
        ]):
            return "booking"

        # -------------------------
        # 8. MEETING
        # -------------------------
        if contains([
            "meeting", "calendar invite",
            "schedule a call",
            "zoom link", "google meet",
            "teams meeting"
        ]):
            return "meeting"


        # -------------------------
        # TRAVEL (GENERIC + TRAIN)
        # -------------------------
        if domain_contains([
            "irctc", "makemytrip", "redbus",
            "goibibo", "yatra"
        ]) or contains([
            "travel itinerary",
            "trip details",
            "visa", "passport",
            "journey plan",
            # Train specific
            "pnr status",
            "train ticket",
            "coach number",
            "seat number",
            "train booking",
            "railway reservation",
            "e-ticket",
            "boarding station"
        ]):
            return "travel"
        
       
        # -------------------------
        # 14. NOTIFICATION (LOW PRIORITY)
        # -------------------------
        if domain_contains([
            "no-reply", "noreply","info",
            "notification", "alerts"
        ]) or contains([
            "this is an automated message",
            "system generated",
            "do not reply"
        ]):
            return "Notification"

        

        

        

        return None

    
    def classify_with_llm(self, email_data: Dict[str, Any]) -> EmailLabelOutput:
        """
        Classify email using LLM with structured output
        Supports both Ollama native format and PydanticOutputParser for other providers
        
        Args:
            email_data: Dictionary with email fields
            
        Returns:
            EmailLabelOutput with label, category, topic, subtopic
        """
        # Check if LLM is available
        if not self.use_ollama_native and (not self.llm or not self.parser):
            logger.warning("⚠️  LLM not available, cannot classify with LLM")
            logger.warning("ℹ️  Falling back to 'Other' label for unclassified email")
            return self._get_fallback_label(email_data)
        
        try:
            # Prepare email data
            user_id = email_data.get('user_id', 'Unknown')
            from_address = email_data.get('from', 'Unknown')
            to_addresses = ', '.join(email_data.get('to', []))
            subject = email_data.get('subject', '')
            body = email_data.get('body', '')
            
            # Truncate body if too long (to save tokens)
            if len(body) > 1000:
                body = body[:1000] + "..."
            
            # Handle Ollama native structured output
            if self.use_ollama_native:
                logger.info(f"Using Ollama native structured output with {self.llm_model}")
                
                # Build system prompt without format_instructions
                system_content = """
You are a precise email classification and analysis assistant.

Your task is to analyze an email and extract:
1. LABEL - EXACTLY ONE labels from the allowed labels
2. CATEGORY - Select ONE from: Issue, Update, Discussion, Request, Question, Confirmation, Complaint, Approval. If it doesn't fit any of these, choose "General"
3. TOPIC - Primary topic being discussed
4. SUBTOPIC - Subtopic if applicable (optional)
5. SUBJECT_MATTER - A simple, concise one-line summary (10-15 words max) describing the main subject of the email

Choose the label that BEST represents the MAIN intent of the email with respect to the user.
Consider the user's context and priorities when selecting the label.
If multiple labels seem possible, select the most dominant purpose.

----------------------
EMAIL LABEL DEFINITIONS
----------------------

Response
- Direct answers to questions asked in previous emails
- Confirmations of requests or actions
- Provides information that was specifically requested
- Examples: "Yes, I can attend the meeting", "Here's the report you asked for", "The answer to your question is..."

FYI (For Your Information)
- Informational updates with no action or reply needed
- Announcements, notifications, or status updates
- Sharing knowledge, articles, or resources
- Examples: "Just keeping you in the loop", "FYI - the office will be closed", "Sharing this article for your awareness"

Escalation
- Raises unresolved issues to management or higher authority
- Expresses urgency, complaints, or critical problems
- Indicates failures, delays, or blocked progress requiring intervention
- Contains phrases like "need immediate attention", "this is urgent", "not resolved yet"
- Examples: "This has been pending for 3 weeks", "Escalating to your manager", "Critical issue needs executive approval"

Notification — Automated/system-generated update or alert  
meeting — Scheduling or discussing a meeting  
hotels — Hotel-related communication  
airlines — Flight-related communication  
travel — General travel discussion  
restaurant — Restaurant reservations or inquiries  
booking — Non-travel reservations or appointments  
bank — Banking or financial matters  
recruitment — Hiring, interviews, or job applications
Other - other types of emails that don't fit the above categories
"""
                
                user_content = f"""Classify and analyze this email for User: {user_id}

From: {from_address}
To: {to_addresses}
Subject: {subject}
Body: {body}

Provide the label, category, topic, and subtopic for this email based on the user's context and priorities."""
                
                # Call Ollama with structured output
                response = ollama_chat(
                    model=self.llm_model,
                    messages=[
                        {'role': 'system', 'content': system_content},
                        {'role': 'user', 'content': user_content}
                    ],
                    format=EmailLabelOutput.model_json_schema(),
                    options={
                        'temperature': 0,
                    }
                )
                
                # Parse the response using Pydantic
                result = EmailLabelOutput.model_validate_json(response.message.content)
                logger.info(f"✅ Ollama classification: {result.label}")
                return result
            
            else:
                # Use PydanticOutputParser for OpenAI, Anthropic, Groq
                logger.info(f"Using PydanticOutputParser with {self.llm_provider}")
                
                # Create formatted prompt with format_instructions
                formatted_prompt = self.prompt.format_messages(
                    format_instructions=self.parser.get_format_instructions(),
                    user_id=user_id,
                    from_address=from_address,
                    to_addresses=to_addresses,
                    subject=subject,
                    body=body
                )
                
                # Get LLM response
                response = self.llm.invoke(formatted_prompt)
                
                # Parse structured output
                result = self.parser.parse(response.content)
                logger.info(f"✅ {self.llm_provider} classification: {result.label}")
                return result
            
        except Exception as e:
            logger.error(f"Error in LLM classification: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            # Fallback to "Other" label when LLM fails
            logger.warning(f"ℹ️  LLM classification failed, using 'Other' label as fallback")
            return self._get_fallback_label(email_data)
    
    def label_email(self, email_data: Dict[str, Any]) -> EmailLabelOutput:
        """
        Main entry point for email labeling with enriched metadata
        
        Args:
            email_data: Dictionary with 'subject', 'body', 'from', 'to' fields
            
        Returns:
            EmailLabelOutput with label, category, topic, subtopic
        """
        # Try rule-based classification first
        label = self.apply_rules(email_data)
        
        if label:
            print(f"✓ Rule-based label: {label}")
            # If rule-based found a label, use LLM to enrich with category/topic/subtopic
            if self.llm and self.parser:
                enriched = self.classify_with_llm(email_data)
                # Override the label with rule-based result
                enriched.label = label
                return enriched
            else:
                # Fallback without enrichment
                subject_matter = email_data.get('subject', 'General email communication')[:50]
                return EmailLabelOutput(
                    label=label,
                    category=email_data.get('subject', '').split()[:3] if email_data.get('subject') else 'General',
                    topic=label.capitalize(),
                    subtopic=None,
                    subject_matter=subject_matter
                )
        
        # Fallback to LLM classification for enriched output
        print(f"→ Using LLM classification")
        result = self.classify_with_llm(email_data)
        print(f"✓ LLM label: {result.label}, category: {result.category}, topic: {result.topic}")
        
        return result
    
    def label_thread(self, messages: List[Dict[str, Any]]) -> EmailLabelOutput:
        """
        Label a thread of emails with enriched metadata - focuses on the last message
        
        Args:
            messages: List of email message dictionaries (chronologically ordered)
            
        Returns:
            EmailLabelOutput with label, category, topic, subtopic for the thread
        """
        if not messages:
            return self._get_fallback_label({'subject': 'Empty thread'})
        
        # Get the last message (most recent) as it's most important
        last_message = messages[-1]
        
        # Create email data for labeling
        email_data = {
            'from': last_message.get('from', ''),
            'to': last_message.get('to', []),
            'subject': last_message.get('subject', ''),
            'body': last_message.get('body', '')
        }
        
        return self.label_email(email_data)
    
    def label_and_store_thread(self, thread_id: str, messages: List[Dict[str, Any]], user_id: str = None) -> Dict[str, Any]:
        """
        Label a thread with cache optimization and store it in SQLite database.
        
        FLOW:
        1. Normalize thread_id
        2. Extract user_id and last_message_id from messages
        3. Check cache: if thread exists with matching last_message_id, return cached label immediately
        4. If not cached: Process through full pipeline (rule-based + LLM)
        5. Store label with last_process_message_id for future cache lookups
        
        Args:
            thread_id: Unique identifier for the thread (will be normalized)
            messages: List of email message dictionaries (chronologically ordered)
            user_id: User ID for context and database storage (extracted from messages if not provided)
            
        Returns:
            Dictionary with label and processing info, or cached label if found
        """
        # Step 0: Normalize thread_id
        thread_id = normalize_thread_id(thread_id)
        
        print(f"\n📧 LABEL AND STORE THREAD: {thread_id}")
        print("="*70)
        
        # Step 1: Extract thread metadata and message_id
        print("Step 1: Extracting thread metadata...")
        last_message = messages[-1]
        subject = last_message.get('subject', 'No subject')
        participants = last_message.get('to', [])
        last_message_id = last_message.get('message_id', None)
        timestamp = last_message.get('timestamp', None)
        
        # Extract user_id if not provided
        if user_id is None:
            user_id = last_message.get('user_id', 'unknown_user')
        
        if isinstance(participants, str):
            participants = [participants]
        
        # Ensure unique participants
        participants = list(set(participants))
        
        print(f"  Subject: {subject}")
        print(f"  Participants: {len(participants)}")
        print(f"  User ID: {user_id}")
        print(f"  Last Message ID: {last_message_id}")
        print(f"  Timestamp: {timestamp}")
        
        # Step 2: CHECK CACHE - Return cached label if exists with matching message_id
        print("\nStep 2: Checking cache for existing label...")
        if last_message_id:
            cached_label = self.get_cached_label_if_exists(user_id, thread_id, last_message_id)
            if cached_label:
                print("✅ CACHE HIT - Returning stored label immediately!")
                combined_result = {
                    "thread_id": thread_id,
                    "user_id": user_id,
                    "label": cached_label['label'],
                    "last_process_message_id": cached_label['last_process_message_id'],
                    "created_at": cached_label['created_at'],
                    "updated_at": cached_label['updated_at'],
                    "source": "cache",
                    "status": "SUCCESS_CACHED"
                }
                print("\n" + "="*70)
                print("✅ Returned cached label!")
                print("="*70)
                return combined_result
        
        # Step 3: CACHE MISS - Process through full pipeline
        print("\nStep 3: CACHE MISS - Processing through label pipeline...")
        ollama_pipeline = OllamaEmailLabelPipeline()
        label_result = ollama_pipeline.label_thread(messages)
        print(f"✓ Label: {label_result.label}")
        
        # Step 4: Store label in SQLite database with last_message_id
        print("\nStep 4: Storing label in SQLite database with message tracking...")
        
        label_data = {
            'label': label_result.label,
            'last_process_message_id': last_message_id
        }
        
        storage_result = self.store_label(user_id, thread_id, label_data)
        
        if storage_result:
            print(f"✅ Label stored successfully in SQLite!")
            storage_status = "SUCCESS"
        else:
            print(f"❌ Failed to store label in SQLite!")
            storage_status = "FAILED"
        
        # Combine results - wrap in label_result for backend compatibility
        combined_result = {
            "label_result": {
                "thread_id": thread_id,
                "user_id": user_id,
                "label": label_result.label,
                "last_process_message_id": last_message_id,
                "storage_result": {
                    "status": storage_status,
                    "database_path": os.path.join(BASE_DATA_DIR, user_id, "sql_data", "chat_thread_processing.db")
                },
                "source": "pipeline",
                "status": "SUCCESS" if storage_status == "SUCCESS" else "PARTIAL_SUCCESS"
            }
        }
        
        print("\n" + "="*70)
        print("✅ Thread labeling and storage complete!")
        print("="*70)
        
        return combined_result
