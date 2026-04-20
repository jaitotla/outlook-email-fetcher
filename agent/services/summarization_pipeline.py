"""
Email Thread Summarization Pipeline
Processes email threads and generates structured summaries using external LLM API
"""
import os
import json
import logging
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Base data directory
BASE_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


class SummarizationPipeline:
    """Pipeline for summarizing email threads using external LLM API"""
    
    def __init__(self, user_id: Optional[str] = None):
        """
        Initialize summarization pipeline
        
        Args:
            user_id: User identifier for scoped operations
        """
        self.user_id = user_id
        self.base_api_url = "https://lsdiedb39c.pagekite.me/chat"
        self.timeout_seconds = 500
        
        logger.info(f"✅ SummarizationPipeline initialized for user: {user_id}")
        logger.info(f"   API Endpoint: {self.base_api_url}")
    
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
    
    def create_summarization_prompt(self, email_thread_text: str) -> str:
        """
        Create the summarization prompt with strict output format
        
        Args:
            email_thread_text: Formatted email thread text
            
        Returns:
            Complete prompt for LLM
        """
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

#### 1️ Conversation Overview
- **Topic:** <one-line summary of what this email thread is about>
- **Participants:** <key people and their roles>
- **Time Range:** <first email date → last email date>

---

#### 2️ Chronological Timeline of Events
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

#### 3️ Current Status (As of Last Email)
- **Current State:** <e.g., Awaiting approval / In progress / Blocked / Completed>
- **Owner:** <person responsible now>
- **Pending Actions:** <bullet list if multiple>

---

#### 4️ Open Questions / Pending Requests
(List anything that is still unanswered or waiting)

- <Question or request>
- <Who needs to respond>

---

#### 5️ Final Ask / Next Expected Action
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
    
    def call_llm_api(self, prompt: str) -> Optional[str]:
        """
        Call external LLM API with the summarization prompt
        
        Args:
            prompt: Complete prompt for summarization
            
        Returns:
            LLM response text or None on failure
        """
        logger.info(f"🚀 Calling LLM API: {self.base_api_url}")
        logger.info(f"   Prompt size: {len(prompt)} characters")
        logger.info(f"   Timeout: {self.timeout_seconds} seconds")
        
        try:
            payload = {
                "prompt": prompt
            }
            
            response = requests.post(
                self.base_api_url,
                json=payload,
                timeout=self.timeout_seconds
            )
            
            # Raise exception for HTTP errors
            response.raise_for_status()
            
            # Parse response
            data = response.json()
            logger.info(f"✅ LLM API call successful")
            logger.info(f"   Response status: {response.status_code}")
            
            # Extract summary from response
            summary_text = data.get('response') or data.get('summary') or data.get('text') or str(data)
            logger.info(f"✅ Summary generated: {len(summary_text)} characters")
            
            return summary_text
            
        except requests.exceptions.Timeout:
            logger.error(f"❌ LLM API call timed out after {self.timeout_seconds}s")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ LLM API HTTP error: {e}")
            logger.error(f"   Response: {e.response.text if hasattr(e, 'response') else 'N/A'}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ LLM API request error: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse LLM API response: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error calling LLM API: {e}")
            return None
    
    def process_and_summarize(self, user_id: str, thread_id: str) -> Dict[str, Any]:
        """
        Main pipeline: load thread, format, call LLM, return summary
        
        Args:
            user_id: User identifier
            thread_id: Gmail thread ID
            
        Returns:
            Dict with success status, summary, and metadata
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"🚀 SUMMARIZATION PIPELINE START")
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
            'metadata': {
                'timestamp': datetime.utcnow().isoformat(),
                'messages_processed': 0,
                'api_call_time': 0
            }
        }
        
        try:
            # Step 1: Load thread data
            logger.info("📂 STEP 1: Loading thread data...")
            thread_data = self.get_thread_json_data(user_id, thread_id)
            
            if not thread_data:
                raise ValueError(f"Could not load thread data for thread_id={thread_id}")
            
            num_messages = len(thread_data.get('messages', []))
            result['metadata']['messages_processed'] = num_messages
            
            # Step 2: Format email thread
            logger.info("\n📧 STEP 2: Formatting email thread...")
            email_thread_text = self.format_email_thread_for_analysis(thread_data)
            
            if not email_thread_text:
                raise ValueError("Failed to format email thread")
            
            # Step 3: Create summarization prompt
            logger.info("\n📝 STEP 3: Creating summarization prompt...")
            prompt = self.create_summarization_prompt(email_thread_text)
            
            # Step 4: Call LLM API
            logger.info("\n🤖 STEP 4: Calling LLM API...")
            start_time = datetime.utcnow()
            summary = self.call_llm_api(prompt)
            end_time = datetime.utcnow()
            
            api_call_time = (end_time - start_time).total_seconds()
            result['metadata']['api_call_time'] = api_call_time
            
            if not summary:
                raise ValueError("LLM API returned empty response")
            
            # Step 5: Return results
            logger.info(f"\n✅ STEP 5: Processing complete (took {api_call_time:.2f}s)")
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
