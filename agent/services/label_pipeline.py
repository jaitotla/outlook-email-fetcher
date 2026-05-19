"""
Email Label Pipeline
Uses rule-based system first, falls back to LLM for complex cases
Integrates with graph database storage pipeline for category/topic organization
"""
import re
import os
import sys
import logging
from typing import Dict, Any, List, Literal, Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_groq import ChatGroq
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate

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
  


class EmailLabelPipeline:
    """
    Pipeline for labeling emails using rule-based system and LLM fallback
    Supports multiple LLM providers with structured output
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
            return "recruitment"

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
        Label a thread and store it in the Neo4j graph database with category/topic hierarchy
        
        This combines the labeling pipeline with graph database storage for email organization.
        
        Args:
            thread_id: Unique identifier for the thread
            messages: List of email message dictionaries (chronologically ordered)
            user_id: User ID for context and graph storage (extracted from messages if not provided)
            
        Returns:
            Dictionary with label_result and graph_store_result
        """
        print(f"\n📧 LABEL AND STORE THREAD: {thread_id}")
        print("="*70)
        
        # Step 1: Label the thread using Ollama
        print("Step 1: Labeling thread with Ollama...")
        ollama_pipeline = OllamaEmailLabelPipeline()
        label_result = ollama_pipeline.label_thread(messages)
        print(f"✓ Label: {label_result.label}")
        print(f"  Category: {label_result.category}")
        print(f"  Topic: {label_result.topic}")
        if label_result.subtopic:
            print(f"  Subtopic: {label_result.subtopic}")
        print(f"  Subject Matter: {label_result.subject_matter}")
        
        # Step 2: Extract thread metadata
        print("\nStep 2: Extracting thread metadata...")
        last_message = messages[-1]
        subject = last_message.get('subject', 'No subject')
        participants = last_message.get('to', [])
        message_id = last_message.get('message_id', None)
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
        print(f"  Message ID: {message_id}")
        print(f"  Timestamp: {timestamp}")
        
        # Step 3: Store in graph database (COMMENTED OUT)
        # print("\nStep 3: Storing in graph database...")
        # 
        # # Create ThreadGraphData from label result
        # graph_data = ThreadGraphData(
        #     thread_id=thread_id,
        #     subject=subject,
        #     participants=participants,
        #     category=label_result.category,
        #     topic=label_result.topic,
        #     user_id=user_id,
        #     subtopic=label_result.subtopic,
        #     subject_matter=label_result.subject_matter,
        #     message_id=message_id,
        #     timestamp=timestamp
        # )
        # 
        # # Create and run graph pipeline only for specific labels
        # if label_result.label in ["response", "FYI", "Awaiting Reply"]:
        #     graph_pipeline = StoreGraphPipeline()
        #     graph_store_result = graph_pipeline.store_thread_graph(graph_data)
        # else:
        #     graph_store_result = {"status": "SKIPPED", "reason": "Label not eligible for graph storage"}
        
        # Combine results
        combined_result = {
            "thread_id": thread_id,
            "user_id": user_id,
            "label_result": {
                "label": label_result.label,
                "category": label_result.category,
                "topic": label_result.topic,
                "subtopic": label_result.subtopic,
                "subject_matter": label_result.subject_matter
            },
            "status": "SUCCESS"
        }
        
        print("\n" + "="*70)
        print("✅ Thread labeling and storage complete!")
        print("="*70)
        
        return combined_result
