"""
Encryption Service
Handles public-key encryption for client-side settings encryption.
Uses libsodium (NaCl) for asymmetric encryption.

Architecture:
- Backend generates per-user Ed25519 keypairs on first settings save
- Private/public keys stored in SQLite system database (agent/data/system/keys.db) per user
- Public key exposed via /api/public-key?user_id=<email> endpoint
- Add-ons encrypt settings client-side before sending
- Backend decrypts with user's private key using SealedBox.decrypt()

Per-User Key Management:
- Each user gets their own Ed25519 keypair on first settings submission
- Latest key is always stored (old keys are replaced)
- Public key endpoint returns the current key for that user
- Private key stays on backend, never shared

Key Features:
- Automatic keypair generation per user on first use
- Persistent per-user storage in SQLite
- Replaces old keys (latest always wins to avoid key mismatch)
- Add-on always fetches fresh public key before saving settings
"""

import os
import sys
import json
import base64
import logging
import sqlite3
from typing import Tuple, Optional, Dict, Any
from datetime import datetime

try:
    from nacl.public import PrivateKey, PublicKey, SealedBox
    from nacl.utils import random
except ImportError as e:
    raise ImportError(
        f"PyNaCl is required but not installed: {e}\n"
        "Please install it with: pip install PyNaCl>=1.5.0"
    )

logger = logging.getLogger(__name__)



class EncryptionService:
    """
    Handles per-user libsodium-based encryption for client-server communication.
    
    Per-user encryption workflow:
    1. Add-on calls GET /api/public-key?user_id=<email> to fetch user's public key
    2. If user has no key yet, backend generates one and stores in SQLite
    3. Add-on encrypts settings with public key using box_seal()
    4. Add-on sends encrypted payload to POST /api/settings/encrypted with user_id
    5. Backend loads user's private key from SQLite
    6. Backend decrypts with private key using SealedBox.decrypt()
    7. Backend encrypts with Fernet and saves to user's settings database
    
    SQLite storage (agent/data/system/keys.db):
    - Table: encryption_keys(user_id, private_key, public_key, created_at, version)
    - One row per user (latest key only — old keys replaced automatically)
    """
    
    # System database path (shared across all users)
    SYSTEM_DB_PATH = None  # Will be set dynamically

    def __init__(self):
        """Initialize encryption service."""
        # Set up system DB path if not already set
        if EncryptionService.SYSTEM_DB_PATH is None:
            agent_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            EncryptionService.SYSTEM_DB_PATH = os.path.join(agent_root, "data", "system", "keys.db")
        
        self._init_db()

    def _get_system_db_path(self) -> str:
        """Get system database path (creates directory if needed)."""
        db_path = EncryptionService.SYSTEM_DB_PATH
        db_dir = os.path.dirname(db_path)
        
        # Create directory if it doesn't exist
        if not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
                logger.info(f"📁 Created system database directory: {db_dir}")
            except Exception as e:
                logger.error(f"❌ Failed to create directory {db_dir}: {e}")
                raise
        
        return db_path

    def _init_db(self) -> None:
        """Initialize system database and create encryption_keys table if needed."""
        db_path = self._get_system_db_path()
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Create encryption_keys table for per-user keys
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS encryption_keys (
                    user_id TEXT PRIMARY KEY,
                    private_key TEXT NOT NULL,
                    public_key TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    version INTEGER DEFAULT 1
                )
            """)
            
            conn.commit()
            conn.close()
            logger.debug(f"✅ System database initialized: {db_path}")
        except Exception as e:
            logger.error(f"❌ Failed to initialize system database: {e}")
            raise

    def get_or_create_user_keys(self, user_id: str) -> Tuple[str, str]:
        """
        Get or create encryption keypair for a user.
        If user has no key, generate new one and replace any old key.
        
        Args:
            user_id: User email or unique identifier
            
        Returns:
            Tuple of (private_key_b64, public_key_b64)
        """
        db_path = self._get_system_db_path()
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check if user has existing key
            cursor.execute("""
                SELECT private_key, public_key FROM encryption_keys 
                WHERE user_id = ?
            """, (user_id,))
            
            row = cursor.fetchone()
            
            if row:
                logger.debug(f"✅ Found existing key for user: {user_id}")
                conn.close()
                return row[0], row[1]
            
            # Generate new keypair for this user
            logger.info(f"🔐 Generating new encryption keypair for user: {user_id}")
            private_key = PrivateKey.generate()
            public_key = private_key.public_key
            
            private_key_b64 = base64.b64encode(bytes(private_key)).decode()
            public_key_b64 = base64.b64encode(bytes(public_key)).decode()
            
            # Insert new keypair (replace old one if exists for this user)
            cursor.execute("""
                INSERT OR REPLACE INTO encryption_keys 
                (user_id, private_key, public_key, created_at, updated_at, version)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)
            """, (user_id, private_key_b64, public_key_b64))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Created and saved new encryption key for user: {user_id}")
            return private_key_b64, public_key_b64
            
        except Exception as e:
            logger.error(f"❌ Failed to get/create user keys: {e}")
            raise

    def get_user_public_key_b64(self, user_id: str) -> str:
        """
        Get user's public key as base64 string.
        Creates new keypair if user doesn't have one yet.
        
        Args:
            user_id: User email or unique identifier
            
        Returns:
            Base64-encoded public key
        """
        _, public_key_b64 = self.get_or_create_user_keys(user_id)
        return public_key_b64

    def get_user_public_key_dict(self, user_id: str) -> Dict[str, Any]:
        """
        Get user's public key metadata for /api/public-key?user_id endpoint.
        
        Args:
            user_id: User email or unique identifier
            
        Returns:
            Dict with public_key, algorithm, key_version, etc.
        """
        public_key_b64 = self.get_user_public_key_b64(user_id)
        
        # Print for logging (helpful for debugging)
        logger.info(f"📤 Providing public key to user: {user_id}")
        
        return {
            "user_id": user_id,
            "public_key": public_key_b64,
            "algorithm": "libsodium/box_seal",
            "key_version": 1,
            "format": "base64"
        }

    def decrypt_settings_for_user(self, user_id: str, encrypted_payload_b64: str) -> Dict[str, Any]:
        """
        Decrypt client-encrypted settings using user's private key.
        
        Args:
            user_id: User email or unique identifier
            encrypted_payload_b64: Base64-encoded encrypted payload from client
            
        Returns:
            Decrypted settings as dictionary
            
        Raises:
            ValueError: If decryption fails
        """
        try:
            # Load user's private key from database
            db_path = self._get_system_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT private_key FROM encryption_keys 
                WHERE user_id = ?
            """, (user_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                raise ValueError(f"No encryption key found for user: {user_id}")
            
            private_key_b64 = row[0]
            private_key_bytes = base64.b64decode(private_key_b64)
            private_key = PrivateKey(private_key_bytes)
            
            # Decode encrypted payload from base64
            try:
                encrypted_bytes = base64.b64decode(encrypted_payload_b64)
            except Exception as e:
                logger.error(f"❌ Invalid base64 encoding for user {user_id}: {e}")
                raise ValueError(f"Payload is not valid base64: {str(e)}")
            
            logger.debug(f"📦 Encrypted payload size: {len(encrypted_bytes)} bytes for user {user_id}")
            
            # Attempt decryption using SealedBox
            try:
                box = SealedBox(private_key)
                plaintext_bytes = box.decrypt(encrypted_bytes)
                logger.debug(f"✅ SealedBox.decrypt() succeeded for user {user_id}")
            except Exception as decrypt_err:
                # Provide diagnostic information
                logger.warning(f"⚠️  SealedBox.decrypt() failed for user {user_id}: {decrypt_err}")
                logger.warning(f"   Payload size: {len(encrypted_bytes)} bytes")
                logger.warning(f"   This typically indicates a KEY MISMATCH")
                logger.warning(f"   Hint: Ensure add-on fetched the latest public key")
                
                # Check if payload might be plaintext (fallback)
                try:
                    plaintext_str = encrypted_bytes.decode('utf-8')
                    if plaintext_str.startswith('{') and plaintext_str.endswith('}'):
                        logger.warning(f"📝 Payload appears to be plaintext JSON for user {user_id}")
                        logger.info("✅ Attempting to parse as plaintext fallback...")
                        settings = json.loads(plaintext_str)
                        logger.info("✅ Successfully parsed plaintext fallback")
                        return settings
                except (UnicodeDecodeError, json.JSONDecodeError):
                    pass
                
                # Re-raise with user context
                raise ValueError(
                    f"Decryption failed for user {user_id} (likely key mismatch): {str(decrypt_err)}\n"
                    f"This occurs when:\n"
                    f"  1. Add-on has cached old public key\n"
                    f"  2. Backend keys were regenerated\n"
                    f"  3. Wrong public key was used for encryption\n"
                    f"Workaround: Fetch fresh public key before saving"
                )
            
            # Decode to UTF-8 and parse JSON
            plaintext_str = plaintext_bytes.decode('utf-8')
            settings = json.loads(plaintext_str)
            
            logger.info(f"✅ Settings decrypted successfully for user {user_id}")
            logger.debug(f"📋 Decrypted settings keys: {list(settings.keys())}")
            
            return settings
        
        except ValueError as e:
            logger.error(f"❌ Decryption failed for user {user_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected error during decryption for user {user_id}: {e}")
            raise ValueError(f"Failed to decrypt settings: {str(e)}")
    
    # Legacy methods for backward compatibility (no longer used, but kept for transition)
    def get_public_key_b64(self) -> str:
        """Deprecated: Use get_user_public_key_b64(user_id) instead."""
        raise NotImplementedError("Use get_user_public_key_b64(user_id) for per-user keys")

    def get_public_key_dict(self) -> Dict[str, Any]:
        """Deprecated: Use get_user_public_key_dict(user_id) instead."""
        raise NotImplementedError("Use get_user_public_key_dict(user_id) for per-user keys")

    def decrypt_settings(self, encrypted_payload_b64: str) -> Dict[str, Any]:
        """Deprecated: Use decrypt_settings_for_user(user_id, encrypted_payload_b64) instead."""
        raise NotImplementedError("Use decrypt_settings_for_user(user_id, encrypted_payload_b64) for per-user keys")


# Global singleton instance
_encryption_service: Optional[EncryptionService] = None


def get_encryption_service() -> EncryptionService:
    """Get or create the global encryption service singleton."""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service


def reset_encryption_service() -> None:
    """Reset the encryption service (mainly for testing)."""
    global _encryption_service
    _encryption_service = None
