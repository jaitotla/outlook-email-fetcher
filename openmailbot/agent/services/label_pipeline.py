"""
Email Label Pipeline
Uses rule-based system first, falls back to LLM for complex cases
Integrates with graph database storage pipeline for category/topic organization
"""
import re
import os
import sys
from typing import Dict, Any, List, Literal, Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate

# Import from the same services directory
from .store_graph_pipeline import StoreGraphPipeline, ThreadGraphData


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
    "Other",
    "Awaiting Reply"

]


class EmailLabelOutput(BaseModel):
    """Structured output for email classification with graph DB metadata"""
    label: EmailLabel = Field(description="The category label for the email")
    category: str = Field(description="Category or context of the email")
    topic: str = Field(description="Primary topic being discussed")
    subtopic: Optional[str] = Field(default=None, description="Subtopic if applicable")
  


class EmailLabelPipeline:
    """
    Pipeline for labeling emails using rule-based system and LLM fallback
    """
    
    def __init__(self, openai_api_key: str = None):
        """
        Initialize the label pipeline
        
        Args:
            openai_api_key: OpenAI API key (if None, uses rule-based only)

        """
        import json
        
        # Try to get API key from parameter, environment, or config file
        if openai_api_key is None:
            openai_api_key = os.getenv("OPENAI_API_KEY")
            
        if openai_api_key is None:
            try:
                with open("/home/ubuntu/openmailbot/openmailbot/agent/config.json", "r") as f:
                    config = json.load(f)
                openai_api_key = config.get("OPENAI_KEY")
            except (FileNotFoundError, json.JSONDecodeError):
                openai_api_key = None
        
        self.openai_api_key = openai_api_key
        self.llm = None
        self.parser = None
        
        # Only initialize LLM if API key is available
        if self.openai_api_key:
            try:
                # Initialize LLM with structured output
                self.llm = ChatOpenAI(
                    model="gpt-4o-mini",
                    temperature=0,
                    api_key=self.openai_api_key
                )
                
                # Setup output parser
                self.parser = PydanticOutputParser(pydantic_object=EmailLabelOutput)
            except Exception as e:
                print(f"⚠️  Warning: Failed to initialize LLM: {str(e)}")
                self.llm = None
                self.parser = None
        
        # Create prompt template
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """
You are a precise email classification and analysis assistant.

Your task is to analyze an email and extract:
1. LABEL - EXACTLY ONE labels from the allowed labels
2. CATEGORY - Select ONE from: Issue, Update, Discussion, Request, Question, Confirmation, Complaint, Approval. If it doesn't fit any of these, choose "General"
3. TOPIC - Primary topic being discussed
4. SUBTOPIC - Subtopic if applicable (optional)

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

Awaiting Reply
- Questions posed that require a response from the recipient
- Requests for information, decisions, or approvals
- Seeks confirmation, feedback, or input
- Contains action items or asks the recipient to do something
- Examples: "Can you please confirm?", "What are your thoughts on this?", "Please let me know by Friday", "Could you provide the updated numbers?"

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
        
        Args:
            email_data: Dictionary with email fields
            
        Returns:
            EmailLabelOutput with label, category, topic, subtopic
        """
        # Check if LLM is available
        if not self.llm or not self.parser:
            print("⚠️  LLM not available, cannot classify with LLM")
            return EmailLabelOutput(
                label="response",
                category="General",
                topic="General Communication",
                subtopic=None
            )
        
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
            
            # Create formatted prompt
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
            
            return result
            
        except Exception as e:
            print(f"Error in LLM classification: {str(e)}")
            # Fallback to general label
            return EmailLabelOutput(
                label="response",
                category="General",
                topic="General Communication",
                subtopic=None
            )
    
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
                return EmailLabelOutput(
                    label=label,
                    category=email_data.get('subject', '').split()[:3] if email_data.get('subject') else 'General',
                    topic=label.capitalize(),
                    subtopic=None
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
            return EmailLabelOutput(
                label="response",
                category="Empty",
                topic="No messages",
                subtopic=None
            )
        
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
    
    def label_and_store_thread(self, thread_id: str, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Label a thread and store it in the Neo4j graph database with category/topic hierarchy
        
        This combines the labeling pipeline with graph database storage for email organization.
        
        Args:
            thread_id: Unique identifier for the thread
            messages: List of email message dictionaries (chronologically ordered)
            
        Returns:
            Dictionary with label_result and graph_store_result
        """
        print(f"\n📧 LABEL AND STORE THREAD: {thread_id}")
        print("="*70)
        
        # Step 1: Label the thread
        print("Step 1: Labeling thread...")
        label_result = self.label_thread(messages)
        print(f"✓ Label: {label_result.label}")
        print(f"  Category: {label_result.category}")
        print(f"  Topic: {label_result.topic}")
        if label_result.subtopic:
            print(f"  Subtopic: {label_result.subtopic}")
        
        # Step 2: Extract thread metadata
        print("\nStep 2: Extracting thread metadata...")
        last_message = messages[-1]
        subject = last_message.get('subject', 'No subject')
        participants = last_message.get('to', [])
        if isinstance(participants, str):
            participants = [participants]
        
        # Ensure unique participants
        participants = list(set(participants))
        
        print(f"  Subject: {subject}")
        print(f"  Participants: {len(participants)}")
        
        # Step 3: Store in graph database
        print("\nStep 3: Storing in graph database...")
        
        # Create ThreadGraphData from label result
        graph_data = ThreadGraphData(
            thread_id=thread_id,
            subject=subject,
            participants=participants,
            category=label_result.category,
            topic=label_result.topic,
            subtopic=label_result.subtopic
        )
        
        # Create and run graph pipeline
        graph_pipeline = StoreGraphPipeline()
        graph_store_result = graph_pipeline.store_thread_graph(graph_data)
        
        # Combine results
        combined_result = {
            "thread_id": thread_id,
            "label_result": {
                "label": label_result.label,
                "category": label_result.category,
                "topic": label_result.topic,
                "subtopic": label_result.subtopic
            },
            "graph_store_result": graph_store_result,
            "status": "SUCCESS" if graph_store_result.get("status") == "SUCCESS" else "COMPLETED_WITH_ERRORS"
        }
        
        print("\n" + "="*70)
        print("✅ Thread labeling and storage complete!")
        print("="*70)
        
        return combined_result
