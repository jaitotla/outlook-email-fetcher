"""
email_tone_pipeline.py
=======================================================================
Production-style pipeline for email tone / relationship personalization.
Integrated with the labeling system to capture user writing style for
emails SENT by the user (where "from" == user_id).

USES EXISTING SERVICES:
- LLMService: Handles all LLM provider logic (OpenAI, Anthropic, Groq, Ollama, etc.)
- SettingsManager: Loads user's configured LLM provider, model, and API key
- No hardcoded providers or custom LLM wrappers

WHAT IT DOES:
1. On label API call, checks if email is SENT (from == user_id)
2. Extracts structured relationship + writing-style info via user's configured LLM
3. Stores FULL history in per-user SQLite (audit log)
4. Stores in ChromaDB (rolling 3 per recipient) for few-shot retrieval
5. Available for drafting agent to use as style guidance

SCHEMA (extracted by LLM with structured JSON output):
{
  "recipient": "prof.sharma@university.edu",
  "relationship": {"type": "Professor", "familiarity": "Established", "authority": "Higher"},
  "writing_style": {
    "tone": "Formal", "politeness": "Very Polite", "warmth": "Neutral",
    "directness": "Indirect", "professionalism": "High",
    "respectfulness": "High", "confidence": "Moderate"
  }
}

USAGE (from labeling pipeline):
    manager = TonePipelineManager(user_id="user@example.com", base_data_dir="/path/to/data")
    extracted = await manager.process_sent_email(
        recipient="prof.sharma@university.edu",
        email_text="Dear Professor Sharma, thank you for..."
    )
    manager.close()
=======================================================================
"""

import json
import logging
import os
import re
import sqlite3
import time
import uuid
from typing import Callable, Dict, List, Optional

from agent.services.llm import LLMService
from agent.services.settings_manager import SettingsManager

try:
    import chromadb
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False

logger = logging.getLogger(__name__)

# =======================================================================
# CONFIG
# =======================================================================

MAX_EMAILS_PER_RECIPIENT_IN_CHROMA = 3
CHROMA_COLLECTION_NAME = "recipient_style_emails"

SYSTEM_PROMPT = """You are a precise writing-style analyst.
Given a SENT email (written BY the user TO a recipient), extract structured
information about the relationship and writing style the user used.

You MUST respond with ONLY valid JSON, no preamble, no markdown fences,
matching EXACTLY this schema and these allowed values:

{
  "recipient": "<the recipient email address, copied as given>",
  "relationship": {
    "type": "<one of: Professor, Manager, Senior Colleague, Peer, Friend, Client, Other>",
    "familiarity": "<one of: New, Developing, Established>",
    "authority": "<one of: Higher, Equal, Lower>"
  },
  "writing_style": {
    "tone": "<one of: Formal, Semi-formal, Casual>",
    "politeness": "<one of: Very Polite, Polite, Neutral, Blunt>",
    "warmth": "<one of: Warm, Neutral, Cold>",
    "directness": "<one of: Direct, Indirect>",
    "professionalism": "<one of: High, Medium, Low>",
    "respectfulness": "<one of: High, Medium, Low>",
    "confidence": "<one of: High, Moderate, Low>"
  }
}

"confidence" here means how confident a reader would be about the sender's
tone/intent from this email alone (i.e. how much hedging language is used).
Base every judgment only on the email text provided. Output JSON only."""


# =======================================================================
# JSON EXTRACTION HELPERS
# =======================================================================

def _extract_json_block(raw_text: str) -> dict:
    """LLM models sometimes wrap JSON in prose or code fences. Strip that."""
    text = raw_text.strip()
    text = re.sub(r"^```(json)?", "", text.strip())
    text = re.sub(r"```$", "", text.strip())
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in LLM output: {raw_text[:200]}")
    return json.loads(match.group(0))


def _default_extracted(recipient: str) -> dict:
    """Returns a safe default extraction when LLM fails or is unavailable."""
    return {
        "recipient": recipient,
        "relationship": {"type": "Other", "familiarity": "Developing", "authority": "Equal"},
        "writing_style": {
            "tone": "Semi-formal",
            "politeness": "Neutral",
            "warmth": "Neutral",
            "directness": "Direct",
            "professionalism": "Medium",
            "respectfulness": "Medium",
            "confidence": "Moderate",
        },
    }


def _fill_defaults(parsed: dict, recipient: str) -> None:
    """In-place fill missing fields with safe defaults."""
    parsed.setdefault("recipient", recipient)
    parsed.setdefault("relationship", {})
    parsed.setdefault("writing_style", {})

    rel = parsed["relationship"]
    rel.setdefault("type", "Other")
    rel.setdefault("familiarity", "Developing")
    rel.setdefault("authority", "Equal")

    ws = parsed["writing_style"]
    ws.setdefault("tone", "Semi-formal")
    ws.setdefault("politeness", "Neutral")
    ws.setdefault("warmth", "Neutral")
    ws.setdefault("directness", "Direct")
    ws.setdefault("professionalism", "Medium")
    ws.setdefault("respectfulness", "Medium")
    ws.setdefault("confidence", "Moderate")


# =======================================================================
# TONE EXTRACTION -- Uses LLMService (all providers)
# =======================================================================

async def extract_email_style(
    recipient: str,
    email_text: str,
    llm_service: Optional[LLMService] = None,
) -> dict:
    """
    Calls user's configured LLM (via LLMService) to extract structured tone info.
    
    Uses LLMService which handles ALL provider logic:
    - OpenAI (GPT-4, GPT-3.5)
    - Anthropic (Claude 3+)
    - Groq (Llama, Mixtral)
    - Ollama (local models)
    - Others configured by user
    
    Returns a dict matching the schema in SYSTEM_PROMPT.

    Args:
        recipient: Email recipient address
        email_text: The full email body
        llm_service: LLMService instance initialized with user settings

    Returns:
        Extracted dict with relationship + writing_style or defaults on error
    """
    if not llm_service:
        logger.warning("No LLMService provided; using safe defaults")
        return _default_extracted(recipient)

    try:
        user_prompt = (
            f"Recipient: {recipient}\n\n"
            f"Email text:\n\"\"\"\n{email_text}\n\"\"\"\n\n"
            f"Extract the structured JSON now."
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # LLMService handles provider logic, API calls, error handling
        provider = llm_service.effective_settings.get("llm_provider", "openai")
        model = llm_service.effective_settings.get("llm_model", "gpt-4o-mini")
        
        response = await llm_service.generate(
            messages,
            provider=provider,
            model=model,
            temperature=0.1,  # Low temp for consistent JSON
        )
        
        parsed = _extract_json_block(response)
        _fill_defaults(parsed, recipient)
        return parsed

    except Exception as e:
        logger.warning(f"Failed to extract tone for {recipient}: {e}")
        return _default_extracted(recipient)


# =======================================================================
# STORAGE -- SQLite (full history) + ChromaDB (rolling 3 per recipient)
# =======================================================================

def init_sqlite(db_path: str) -> sqlite3.Connection:
    """Initialize or open SQLite database for tone history."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS emails (
            id TEXT PRIMARY KEY,
            recipient TEXT NOT NULL,
            email_text TEXT NOT NULL,
            relationship_type TEXT,
            familiarity TEXT,
            authority TEXT,
            tone TEXT,
            politeness TEXT,
            warmth TEXT,
            directness TEXT,
            professionalism TEXT,
            respectfulness TEXT,
            confidence TEXT,
            created_at REAL NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_emails_recipient ON emails(recipient)")
    conn.commit()
    return conn


def store_in_sqlite(
    conn: sqlite3.Connection,
    recipient: str,
    email_text: str,
    extracted: dict,
    email_id: Optional[str] = None,
) -> str:
    """Stores one processed email permanently. Returns the email_id."""
    email_id = email_id or str(uuid.uuid4())
    rel = extracted.get("relationship", {})
    style = extracted.get("writing_style", {})

    conn.execute(
        """
        INSERT INTO emails (
            id, recipient, email_text, relationship_type, familiarity, authority,
            tone, politeness, warmth, directness, professionalism, respectfulness,
            confidence, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            email_id,
            recipient,
            email_text,
            rel.get("type"),
            rel.get("familiarity"),
            rel.get("authority"),
            style.get("tone"),
            style.get("politeness"),
            style.get("warmth"),
            style.get("directness"),
            style.get("professionalism"),
            style.get("respectfulness"),
            style.get("confidence"),
            time.time(),
        ),
    )
    conn.commit()
    return email_id


def get_all_emails_for_recipient(conn: sqlite3.Connection, recipient: str):
    """Retrieve all stored emails for a recipient (audit history)."""
    cur = conn.execute(
        "SELECT * FROM emails WHERE recipient = ? ORDER BY created_at ASC", (recipient,)
    )
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def init_chroma(db_path: str):
    """
    Initialize ChromaDB for per-recipient style embeddings.
    Uses ChromaDB's default embedding (sentence-transformers).
    """
    if not HAS_CHROMADB:
        logger.warning("ChromaDB not installed; skipping embedding storage")
        return None, None

    try:
        client = chromadb.PersistentClient(path=db_path)
        collection = client.get_or_create_collection(
            name=CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("ChromaDB initialized with default embedding")
        return client, collection
    except Exception as e:
        logger.warning(f"Failed to initialize ChromaDB: {e}")
        return None, None


def store_in_chroma(
    collection,
    recipient: str,
    email_text: str,
    extracted: dict,
    email_id: Optional[str] = None,
    max_per_recipient: int = MAX_EMAILS_PER_RECIPIENT_IN_CHROMA,
) -> str:
    """
    Embeds + inserts one email into ChromaDB, then enforces rolling window.
    """
    if collection is None:
        return email_id or str(uuid.uuid4())

    email_id = email_id or str(uuid.uuid4())
    rel = extracted.get("relationship", {})
    style = extracted.get("writing_style", {})
    created_at = time.time()

    metadata = {
        "recipient": recipient,
        "created_at": created_at,
        "relationship_type": rel.get("type", ""),
        "familiarity": rel.get("familiarity", ""),
        "authority": rel.get("authority", ""),
        "tone": style.get("tone", ""),
        "politeness": style.get("politeness", ""),
        "warmth": style.get("warmth", ""),
        "directness": style.get("directness", ""),
        "professionalism": style.get("professionalism", ""),
        "respectfulness": style.get("respectfulness", ""),
        "confidence": style.get("confidence", ""),
        "extracted_json": json.dumps(extracted),
    }

    try:
        collection.add(ids=[email_id], documents=[email_text], metadatas=[metadata])
        _evict_old_entries(collection, recipient, max_per_recipient)
    except Exception as e:
        logger.warning(f"Failed to store in ChromaDB: {e}")

    return email_id


def _evict_old_entries(collection, recipient: str, max_per_recipient: int) -> None:
    """Keeps only the `max_per_recipient` newest docs for a recipient."""
    try:
        existing = collection.get(where={"recipient": recipient}, include=["metadatas"])
        ids = existing["ids"]
        metadatas = existing["metadatas"]

        if len(ids) <= max_per_recipient:
            return

        paired = sorted(
            zip(ids, metadatas), key=lambda pair: pair[1]["created_at"], reverse=True
        )
        ids_to_keep = {pid for pid, _ in paired[:max_per_recipient]}
        ids_to_delete = [pid for pid in ids if pid not in ids_to_keep]

        if ids_to_delete:
            collection.delete(ids=ids_to_delete)
            logger.info(
                f"Evicted {len(ids_to_delete)} old entries for {recipient} "
                f"(keeping {max_per_recipient})"
            )
    except Exception as e:
        logger.warning(f"Failed to evict old entries: {e}")


def get_recent_emails_for_recipient(collection, recipient: str, n_results: int = 3):
    """Retrieval used by drafting agent: latest style examples for a recipient."""
    if collection is None:
        return []

    try:
        existing = collection.get(
            where={"recipient": recipient}, include=["documents", "metadatas"]
        )
        paired = sorted(
            zip(existing["ids"], existing["documents"], existing["metadatas"]),
            key=lambda triple: triple[2]["created_at"],
            reverse=True,
        )
        paired = paired[:n_results]
        return [{"id": pid, "email_text": doc, "metadata": meta} for pid, doc, meta in paired]
    except Exception as e:
        logger.warning(f"Failed to retrieve recent emails: {e}")
        return []


def count_docs_for_recipient(collection, recipient: str) -> int:
    """Count stored emails for a recipient in ChromaDB."""
    if collection is None:
        return 0
    try:
        existing = collection.get(where={"recipient": recipient}, include=[])
        return len(existing["ids"])
    except Exception:
        return 0


# =======================================================================
# TONE PIPELINE MANAGER -- Per-user, uses existing services
# =======================================================================

class TonePipelineManager:
    """
    Per-user manager for tone extraction + storage using LLMService & SettingsManager.
    
    Automatically loads user settings and respects their configured LLM provider,
    model, and API key. No hardcoded providers.
    """

    def __init__(self, user_id: str, base_data_dir: str):
        """
        Args:
            user_id: The user's email or unique identifier
            base_data_dir: Base path to `data/` folder (e.g., /backend/data)
        """
        self.user_id = user_id
        self.base_data_dir = base_data_dir

        # Load settings via SettingsManager
        try:
            settings_manager = SettingsManager(user_id)
            retrieved = settings_manager.get_settings(setting_type="general")
            self.effective_settings = retrieved if retrieved else {}
            logger.info(f"✅ Loaded settings for {user_id}")
        except Exception as e:
            logger.warning(f"Failed to load settings: {e}; using empty dict")
            self.effective_settings = {}

        # Initialize LLMService with user's settings
        try:
            self.llm_service = LLMService(effective_settings=self.effective_settings)
            logger.info("✅ LLMService initialized for tone extraction")
        except Exception as e:
            logger.warning(f"⚠️  LLMService init failed (non-fatal): {e}")
            self.llm_service = None

        # Create user-isolated tone_db
        self.user_tone_dir = os.path.join(base_data_dir, user_id, "tone_db")
        os.makedirs(self.user_tone_dir, exist_ok=True)

        self.sqlite_path = os.path.join(self.user_tone_dir, "email_history.db")
        self.chroma_path = os.path.join(self.user_tone_dir, "chroma_store")

        # Initialize storage connections
        self.sqlite_conn = init_sqlite(self.sqlite_path)
        self.chroma_client, self.chroma_collection = init_chroma(self.chroma_path)

        logger.info(
            f"TonePipelineManager initialized for {user_id} "
            f"(SQLite: {self.sqlite_path})"
        )

    def close(self):
        """Close database connections."""
        try:
            if self.sqlite_conn:
                self.sqlite_conn.close()
                logger.info("✅ SQLite connection closed")
        except Exception as e:
            logger.warning(f"Failed to close SQLite: {e}")

    def __del__(self):
        """Ensure connections closed on garbage collection."""
        self.close()

    async def process_sent_email(
        self,
        recipient: str,
        email_text: str,
        email_id: Optional[str] = None,
    ) -> dict:
        """
        End-to-end processing of a SENT email using user's LLM provider.
        
        Flow:
        1. Extract tone via LLMService (uses user's provider/model)
        2. Store in SQLite (full audit history)
        3. Store in ChromaDB (rolling window for few-shot)

        Args:
            recipient: Email recipient address
            email_text: Full email body
            email_id: Optional ID to tie back to source

        Returns:
            Extracted dict with relationship + writing_style
        """
        try:
            logger.info(f"🎨 Extracting tone for {recipient}...")
            
            # Step 1: Extract tone using LLMService
            extracted = await extract_email_style(
                recipient,
                email_text,
                llm_service=self.llm_service,
            )

            # Step 2: Store in SQLite (audit history)
            sqlite_id = store_in_sqlite(
                self.sqlite_conn, recipient, email_text, extracted, email_id=email_id
            )
            logger.info(f"   ✅ Stored in SQLite: {sqlite_id}")

            # Step 3: Store in ChromaDB (rolling window)
            if self.chroma_collection:
                store_in_chroma(
                    self.chroma_collection, recipient, email_text, extracted, email_id=sqlite_id
                )
                count = count_docs_for_recipient(self.chroma_collection, recipient)
                logger.info(f"   ✅ Stored in ChromaDB ({count}/{MAX_EMAILS_PER_RECIPIENT_IN_CHROMA})")

            return extracted

        except Exception as e:
            logger.error(f"Failed to process sent email for {recipient}: {e}", exc_info=True)
            return _default_extracted(recipient)

    def get_all_emails_for_recipient(self, recipient: str) -> List[dict]:
        """Retrieve full audit history for a recipient."""
        try:
            return get_all_emails_for_recipient(self.sqlite_conn, recipient)
        except Exception as e:
            logger.error(f"Failed to retrieve emails for {recipient}: {e}")
            return []

    def get_recent_emails_for_recipient(self, recipient: str, n_results: int = 3) -> List[dict]:
        """Retrieve recent style examples for drafting agent."""
        return get_recent_emails_for_recipient(self.chroma_collection, recipient, n_results)

    def get_style_profile_stats(self, recipient: str) -> dict:
        """Aggregates SQLite history for a recipient into style stats summary."""
        rows = self.get_all_emails_for_recipient(recipient)
        if not rows:
            return {}

        return {
            "n_emails_observed": len(rows),
            "recipient": recipient,
            "emails": rows,
        }
