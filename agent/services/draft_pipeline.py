import os
import json
import logging
import traceback
import csv
from typing import Dict, List, Optional

from llama_index.readers.file import PDFReader

from agent.services.llm import LLMService
from agent.services.settings_manager import SettingsManager
from agent.services.email_tone_pipeline import TonePipelineManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# def _load_config() -> dict:
#     """Load config from relative path, fall back to empty dict gracefully."""
#     candidates = [
#         os.path.join(os.path.dirname(__file__), "..", "config.json"),
#         os.path.join(os.path.dirname(__file__), "config.json"),
#         os.getenv("OPENMAILBOT_CONFIG_PATH", ""),
#     ]
#     for path in candidates:
#         path = os.path.abspath(path)
#         if os.path.exists(path):
#             try:
#                 with open(path, "r") as f:
#                     return json.load(f)
#             except Exception:
#                 pass
#     return {}


# CONFIG = _load_config()

# Base data directory - point to backend/data (not agent/data)
# From: openmailbot/agent/services/draft_pipeline.py
# To: openmailbot/backend/data
BASE_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),  # openmailbot/
    "backend",
    "data"
)
BASE_PATH = BASE_DATA_DIR


# ---------------------------------------------------------------------------
# Attachment extraction helpers (no RAG / no embeddings)
# ---------------------------------------------------------------------------

def _extract_csv_context(file_path: str) -> str:
    """Return a string representation of the top 5 rows of a CSV or Excel file."""
    ext = os.path.splitext(file_path)[1].lower()
    try:
        import pandas as pd
        if ext in ('.xls', '.xlsx', '.xlsm', '.xlsb'):
            df = pd.read_excel(file_path, nrows=5)
        else:
            df = pd.read_csv(file_path, nrows=5)
        return df.to_string(index=False)
    except ImportError:
        # Fallback: stdlib csv module (CSV only)
        rows = []
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.reader(f)
            for i, row in enumerate(reader):
                if i >= 6:  # header + 5 data rows
                    break
                rows.append(', '.join(row))
        return '\n'.join(rows)


def _extract_pdf_context(file_path: str) -> str:
    """Extract full text from a PDF file using llama_index PDFReader."""
    from pathlib import Path
    reader = PDFReader()
    documents = reader.load_data(file=Path(file_path))
    parts = [doc.text.strip() for doc in documents if doc.text and doc.text.strip()]
    return '\n\n'.join(parts)


def _extract_attachment_context(file_path: str, filename: str) -> str:
    """Dispatch to the correct extractor based on file extension."""
    ext = os.path.splitext(filename)[1].lower()

    if ext in ('.csv', '.xls', '.xlsx', '.xlsm', '.xlsb'):
        logger.info(f"  📊 Extracting top 5 rows from {filename}")
        content = _extract_csv_context(file_path)
        return f"[Spreadsheet: {filename} — Top 5 rows]\n{content}"

    elif ext == '.pdf':
        logger.info(f"  📄 Extracting PDF content from {filename}")
        content = _extract_pdf_context(file_path)
        return f"[PDF: {filename}]\n{content}"

    elif ext in ('.txt', '.md', '.rst'):
        logger.info(f"  📝 Reading text file {filename}")
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            return f"[Text file: {filename}]\n{f.read()}"

    else:
        logger.info(f"  ⚠️  Unsupported attachment type: {filename} — skipped")
        return f"[Attachment: {filename} — unsupported type, skipped]"


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class DraftPipeline:
    """Clean pipeline: email data + inline attachment context + tone profile → LLM draft."""

    def __init__(self, user_id: Optional[str] = None, effective_settings: Optional[Dict] = None):
        self.user_id = user_id

        if effective_settings:
            self.effective_settings = effective_settings
        elif user_id:
            settings_manager = SettingsManager(user_id)
            retrieved = settings_manager.get_settings(setting_type="general")
            self.effective_settings = retrieved if retrieved else {}
        else:
            self.effective_settings = {}

        self.llm_provider = self.effective_settings.get("llm_provider")
        self.llm_model = self.effective_settings.get("llm_model")

        try:
            # Pass effective_settings to LLMService constructor
            self.llm_service = LLMService(effective_settings=self.effective_settings)
            logger.info("✅ LLMService initialized successfully")
            logger.info(f"   LLM Provider: {self.llm_provider}")
            logger.info(f"   LLM Model: {self.llm_model}")
        except Exception as e:
            logger.error(f"Failed to initialize LLMService: {e}")
            raise

        # Initialize TonePipelineManager for tone-aware drafting
        try:
            tone_base_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),  # openmailbot/
                "backend",
                "data"
            )
            self.tone_manager = TonePipelineManager(user_id, tone_base_dir) if user_id else None
            if self.tone_manager:
                logger.info("✅ TonePipelineManager initialized for tone-aware drafting")
        except Exception as e:
            logger.warning(f"⚠️  TonePipelineManager initialization failed (non-fatal): {e}")
            self.tone_manager = None

    def close(self):
        """Close any open database connections."""
        try:
            if self.tone_manager:
                self.tone_manager.close()
                logger.info("✅ TonePipelineManager closed")
        except Exception as e:
            logger.warning(f"Error closing TonePipelineManager: {e}")

    def __del__(self):
        """Ensure connections are closed on garbage collection."""
        self.close()

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    def get_thread_json_data(self, user_id: str, thread_id: str) -> Optional[Dict]:
        """Load thread data from the user's log_emails directory."""
        file_path = os.path.join(
            BASE_DATA_DIR, user_id, "log_emails", thread_id, f"{thread_id}.json"
        )
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
        """Return a list of attachment dicts from the store_attachments directory."""
        thread_path = os.path.join(BASE_DATA_DIR, user_id, "store_attachments", thread_id)

        if not os.path.exists(thread_path):
            logger.warning(f"No attachments directory for thread: {thread_id}")
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
                                    'message_id': metadata.get('message_id'),
                                })
                except Exception as e:
                    logger.error(f"Error reading metadata file {metadata_file}: {e}")

        # Fallback: list raw files if no metadata found
        if not attachments:
            for file in os.listdir(thread_path):
                if not file.endswith('_metadata.json'):
                    attachments.append({
                        'filename': file,
                        'path': os.path.join(thread_path, file),
                        'attachment_id': file,
                    })

        return attachments

    # ------------------------------------------------------------------
    # Attachment context extraction
    # ------------------------------------------------------------------

    def extract_attachments_context(self, user_id: str, thread_id: str) -> str:
        """
        Extract inline context from all attachments for a thread.

        - CSV / Excel  → top 5 rows
        - PDF          → full text
        - Text files   → raw content
        - Other        → skipped with a note
        """
        attachments = self.get_thread_attachments(user_id, thread_id)
        if not attachments:
            logger.info("No attachments found for this thread.")
            return ""

        context_parts = []
        for att in attachments:
            filename = att.get('filename', 'unknown')
            file_path = att.get('path')

            if not file_path or not os.path.exists(file_path):
                logger.warning(f"  ⚠️  Attachment file not found: {file_path}")
                continue

            try:
                context = _extract_attachment_context(file_path, filename)
                context_parts.append(context)
                logger.info(f"  ✅ Extracted context from {filename}")
            except Exception as e:
                logger.error(f"  ❌ Failed to extract {filename}: {e}")
                context_parts.append(f"[Attachment: {filename} — extraction failed: {e}]")

        return "\n\n---\n\n".join(context_parts)

    # ------------------------------------------------------------------
    # Tone-aware context extraction
    # ------------------------------------------------------------------

    def _extract_primary_recipient(self, thread_data: Dict) -> Optional[str]:
        """
        Extract the primary recipient from the thread (usually the sender of the most recent email).
        
        Logic:
        - Get the most recent message where from != user_id (the other party)
        - Return their email address
        
        Returns None if no suitable recipient found.
        """
        messages = thread_data.get('messages', [])
        if not messages:
            return None
        
        # Get the most recent message (last one in the list)
        latest_msg = messages[-1]
        sender = latest_msg.get('from', '').strip().lower()
        user_id_lower = (self.user_id or '').strip().lower()
        
        # If the latest message is from someone else, that's our primary recipient
        if sender and sender != user_id_lower:
            return latest_msg.get('from')
        
        # Otherwise, find the most recent message from someone else
        for msg in reversed(messages):
            sender = msg.get('from', '').strip().lower()
            if sender and sender != user_id_lower:
                return msg.get('from')
        
        return None

    def _build_tone_context(self, recipient: str) -> str:
        """
        Build a style card from the user's tone profile with this recipient.
        
        Returns a string that will be injected into the system prompt to make
        the LLM generate replies matching the user's established writing style.
        
        Components:
        - Aggregate tone profile (from full SQLite history)
        - Recent 3 email examples (from ChromaDB, for few-shot learning)
        - Stability indicators (flagged if tone is variable)
        """
        if not self.tone_manager or not recipient:
            logger.info("ℹ️  No tone profile available (manager not initialized or no recipient)")
            return ""
        
        try:
            logger.info(f"📝 Building tone context for {recipient}...")
            
            # Get aggregate profile
            profile = self.tone_manager.get_style_profile_stats(recipient)
            if not profile or profile.get('n_emails_observed', 0) == 0:
                logger.info(f"   ℹ️  No prior emails to {recipient} — using neutral defaults")
                return ""
            
            # Get recent examples for few-shot
            recent_emails = self.tone_manager.get_recent_emails_for_recipient(recipient, n_results=3)
            
            # Build style card
            tone_context = self._build_style_card(recipient, profile, recent_emails)
            logger.info(f"   ✅ Tone context built ({profile.get('n_emails_observed', 0)} emails analyzed)")
            return tone_context
            
        except Exception as e:
            logger.warning(f"⚠️  Failed to build tone context: {e}")
            return ""

    def _build_style_card(self, recipient: str, profile: Dict, few_shot_examples: List[Dict]) -> str:
        """
        Build the style directive block for the system prompt.
        
        Shows:
        - Relationship type and authority
        - Aggregate writing style (tone, politeness, warmth, etc.)
        - Flags for variable dimensions
        - Recent examples for few-shot learning
        """
        if not profile:
            return ""
        
        n_emails = profile.get('n_emails_observed', 0)
        if n_emails == 0:
            return ""
        
        lines = [
            f"━━━ TONE CONTEXT (based on {n_emails} prior email(s) to this recipient) ━━━",
            f"",
            f"Relationship: {profile.get('relationship_type', 'Unknown')} "
            f"(authority: {profile.get('authority', 'Equal')})",
        ]
        
        # Add writing style profile
        style_attrs = ['tone', 'politeness', 'warmth', 'directness', 'professionalism', 'respectfulness']
        style_lines = []
        for attr in style_attrs:
            attr_data = profile.get(attr, {})
            label = attr_data.get('label', 'Unknown')
            stability = attr_data.get('stability', '')
            
            if stability in ('somewhat variable', 'highly variable'):
                style_lines.append(f"  • {attr}: {label} ({stability})")
            else:
                style_lines.append(f"  • {attr}: {label}")
        
        lines.extend(["", "Writing Style:"] + style_lines)
        
        # Add few-shot examples
        if few_shot_examples:
            lines.extend([
                "",
                "Recent examples of how you write to this recipient:",
            ])
            for i, example in enumerate(few_shot_examples, 1):
                lines.append(f"  [{i}] {example.get('email_text', '')[:100]}...")
        
        lines.append("━━━ END TONE CONTEXT ━━━")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Draft generation
    # ------------------------------------------------------------------

    async def generate_draft(
        self,
        email_data: str,
        attachment_context: str,
        thread_id: str,
        user_preferences: Dict = None,
        tone_context: str = None,
    ) -> str:
        """
        Build a single prompt from email + attachment context + tone profile and call LLMService.
        
        Args:
            email_data: The email thread as JSON
            attachment_context: Extracted attachment content (CSV/PDF/etc.)
            thread_id: The thread ID
            user_preferences: User preferences (name, position, tone, etc.)
            tone_context: Optional tone profile string (from _build_tone_context)
        """
        prefs = user_preferences or {}
        name = prefs.get('name', 'User')
        position = prefs.get('position', 'Professional')
        tone = prefs.get('tone', 'professional and concise')
        custom_instructions = prefs.get('custom_instructions', '')

        system_prompt = f"""You are an AI email assistant helping {name}, a {position}, to draft professional email responses.

Your responsibilities:
- Analyze the full email thread for background and continuity
- Focus primarily on the MOST RECENT 4–5 emails to determine current topic and intent
- Draft a professional reply that directly addresses the latest email
- Detect and personalize the greeting and signature based on recipient(s)

RECIPIENT DETECTION & PERSONALIZATION:
1. Extract all recipient names from the email thread (look for senders/recipients in the thread)
2. Greeting Rules:
   - If ONE recipient: Use personalized greeting "Dear [Recipient Name]," at the start
   - If MULTIPLE recipients: Use "Dear Team," as the greeting
   - Always extract the actual names from the email addresses if available
3. Signature Rules:
   - Always end with an appropriate closing: "Regards," or "Best regards,"
   - Follow the closing with the sender's name: {name}
   - Format: "Regards,\n{name}" or "Best regards,\n{name}"

Guidelines:
- Tone: {tone}
- Additional Instructions: {custom_instructions}
- Be accurate and context-aware
- Use the full thread ONLY as historical reference
- DO NOT repeat or summarize early-stage discussion unless required
- The response should reflect the current state of the conversation
- If attachment content is provided, incorporate relevant information naturally

Important Rules:
1. Prioritize the last 4–5 emails when drafting
2. Use older emails only for continuity and context
3. The draft must sound like a natural continuation of the latest exchange
4. Do NOT recap the entire thread
5. If attachment data is provided, use it appropriately in the response
6. Always include personalized greeting at the beginning
7. Always include signature with {name} at the end

Output: A professional, concise, context-aware email reply with personalized greeting, body addressing the latest discussion, and signature including {name}."""

        # Inject tone context if available
        if tone_context:
            system_prompt += f"\n\n{tone_context}\n\n"
            system_prompt += "IMPORTANT: When drafting the reply, match the recipient-specific tone and style shown above."

        attachment_section = (
            f"\n\nATTACHMENT CONTENT:\n{attachment_context}"
            if attachment_context else ""
        )

        user_prompt = f"""EMAIL THREAD:
{email_data}{attachment_section}

Please draft a professional email response that:
1. Addresses the most recent email in the thread
2. Incorporates relevant attachment information if provided
3. Maintains the conversation's current context and tone
4. Is ready to send without further editing"""

        # Determine actual model for logging
        actual_model = self.llm_model
        if self.llm_provider in ("manotr", "inbuilt"):
            actual_model = "llama3.2"  # Hardcoded in utils.py
            logger.info(f"🤖 Generating draft using {self.llm_provider}")
            logger.info(f"   Configured Model: {self.llm_model} (ignored for {self.llm_provider})")
            logger.info(f"   Actual Model: {actual_model}")
        else:
            logger.info(f"🤖 Generating draft using {self.llm_provider} / {actual_model}...")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        draft_content = await self.llm_service.generate(
            messages,
            provider=self.llm_provider,
            model=self.llm_model,
            temperature=0.7,
        )

        logger.info("✅ Draft generated successfully")
        return draft_content

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def process_email_request(
        self,
        user_id: str,
        thread_id: str,
        user_preferences: Dict = None,
    ) -> Dict:
        """
        Main pipeline entry point.

        Flow:
        1. Load email thread JSON
        2. Extract attachment content inline (CSV → top 5 rows, PDF → full text)
        3. Combine into a single prompt and call LLMService
        4. Return the generated draft

        Args:
            user_id: User identifier (email address)
            thread_id: Gmail thread ID
            user_preferences: User settings for draft generation

        Returns:
            Dict with 'success', 'draft_content', and 'processing_info'
        """
        logger.info(f"🚀 Starting draft pipeline for user: {user_id}, thread: {thread_id}")

        processing_info: Dict = {
            'attachments_found': 0,
            'errors': [],
        }

        try:
            # Step 1: Load email thread
            thread_data = self.get_thread_json_data(user_id, thread_id)
            if not thread_data:
                return {
                    'success': False,
                    'error': f'Thread JSON not found for thread_id: {thread_id}',
                    'processing_info': processing_info,
                }

            email_data = json.dumps(thread_data, indent=2)
            logger.info(f"Loaded thread data with {len(thread_data.get('messages', []))} messages")

            # Step 2: Extract attachment context (inline, no RAG)
            logger.info("📎 Extracting attachment context...")
            attachment_context = self.extract_attachments_context(user_id, thread_id)
            processing_info['attachments_found'] = len(
                self.get_thread_attachments(user_id, thread_id)
            )

            if attachment_context:
                logger.info(f"📚 Attachment context: {len(attachment_context)} characters")
            else:
                logger.info("ℹ️  No attachment context")

            # Step 3: Extract tone context (if tone profile available)
            logger.info("🎨 Extracting tone profile...")
            tone_context = ""
            processing_info['tone_profile'] = None
            
            try:
                recipient = self._extract_primary_recipient(thread_data)
                if recipient:
                    logger.info(f"   Recipient detected: {recipient}")
                    tone_context = self._build_tone_context(recipient)
                    processing_info['tone_profile'] = {
                        'recipient': recipient,
                        'has_context': bool(tone_context)
                    }
                    if tone_context:
                        logger.info(f"   ✅ Tone profile loaded for {recipient}")
                    else:
                        logger.info(f"   ℹ️  No tone profile for {recipient} (first email or not yet captured)")
                else:
                    logger.info("   ℹ️  Could not determine recipient")
            except Exception as tone_err:
                logger.warning(f"   ⚠️  Tone extraction failed (non-fatal): {tone_err}")
                processing_info['tone_profile'] = {'error': str(tone_err)}

            # Step 4: Generate draft
            logger.info("📝 Generating draft with tone awareness...")
            draft_content = await self.generate_draft(
                email_data, attachment_context, thread_id, user_preferences, tone_context=tone_context
            )

            logger.info("✅ Draft pipeline completed successfully")
            return {
                'success': True,
                'draft_content': draft_content,
                'processing_info': processing_info,
            }

        except Exception as e:
            logger.error(f"Draft pipeline error: {e}")
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'error': str(e),
                'processing_info': processing_info,
            }
