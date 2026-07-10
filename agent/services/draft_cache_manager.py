"""
Draft Cache Manager
Handles storage and retrieval of generated drafts from SQLite database
Allows draft reuse if the same thread/message is being drafted again
"""
import os
import sqlite3
import json
import logging
from typing import Dict, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Base data directory - point to backend/data (not agent/data)
BASE_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),  # openmailbot/
    "backend",
    "data"
)


class DraftCacheManager:
    """
    Manages draft caching in SQLite per user.
    
    Database: data/{user_id}/sql_data/draft_cache.db
    Table: draft_cache
        - user_id: Email address (user identifier)
        - thread_id: Gmail thread ID (or canonical Message-ID)
        - last_message_id: Last message in the thread (for cache validation)
        - draft_content: The generated draft email text
        - processing_info: JSON with attachments_found, tone_profile, etc.
        - created_at: Timestamp when draft was generated
        - updated_at: Timestamp when draft was last updated
    """
    
    def __init__(self, user_id: str):
        """
        Initialize the draft cache manager for a user.
        
        Args:
            user_id: User identifier (email address)
        """
        self.user_id = user_id
        self.db_path = self._get_db_path(user_id)
        self._ensure_db_initialized()
    
    @staticmethod
    def _get_db_path(user_id: str) -> str:
        """
        Get the SQLite database path for a user.
        
        Args:
            user_id: User identifier (email address)
            
        Returns:
            Path to user's draft_cache.db file
        """
        user_data_dir = os.path.join(BASE_DATA_DIR, user_id, "sql_data")
        os.makedirs(user_data_dir, exist_ok=True)
        return os.path.join(user_data_dir, "draft_cache.db")
    
    def _ensure_db_initialized(self):
        """
        Ensure the SQLite database and table exist.
        Create the draft_cache table if it doesn't exist.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS draft_cache (
                    user_id TEXT NOT NULL,
                    thread_id TEXT NOT NULL,
                    last_message_id TEXT NOT NULL,
                    draft_content TEXT NOT NULL,
                    processing_info TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, thread_id)
                )
            """)
            
            # Create index on thread_id for faster lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_draft_cache_thread
                ON draft_cache(user_id, thread_id)
            """)
            
            conn.commit()
            conn.close()
            logger.info(f"✅ Draft cache database initialized: {self.db_path}")
        except Exception as e:
            logger.error(f"❌ Failed to initialize draft cache database: {e}")
            raise
    
    def save_draft(
        self,
        thread_id: str,
        last_message_id: str,
        draft_content: str,
        processing_info: Dict[str, Any] = None,
    ) -> bool:
        """
        Save a generated draft to the cache.
        
        Args:
            thread_id: Gmail thread ID (or canonical Message-ID)
            last_message_id: The last message ID in the thread
            draft_content: The generated draft email text
            processing_info: JSON data with attachments_found, tone_profile, etc.
            
        Returns:
            True if save successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            now = datetime.utcnow().isoformat()
            processing_info_json = json.dumps(processing_info or {})
            
            # Insert or replace (upsert)
            cursor.execute("""
                INSERT OR REPLACE INTO draft_cache 
                (user_id, thread_id, last_message_id, draft_content, processing_info, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                self.user_id,
                thread_id,
                last_message_id,
                draft_content,
                processing_info_json,
                now,
                now
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Draft cached for thread {thread_id}")
            logger.info(f"   User: {self.user_id}")
            logger.info(f"   Message ID: {last_message_id}")
            logger.info(f"   Draft size: {len(draft_content)} chars")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to save draft to cache: {e}")
            return False
    
    def get_draft(self, thread_id: str, last_message_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a cached draft if it exists and matches the last_message_id.
        
        Args:
            thread_id: Gmail thread ID (or canonical Message-ID)
            last_message_id: The last message ID in the thread
            
        Returns:
            Dict with draft_content and processing_info if found and valid, None otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT draft_content, processing_info, last_message_id
                FROM draft_cache
                WHERE user_id = ? AND thread_id = ?
            """, (self.user_id, thread_id))
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                logger.info(f"ℹ️  No cached draft for thread {thread_id}")
                return None
            
            draft_content, processing_info_json, cached_message_id = row
            
            # Validate that the last_message_id matches
            if cached_message_id != last_message_id:
                logger.info(f"⚠️  Cache mismatch for thread {thread_id}")
                logger.info(f"   Cached message ID: {cached_message_id}")
                logger.info(f"   Current message ID: {last_message_id}")
                logger.info(f"   Cache is stale — will regenerate draft")
                return None
            
            # Cache hit!
            processing_info = json.loads(processing_info_json) if processing_info_json else {}
            logger.info(f"✅ Draft cache HIT for thread {thread_id}")
            logger.info(f"   User: {self.user_id}")
            logger.info(f"   Message ID: {last_message_id}")
            logger.info(f"   Draft size: {len(draft_content)} chars")
            
            return {
                "draft_content": draft_content,
                "processing_info": processing_info,
                "cached": True
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to retrieve draft from cache: {e}")
            return None
    
    def delete_draft(self, thread_id: str) -> bool:
        """
        Delete a cached draft.
        
        Args:
            thread_id: Gmail thread ID (or canonical Message-ID)
            
        Returns:
            True if delete successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM draft_cache
                WHERE user_id = ? AND thread_id = ?
            """, (self.user_id, thread_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Deleted cached draft for thread {thread_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to delete draft from cache: {e}")
            return False
    
    def invalidate_stale_cache(self, thread_id: str, last_message_id: str) -> bool:
        """
        Check if cached draft exists for this thread_id, and if the last_message_id 
        doesn't match, delete the stale cache entry.
        
        Args:
            thread_id: Gmail thread ID (or canonical Message-ID)
            last_message_id: Current last message ID in the thread
            
        Returns:
            True if stale cache was deleted, False if cache is valid or not found
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check if cache exists for this thread
            cursor.execute("""
                SELECT last_message_id FROM draft_cache
                WHERE user_id = ? AND thread_id = ?
            """, (self.user_id, thread_id))
            
            row = cursor.fetchone()
            
            if not row:
                # No cache found - nothing to invalidate
                conn.close()
                return False
            
            cached_message_id = row[0]
            
            # Check if message IDs don't match
            if cached_message_id != last_message_id:
                # Stale cache detected - delete it
                cursor.execute("""
                    DELETE FROM draft_cache
                    WHERE user_id = ? AND thread_id = ?
                """, (self.user_id, thread_id))
                
                conn.commit()
                conn.close()
                
                logger.warning(f"🗑️  [Stale Cache] Deleted cached draft for thread {thread_id}")
                logger.warning(f"   Cached message ID: {cached_message_id}")
                logger.warning(f"   Current message ID: {last_message_id}")
                logger.warning(f"   Reason: Last message in thread has changed")
                return True
            
            # Cache is still valid
            conn.close()
            return False
            
        except Exception as e:
            logger.error(f"❌ Failed to validate cache staleness: {e}")
            return False
    
    def clear_all_drafts(self) -> bool:
        """
        Delete all cached drafts for this user.
        
        Returns:
            True if clear successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM draft_cache
                WHERE user_id = ?
            """, (self.user_id,))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Cleared all cached drafts for user {self.user_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to clear draft cache: {e}")
            return False
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics for this user.
        
        Returns:
            Dict with cache_size, total_threads, created_at, updated_at
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT COUNT(*) as total, 
                       SUM(LENGTH(draft_content)) as size_bytes,
                       MIN(created_at) as created_at,
                       MAX(updated_at) as updated_at
                FROM draft_cache
                WHERE user_id = ?
            """, (self.user_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return {
                    "total_threads": 0,
                    "cache_size_mb": 0,
                    "created_at": None,
                    "updated_at": None
                }
            
            total, size_bytes, created_at, updated_at = row
            size_mb = (size_bytes or 0) / (1024 * 1024)
            
            return {
                "total_threads": total or 0,
                "cache_size_mb": round(size_mb, 2),
                "created_at": created_at,
                "updated_at": updated_at
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get cache stats: {e}")
            return {}
