import os
import json
import logging
import traceback
import csv
from typing import Dict, List, Optional

from llama_index.readers.file import PDFReader

from services.llm import LLMService
from services.settings_manager import SettingsManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _load_config() -> dict:
    """Load config from relative path, fall back to empty dict gracefully."""
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "config.json"),
        os.path.join(os.path.dirname(__file__), "config.json"),
        os.getenv("OPENMAILBOT_CONFIG_PATH", ""),
    ]
    for path in candidates:
        path = os.path.abspath(path)
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}


CONFIG = _load_config()

# Base data directory: agent/data/{user_id}/...
BASE_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
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
    """Clean pipeline: email data + inline attachment context → LLM draft."""

    def __init__(self, user_id: Optional[str] = None, effective_settings: Optional[Dict] = None):
        self.user_id = user_id

        if effective_settings:
            self.effective_settings = effective_settings
        elif user_id:
            settings_manager = SettingsManager(user_id)
            retrieved = settings_manager.get_settings(user_id, "general")
            self.effective_settings = retrieved if retrieved else {}
        else:
            self.effective_settings = {}

        self.llm_provider = self.effective_settings.get("llm_provider", "inbuilt")
        self.llm_model = self.effective_settings.get("llm_model", "gpt-4o-mini")

        try:
            self.llm_service = LLMService()
            if self.effective_settings:
                self.llm_service.effective_settings = self.effective_settings
                self.llm_service.default_provider = self.llm_provider
                self.llm_service.default_model = self.llm_model
                self.llm_service._init_clients()
            logger.info("✅ LLMService initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize LLMService: {e}")
            raise

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
    # Draft generation
    # ------------------------------------------------------------------

    async def generate_draft(
        self,
        email_data: str,
        attachment_context: str,
        thread_id: str,
        user_preferences: Dict = None,
    ) -> str:
        """Build a single prompt from email + attachment context and call LLMService."""
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

Output: A professional, concise, context-aware email reply addressing the latest discussion."""

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

        logger.info(f"🤖 Generating draft using {self.llm_provider} / {self.llm_model}...")

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

            # Step 3: Generate draft
            logger.info("📝 Generating draft...")
            draft_content = await self.generate_draft(
                email_data, attachment_context, thread_id, user_preferences
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
