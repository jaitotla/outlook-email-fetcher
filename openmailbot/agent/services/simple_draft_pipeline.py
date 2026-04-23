import os
import json
import logging
import traceback
from typing import Dict, List, Optional

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


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class SimpleDraftPipeline:
    """Simple pipeline: email data → LLM draft (no attachments)."""

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
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading thread JSON {file_path}: {e}")
            return None

    # ------------------------------------------------------------------
    # Draft generation
    # ------------------------------------------------------------------

    async def generate_draft(
        self,
        email_data: str,
        thread_id: str,
        user_preferences: Dict = None,
    ) -> str:
        """Build a single prompt from email data and call LLMService."""
        prefs = user_preferences or {}
        name = prefs.get("name", "User")
        position = prefs.get("position", "Professional")
        tone = prefs.get("tone", "professional and concise")
        custom_instructions = prefs.get("custom_instructions", "")

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

Important Rules:
1. Prioritize the last 4–5 emails when drafting
2. Use older emails only for continuity and context
3. The draft must sound like a natural continuation of the latest exchange
4. Do NOT recap the entire thread

Output: A professional, concise, context-aware email reply addressing the latest discussion."""

        user_prompt = f"""EMAIL THREAD:
{email_data}

Please draft a professional email response that:
1. Addresses the most recent email in the thread
2. Maintains the conversation's current context and tone
3. Is ready to send without further editing"""

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
        1. Load email thread JSON from disk
        2. Send to LLMService to generate draft
        3. Return the generated draft

        Args:
            user_id: User identifier (email address)
            thread_id: Gmail thread ID
            user_preferences: User settings for draft generation

        Returns:
            Dict with 'success', 'draft_content', and 'processing_info'
        """
        logger.info(f"🚀 Starting simple draft pipeline for user: {user_id}, thread: {thread_id}")

        processing_info: Dict = {"errors": []}

        try:
            # Step 1: Load email thread
            thread_data = self.get_thread_json_data(user_id, thread_id)
            if not thread_data:
                return {
                    "success": False,
                    "error": f"Thread JSON not found for thread_id: {thread_id}",
                    "processing_info": processing_info,
                }

            email_data = json.dumps(thread_data, indent=2)
            logger.info(
                f"Loaded thread data with {len(thread_data.get('messages', []))} messages"
            )

            # Step 2: Generate draft
            logger.info("📝 Generating draft...")
            draft_content = await self.generate_draft(
                email_data, thread_id, user_preferences
            )

            logger.info("✅ Simple draft pipeline completed successfully")
            return {
                "success": True,
                "draft_content": draft_content,
                "processing_info": processing_info,
            }

        except Exception as e:
            logger.error(f"Simple draft pipeline error: {e}")
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": str(e),
                "processing_info": processing_info,
            }
