"""
store_pipeline.py
=================
Two lightweight pipelines that run after preprocessed email data is available:

1. CheckAndStoreEmailPipeline
   - Receives a list of preprocessed messages (user_id, thread_id, messages[])
   - For each message checks whether (user_id, thread_id, message_id) already
     exists in the per-user SQLite DB / ChromaDB vector store
   - If not processed → generates embedding and stores in vector DB, then marks
     as processed in SQLite

2. CheckAndStoreAttachmentsPipeline
   - Receives user_id + thread_id (attachments already saved to disk by
     /api/store-attachments)
   - For each attachment checks whether (user_id, thread_id, attachment_id)
     already exists
   - If not processed → extracts text, generates embeddings per chunk, stores
     in vector DB, then marks as processed
"""

import os
import json
import sqlite3
import asyncio
import traceback
import re
import concurrent.futures
import logging
from typing import Dict, List, Optional, Set

import chromadb
from llama_index.core import SimpleDirectoryReader
from llama_index.readers.file import PDFReader, CSVReader

from agent.services.embeddings import EmbeddingService
from agent.services.settings_manager import SettingsManager

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (mirror chat_pipeline.py)
# ---------------------------------------------------------------------------
# Base data directory - point to backend/data (not agent/data)
# From: openmailbot/agent/services/store_pipeline.py
# To: openmailbot/backend/data
BASE_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),  # openmailbot/
    "backend",
    "data"
)

FILE_EXTRACTOR = {
    ".pdf": PDFReader(),
    ".csv": CSVReader(),
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sanitize_namespace(namespace: str) -> str:
    """Sanitize namespace to be ChromaDB-compliant ([a-zA-Z0-9._-])."""
    sanitized = namespace.replace("@", ".").replace(":", "_")
    sanitized = re.sub(r"[^a-zA-Z0-9._\-]", "_", sanitized)
    return sanitized


# ---------------------------------------------------------------------------
# Shared DB / Vector DB mixin
# ---------------------------------------------------------------------------

class _BaseStorePipeline:
    """Shared infrastructure: SQLite tracking DB + ChromaDB + EmbeddingService."""

    def __init__(self, user_id: Optional[str] = None):
        self.user_id = user_id
        try:
            # Load full user settings from DB, then inject user_id
            user_settings = {}
            if user_id:
                loaded = SettingsManager(user_id=user_id).get_settings(user_id=user_id)
                if loaded:
                    user_settings = loaded
                    logger.info(f"Loaded settings for user {user_id}: vector_provider={user_settings.get('vector_provider')}, embedding_provider={user_settings.get('embedding_provider')}")
                else:
                    logger.warning(f"No settings found for user {user_id}, using defaults")
            # Always inject user_id so ChromaDB uses per-user storage path
            user_settings["user_id"] = user_id
            self.embedding_service = EmbeddingService(effective_settings=user_settings)
            logger.info(f"✅ EmbeddingService initialised for user: {user_id}")
        except Exception as exc:
            logger.error(f"Failed to initialise EmbeddingService: {exc}")
            raise

    # ------------------------------------------------------------------
    # Async helpers
    # ------------------------------------------------------------------

    def _run_in_new_loop(self, coro):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    def _run_async_task(self, coro):
        """Run an async coroutine from sync context in a fresh thread/loop."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self._run_in_new_loop, coro)
            return future.result()

    def _get_embedding_sync(self, text: str) -> List[float]:
        return self._run_async_task(self.embedding_service.generate_embedding(text))

    # ------------------------------------------------------------------
    # SQLite helpers
    # ------------------------------------------------------------------

    def _user_db_path(self, user_id: str) -> str:
        path = os.path.join(BASE_DATA_DIR, user_id, "sql_data", "chat_thread_processing.db")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path

    def ensure_user_db(self, user_id: str):
        """Create per-user SQLite DB with required tables if they don't exist."""
        conn = sqlite3.connect(self._user_db_path(user_id))
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                thread_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                processed_status TEXT DEFAULT 'completed',
                chroma_collection TEXT,
                UNIQUE(user_id, thread_id, message_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attachment_processing (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                thread_id TEXT NOT NULL,
                message_id TEXT,
                attachment_id TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                processed_status TEXT DEFAULT 'pending',
                processed_timestamp DATETIME,
                chroma_collection TEXT,
                metadata TEXT,
                UNIQUE(user_id, thread_id, attachment_id)
            )
        """)
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # ChromaDB helpers
    # ------------------------------------------------------------------

    def get_user_chroma_client(self, user_id: str):
        user_vector_path = os.path.join(BASE_DATA_DIR, user_id, "vector_db")
        os.makedirs(user_vector_path, exist_ok=True)
        chroma_path = os.path.join(user_vector_path, f"cdb_{user_id}")
        os.makedirs(chroma_path, exist_ok=True)
        return chromadb.PersistentClient(path=chroma_path)

    def get_user_collection(self, user_id: str, collection_name: str = "email_threads"):
        client = self.get_user_chroma_client(user_id)
        return client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )


# ===========================================================================
# 1. CheckAndStoreEmailPipeline
# ===========================================================================

class CheckAndStoreEmailPipeline(_BaseStorePipeline):
    """
    Takes preprocessed messages and stores them in the vector DB.

    Usage
    -----
    pipeline = CheckAndStoreEmailPipeline(user_id="user@example.com")
    result = pipeline.run(user_id, thread_id, messages)

    `messages` is a list of dicts with at least:
        message_id, subject, body, from, to, timestamp
    """
    
    def __init__(self, user_id: Optional[str] = None):
        super().__init__(user_id)

    # ------------------------------------------------------------------
    # Check helpers
    # ------------------------------------------------------------------

    def is_message_processed(self, user_id: str, thread_id: str, message_id: str) -> bool:
        """Return True if this (user_id, thread_id, message_id) is already stored."""
        self.ensure_user_db(user_id)
        conn = sqlite3.connect(self._user_db_path(user_id))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT processed_status FROM email_embeddings "
            "WHERE user_id=? AND thread_id=? AND message_id=?",
            (user_id, thread_id, message_id),
        )
        row = cursor.fetchone()
        conn.close()
        return row is not None and row[0] == "completed"

    def mark_message_processed(self, user_id: str, thread_id: str, message_id: str):
        self.ensure_user_db(user_id)
        conn = sqlite3.connect(self._user_db_path(user_id))
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO email_embeddings
                (user_id, thread_id, message_id, processed_status, chroma_collection)
            VALUES (?, ?, ?, 'completed', 'email_threads')
            """,
            (user_id, thread_id, message_id),
        )
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # Core store logic (async versions)
    # ------------------------------------------------------------------

    async def store_email_to_vector_db_async(self, user_id: str, thread_id: str, message_data: Dict):
        """Async: Embed a single preprocessed message and persist in ChromaDB."""
        message_id = message_data.get("message_id", "unknown")
        logger.info(f"  ➕ Embedding message {message_id}")

        subject = message_data.get("subject", "")
        body = message_data.get("body", "")
        timestamp = message_data.get("timestamp", "")
        from_email = message_data.get("from", "")

        to_email = message_data.get("to", "")
        if isinstance(to_email, list):
            to_email = ", ".join(to_email)
        elif not isinstance(to_email, str):
            to_email = str(to_email)

        text_to_embed = f"Subject: {subject}\n\nBody: {body}".strip()

        if not text_to_embed or text_to_embed == "Subject: \n\nBody: ":
            logger.warning(f"  ⚠️  Empty content for message {message_id}, skipping")
            return

        metadata = {
            "thread_id": thread_id,
            "message_id": message_id,
            "timestamp": timestamp,
            "type": "email_data",
            "subject": subject,
            "from": from_email,
            "to": to_email,
            "document": text_to_embed,
        }

        embedding = self._get_embedding_sync(text_to_embed)
        doc_id = f"{user_id}_{thread_id}_{message_id}"
        namespace = sanitize_namespace(f"{user_id}_email_threads")

        await self.embedding_service.store_embedding(
            embedding=embedding,
            metadata=metadata,
            namespace=namespace,
            vector_id=doc_id,
        )

        self.mark_message_processed(user_id, thread_id, message_id)
        logger.info(f"  ✅ Message {message_id} stored in vector DB")

    # ------------------------------------------------------------------
    # Entry point (async)
    # ------------------------------------------------------------------

    async def run(self, user_id: str, thread_id: str, messages: List[Dict]) -> Dict:
        """
        Async: Check each message and store unprocessed ones.

        Parameters
        ----------
        user_id   : user identifier
        thread_id : thread identifier
        messages  : list of preprocessed message dicts

        Returns
        -------
        dict with keys: total, already_stored, newly_stored, errors
        """
        logger.info(
            f"🚀 CheckAndStoreEmailPipeline.run | user={user_id} thread={thread_id} msgs={len(messages)}"
        )
        result = {"total": len(messages), "already_stored": 0, "newly_stored": 0, "errors": []}

        for msg in messages:
            message_id = msg.get("message_id", "unknown")
            try:
                if self.is_message_processed(user_id, thread_id, message_id):
                    logger.info(f"  ⏭️  Message {message_id} already stored, skipping")
                    result["already_stored"] += 1
                    continue

                await self.store_email_to_vector_db_async(user_id, thread_id, msg)
                result["newly_stored"] += 1

            except Exception as exc:
                err = f"message {message_id}: {exc}"
                logger.error(f"  ✗ {err}")
                logger.error(traceback.format_exc())
                result["errors"].append(err)

        logger.info(f"✅ CheckAndStoreEmailPipeline done: {result}")
        return result


# ===========================================================================
# 2. CheckAndStoreAttachmentsPipeline
# ===========================================================================

class CheckAndStoreAttachmentsPipeline(_BaseStorePipeline):
    """
    Reads attachments already saved on disk and stores their embeddings.

    Usage
    -----
    pipeline = CheckAndStoreAttachmentsPipeline(user_id="user@example.com")
    result = pipeline.run(user_id, thread_id)
    """
    
    def __init__(self, user_id: Optional[str] = None):
        super().__init__(user_id)

    # ------------------------------------------------------------------
    # Check helpers
    # ------------------------------------------------------------------

    def is_attachment_processed(self, user_id: str, thread_id: str, attachment_id: str) -> bool:
        """Return True if this attachment is already embedded and stored."""
        self.ensure_user_db(user_id)
        conn = sqlite3.connect(self._user_db_path(user_id))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT processed_status FROM attachment_processing "
            "WHERE user_id=? AND thread_id=? AND attachment_id=?",
            (user_id, thread_id, attachment_id),
        )
        row = cursor.fetchone()
        conn.close()
        return row is not None and row[0] == "completed"

    def mark_attachment_processed(
        self, user_id: str, thread_id: str, message_id: str, attachment_id: str
    ):
        self.ensure_user_db(user_id)
        conn = sqlite3.connect(self._user_db_path(user_id))
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO attachment_processing
                (user_id, thread_id, message_id, attachment_id,
                 processed_status, processed_timestamp)
            VALUES (?, ?, ?, ?, 'completed', CURRENT_TIMESTAMP)
            """,
            (user_id, thread_id, message_id, attachment_id),
        )
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # Discover attachments on disk
    # ------------------------------------------------------------------

    def get_thread_attachments(self, user_id: str, thread_id: str) -> List[Dict]:
        """
        Return list of attachment dicts from:
          data/{user_id}/store_attachments/{thread_id}/
        Each dict has: filename, path, attachment_id, message_id
        """
        thread_path = os.path.join(BASE_DATA_DIR, user_id, "store_attachments", thread_id)
        if not os.path.exists(thread_path):
            logger.warning(f"No attachments directory for thread {thread_id}: {thread_path}")
            return []

        attachments: List[Dict] = []

        # Primary: read *_metadata.json sidecar files
        for fname in os.listdir(thread_path):
            if fname.endswith("_metadata.json"):
                meta_path = os.path.join(thread_path, fname)
                try:
                    with open(meta_path, "r") as f:
                        meta = json.load(f)
                    for att in meta.get("attachments", []):
                        if "error" not in att:
                            attachments.append(
                                {
                                    "filename": att.get("filename"),
                                    "path": att.get("filepath") or att.get("path"),
                                    "attachment_id": att.get("filename"),
                                    "message_id": meta.get("message_id", thread_id),
                                }
                            )
                except Exception as exc:
                    logger.error(f"Error reading metadata {meta_path}: {exc}")

        # Fallback: raw files (no metadata)
        if not attachments:
            for fname in os.listdir(thread_path):
                if not fname.endswith("_metadata.json"):
                    attachments.append(
                        {
                            "filename": fname,
                            "path": os.path.join(thread_path, fname),
                            "attachment_id": fname,
                            "message_id": thread_id,
                        }
                    )

        return attachments

    # ------------------------------------------------------------------
    # Core store logic (async versions)
    # ------------------------------------------------------------------

    async def store_attachment_to_vector_db_async(
        self,
        user_id: str,
        thread_id: str,
        message_id: str,
        attachment_path: str,
        attachment_id: str,
    ):
        """Async: Extract text from an attachment file, embed each chunk, and store."""
        logger.info(f"  ➕ Processing attachment {attachment_id}")

        documents = SimpleDirectoryReader(
            input_files=[attachment_path],
            file_extractor=FILE_EXTRACTOR,
        ).load_data()

        if not documents:
            logger.warning(f"  ⚠️  No content extracted from {attachment_path}")
            return

        namespace = sanitize_namespace(f"{user_id}_email_threads")
        chunk_count = 0

        for idx, doc in enumerate(documents):
            text = doc.text.strip() if doc.text else ""
            if not text:
                continue

            metadata = {
                "message_id": message_id,
                "thread_id": thread_id,
                "attachment_id": attachment_id,
                "filename": os.path.basename(attachment_path),
                "chunk_index": str(idx),
                "type": "attachment_data",
                "document": text,
            }

            try:
                embedding = self._get_embedding_sync(text)
                doc_id = f"{user_id}_{thread_id}_{attachment_id}_{idx}"

                await self.embedding_service.store_embedding(
                    embedding=embedding,
                    metadata=metadata,
                    namespace=namespace,
                    vector_id=doc_id,
                )
                chunk_count += 1
                logger.info(f"  ✓ Stored chunk {idx} (id: {doc_id})")

            except Exception as exc:
                logger.error(f"  ✗ Failed to embed chunk {idx}: {exc}")
                raise

        if chunk_count == 0:
            logger.warning(f"  ⚠️  No chunks stored for {attachment_id}")
            return

        self.mark_attachment_processed(user_id, thread_id, message_id, attachment_id)
        logger.info(f"  ✅ Attachment {attachment_id}: {chunk_count} chunks stored")

    # ------------------------------------------------------------------
    # Entry point (async)
    # ------------------------------------------------------------------

    async def run(self, user_id: str, thread_id: str) -> Dict:
        """
        Async: Discover all attachments for the thread, check each against the DB,
        embed and store the unprocessed ones.

        Returns
        -------
        dict with keys: found, already_stored, newly_stored, errors
        """
        logger.info(
            f"🚀 CheckAndStoreAttachmentsPipeline.run | user={user_id} thread={thread_id}"
        )
        result = {"found": 0, "already_stored": 0, "newly_stored": 0, "errors": []}

        attachments = self.get_thread_attachments(user_id, thread_id)
        result["found"] = len(attachments)

        for att in attachments:
            attachment_id = att.get("attachment_id") or att.get("filename", "unknown")
            attachment_path = att.get("path", "")
            message_id = att.get("message_id", thread_id)

            if not attachment_path or not os.path.exists(attachment_path):
                logger.warning(f"  ⚠️  File not found: {attachment_path}")
                result["errors"].append(f"file not found: {attachment_path}")
                continue

            try:
                if self.is_attachment_processed(user_id, thread_id, attachment_id):
                    logger.info(f"  ⏭️  Attachment {attachment_id} already stored, skipping")
                    result["already_stored"] += 1
                    continue

                await self.store_attachment_to_vector_db_async(
                    user_id, thread_id, message_id, attachment_path, attachment_id
                )
                result["newly_stored"] += 1

            except Exception as exc:
                err = f"attachment {attachment_id}: {exc}"
                logger.error(f"  ✗ {err}")
                logger.error(traceback.format_exc())
                result["errors"].append(err)

        logger.info(f"✅ CheckAndStoreAttachmentsPipeline done: {result}")
        return result
