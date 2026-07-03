"""
Email Label Pipeline (Ollama Version)
Uses rule-based system first, falls back to Ollama LLM for complex cases
Integrates with graph database storage pipeline for category/topic organization
"""
import re
import os
import sys
import json
import requests
from typing import Dict, Any, List, Literal, Optional
from pydantic import BaseModel, Field

# Import from the same services directory (if needed)
# from .store_graph_pipeline import StoreGraphPipeline, ThreadGraphData


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
    Pipeline for labeling emails using rule-based system and Ollama LLM fallback
    """
    
    def __init__(self, ollama_url: str = None, model: str = "llama3.2"):
        """
        Initialize the label pipeline with Ollama
        
        Args:
            ollama_url: Ollama API endpoint URL (default: https://lsdiedb39c.pagekite.me/chat_structure)
            model: Ollama model to use (default: llama3.2)
        """
        # Set default Ollama URL if not provided
        self.ollama_url = ollama_url or "https://lsdiedb39c.pagekite.me/chat_structure"
        self.model = model
        
        # Test Ollama connection
        try:
            self._test_ollama_connection()
            self.ollama_available = True
            print(f"✓ Ollama connection successful at {self.ollama_url}")
        except Exception as e:
            print(f"⚠️  Warning: Ollama not available: {str(e)}")
            self.ollama_available = False
    
    def _test_ollama_connection(self):
        """Test if Ollama endpoint is reachable"""
        test_payload = {
            "query": "Test",
            "schema": {"type": "object", "properties": {"test": {"type": "string"}}}
        }
        response = requests.post(self.ollama_url, json=test_payload, timeout=5)
        response.raise_for_status()
    
    def _create_system_prompt(self) -> str:
        """Create the system prompt for email classification"""
        return """You are a precise email classification and analysis assistant.

Your task is to analyze an email and extract:
1. LABEL - EXACTLY ONE labels from the allowed labels
2. CATEGORY - Select ONE CATEGORY:Finance ,Operations,Sales,Support,Logistics,HR,Legal,Technical,Technical problem,business comunication,General 
3. TOPIC - Primary topic being discussed
4. SUBTOPIC - Subtopic if applicable (optional)
5. SUBJECT_MATTER - A simple, concise one-line summary (8-10 words max) describing the main subject of the email

IMPORTANT:
- Labels must be created ONLY from the perspective of this user (user_id)
- Determine whether THIS USER needs to take action
- Ignore actions/questions directed to other people
- If someone else is asked for information and the user is only copied, treat it as FYI
- If the user is not expected to reply or act, mark accordingly
- Focus on what this email means FOR THE USER ONLY

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
- THIS USER is CC'd or BCC'd on emails between other people
- Someone else is being asked to respond, not THIS USER
- Announcements, notifications, or status updates
- Sharing knowledge, articles, or resources
- Examples: "Just keeping you in the loop", "FYI - the office will be closed", "Sharing this article for your awareness", "You're CC'd on this conversation between others"

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
Other - other types of emails that don't fit the above categories"""

    def apply_rules(self, email_data: Dict[str, Any]) -> Optional[str]:
        """Rule-based email classification"""
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
        # 1. BANK
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
        # 2. AIRLINES
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
        # 3. HOTELS
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
        # 4. RESTAURANT
        # -------------------------
        if contains([
            "restaurant reservation",
            "table booked",
            "zomato", "swiggy",
            "dining", "food order"
        ]):
            return "restaurant"

        # -------------------------
        # 5. RECRUITMENT
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
        # 6. BOOKING
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
        # 7. MEETING
        # -------------------------
        if contains([
            "meeting", "calendar invite",
            "schedule a call",
            "zoom link", "google meet",
            "teams meeting"
        ]):
            return "meeting"

        # -------------------------
        # 8. TRAVEL (GENERIC + TRAIN)
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
        # 10. NOTIFICATION (LOW PRIORITY)
        # -------------------------
        if domain_contains([
            "no-reply", "noreply", "info",
            "notification", "alerts"
        ]) or contains([
            "this is an automated message",
            "system generated",
            "do not reply"
        ]):
            return "Notification"

        return None
    
    def classify_with_ollama(self, email_data: Dict[str, Any]) -> EmailLabelOutput:
        """
        Classify email using Ollama with structured output
        
        Args:
            email_data: Dictionary with email fields
            
        Returns:
            EmailLabelOutput with label, category, topic, subtopic
        """
        # Check if Ollama is available
        if not self.ollama_available:
            print("⚠️  Ollama not available, cannot classify with LLM")
            print("ℹ️  Falling back to 'Other' label for unclassified email")
            return self._fallback_output(email_data)
        
        try:
            # Prepare email data
            user_id = email_data.get('user_id', 'Unknown')
            from_address = email_data.get('from', 'Unknown')
            to_addresses = ', '.join(email_data.get('to', [])) if isinstance(email_data.get('to'), list) else email_data.get('to', '')
            subject = email_data.get('subject', '')
            body = email_data.get('body', '')
            
            # Truncate body if too long (to save tokens)
            if len(body) > 1000:
                body = body[:1000] + "..."
            
            # Create user query
            user_query = f"""Classify and analyze this email perspective of this user ({user_id}


From: {from_address}
To: {to_addresses}
Subject: {subject}
Body: {body}


Provide the label, category, topic, and subtopic for this email based on the user's context and priorities.

{self._create_system_prompt()}"""
            
            # Prepare Ollama payload
            payload = {
                "query": user_query,
                "schema": EmailLabelOutput.model_json_schema()
            }
            
            # Make request to Ollama
            response = requests.post(self.ollama_url, json=payload, timeout=30)
            response.raise_for_status()
            
            # Parse response
            response_json = response.json()
            
            # Extract the data field if it exists (Ollama wraps response in data/status)
            if 'data' in response_json:
                result_data = response_json['data']
            else:
                result_data = response_json
            
            # Validate and create EmailLabelOutput
            result = EmailLabelOutput(**result_data)
            
            return result
            
        except requests.exceptions.RequestException as e:
            print(f"Error in Ollama API request: {str(e)}")
            print(f"ℹ️  Falling back to 'Other' label for unclassified email")
            return self._fallback_output(email_data)
        except Exception as e:
            print(f"Error in Ollama classification: {str(e)}")
            print(f"ℹ️  Falling back to 'Other' label for unclassified email")
            return self._fallback_output(email_data)
    
    def _fallback_output(self, email_data: Dict[str, Any] = None) -> EmailLabelOutput:
        """Return fallback output when classification fails"""
        subject = email_data.get('subject', 'Unclassified Email') if email_data else 'Unclassified Email'
        return EmailLabelOutput(
            label="Other",
            category="Unclassified",
            topic="Review Needed",
            subtopic=None,
            subject_matter=f"Please review: {subject[:40]}"
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
            # If rule-based found a label, use Ollama to enrich with category/topic/subtopic
            if self.ollama_available:
                enriched = self.classify_with_ollama(email_data)
                # Override the label with rule-based result
                enriched.label = label
                return enriched
            else:
                # Fallback without enrichment
                category = ' '.join(email_data.get('subject', '').split()[:3]) if email_data.get('subject') else 'General'
                subject_matter = email_data.get('subject', 'General email communication')[:50]
                return EmailLabelOutput(
                    label=label,
                    category=category,
                    topic=label.capitalize(),
                    subtopic=None,
                    subject_matter=subject_matter
                )
        
        # Fallback to Ollama classification for enriched output
        print(f"→ Using Ollama classification")
        result = self.classify_with_ollama(email_data)
        print(f"✓ Ollama label: {result.label}, category: {result.category}, topic: {result.topic}")
        
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
            return self._fallback_output({'subject': 'Empty thread'})
        
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


# # Example usage
# if __name__ == "__main__":
#     # Initialize pipeline
#     pipeline = EmailLabelPipeline(
#         ollama_url="https://lsdiedb39c.pagekite.me/chat_structure",
#         model="llama3.2"
#     )
    
#     # Test email
#     test_email = {
#         "from": "reservations@marriott.com",
#         "to": ["user@example.com"],
#         "subject": "Your Hotel Booking Confirmation",
#         "body": "Dear Guest, Your reservation at Marriott Hotel has been confirmed. Check-in: Jan 15, 2025. Check-out: Jan 18, 2025."
#     }
    
#     # Classify
#     result = pipeline.label_email(test_email)
#     print(f"\nResult:")
#     print(f"Label: {result.label}")
#     print(f"Category: {result.category}")
#     print(f"Topic: {result.topic}")
#     print(f"Subtopic: {result.subtopic}")