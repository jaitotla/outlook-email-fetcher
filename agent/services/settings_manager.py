"""
Settings Manager
Handles encrypted storage and retrieval of user settings from SQLite database
Replaces config_settings.json file-based storage
"""
import os
import sqlite3
import json
import logging
from typing import Dict, Optional, Any
import base64

# Import cryptography components
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
except ImportError as e:
    raise ImportError(
        f"cryptography library is required but not installed: {e}\n"
        "Please install it with: pip install cryptography>=41.0.0"
    )

logger = logging.getLogger(__name__)

# Base data directory under the agent package: agent/data/{user_id}/...
# Use abspath so the path is always absolute regardless of working directory
BASE_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

# Encryption key - in production, this should come from environment variable
# For now, using a default that should be changed
ENCRYPTION_KEY_SALT = b"openmailbot_settings_salt_v1"  # Should be stored securely


def _get_encryption_key(user_id: str = "default") -> bytes:
    """
    Generate encryption key from user_id and salt.
    In production, this should use environment variables and secure key management.
    """
    # Create a key from user_id + salt
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=ENCRYPTION_KEY_SALT,
        iterations=100000,
        backend=default_backend()
    )
    key = base64.urlsafe_b64encode(kdf.derive(user_id.encode()))
    return key


def encrypt_settings(settings: Dict[str, Any], user_id: str = "default") -> str:
    """
    Encrypt settings dictionary to string format for storage.
    
    Args:
        settings: Dictionary of settings to encrypt
        user_id: User ID for key derivation
        
    Returns:
        Encrypted settings as base64 string
    """
    try:
        key = _get_encryption_key(user_id)
        cipher = Fernet(key)
        
        # Convert settings dict to JSON string
        settings_json = json.dumps(settings)
        
        # Encrypt the JSON
        encrypted = cipher.encrypt(settings_json.encode())
        
        # Return as base64 string for storage
        return base64.b64encode(encrypted).decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to encrypt settings: {e}")
        raise


def decrypt_settings(encrypted_data: str, user_id: str = "default") -> Dict[str, Any]:
    """
    Decrypt settings from encrypted string format.
    
    Args:
        encrypted_data: Encrypted settings as base64 string
        user_id: User ID for key derivation
        
    Returns:
        Decrypted settings dictionary
    """
    try:
        key = _get_encryption_key(user_id)
        cipher = Fernet(key)
        
        # Decode from base64
        encrypted_bytes = base64.b64decode(encrypted_data)
        
        # Decrypt
        decrypted = cipher.decrypt(encrypted_bytes)
        
        # Parse JSON
        settings = json.loads(decrypted.decode('utf-8'))
        
        return settings
    except Exception as e:
        logger.error(f"Failed to decrypt settings: {e}")
        raise


class SettingsManager:
    """Manager for encrypted user settings storage and retrieval"""
    
    def __init__(self, user_id: str = None):
        """
        Initialize settings manager.
        
        Args:
            user_id: Optional user ID, can be provided on each method call too
        """
        self.user_id = user_id
        self.base_data_dir = BASE_DATA_DIR
    
    def _ensure_db_exists(self, user_id: str):
        """Ensure settings table exists in user's database"""
        user_db = os.path.join(self.base_data_dir, user_id, "sql_data", "chat_thread_processing.db")
        os.makedirs(os.path.dirname(user_db), exist_ok=True)
        
        conn = sqlite3.connect(user_db)
        cursor = conn.cursor()
        
        # Create user_settings table if not exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                setting_key TEXT NOT NULL,
                encrypted_value TEXT NOT NULL,
                setting_type TEXT DEFAULT 'general',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, setting_key, setting_type)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_settings(self, settings: Dict[str, Any], user_id: str = None, 
                     setting_type: str = "general") -> bool:
        """
        Save encrypted user settings to database.
        
        Args:
            settings: Dictionary of settings to save
            user_id: User ID (uses self.user_id if not provided)
            setting_type: Type of setting (default: "general", can be "llm", "embedding", etc.)
            
        Returns:
            True if successful, False otherwise
        """
        user_id = user_id or self.user_id
        if not user_id:
            logger.error("user_id required for save_settings")
            return False
        
        try:
            self._ensure_db_exists(user_id)
            user_db = os.path.join(self.base_data_dir, user_id, "sql_data", "chat_thread_processing.db")
            
            conn = sqlite3.connect(user_db)
            cursor = conn.cursor()
            
            # Encrypt the entire settings dict
            encrypted_data = encrypt_settings(settings, user_id)
            
            # Store with a composite key (e.g., "all_settings" for general, or specific keys)
            cursor.execute('''
                INSERT OR REPLACE INTO user_settings 
                (user_id, setting_key, encrypted_value, setting_type, updated_timestamp)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (user_id, "all_settings", encrypted_data, setting_type))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Saved settings for user {user_id} (type: {setting_type})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            return False
    
    def get_settings(self, user_id: str = None, 
                    setting_type: str = "general") -> Optional[Dict[str, Any]]:
        """
        Retrieve and decrypt user settings from database.
        
        Args:
            user_id: User ID (uses self.user_id if not provided)
            setting_type: Type of setting to retrieve (default: "general")
            
        Returns:
            Decrypted settings dictionary, or None if not found
        """
        user_id = user_id or self.user_id
        if not user_id:
            logger.error("user_id required for get_settings")
            return None
        
        try:
            user_db = os.path.join(self.base_data_dir, user_id, "sql_data", "chat_thread_processing.db")
            logger.info(f"DEBUG get_settings looking for DB at: {os.path.abspath(user_db)}")
            
            # If DB doesn't exist yet, ensure it gets created (first run after wipe/restart)
            if not os.path.exists(user_db):
                logger.warning(f"Database not found for user {user_id} at {os.path.abspath(user_db)}")
                return None
            
            conn = sqlite3.connect(user_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT encrypted_value FROM user_settings
                WHERE user_id = ? AND setting_key = 'all_settings' AND setting_type = ?
                ORDER BY updated_timestamp DESC LIMIT 1
            ''', (user_id, setting_type))
            
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                logger.warning(f"No settings found for user {user_id} (type: {setting_type})")
                return None
            
            encrypted_data = result[0]
            settings = decrypt_settings(encrypted_data, user_id)
            
            logger.info(f"Retrieved settings for user {user_id} (type: {setting_type})")
            return settings
            
        except Exception as e:
            logger.error(f"Failed to retrieve settings: {e}")
            return None
    
    def get_setting_value(self, key: str, user_id: str = None, 
                         setting_type: str = "general", default: Any = None) -> Any:
        """
        Get a specific setting value from the user's settings.
        
        Args:
            key: Setting key to retrieve
            user_id: User ID (uses self.user_id if not provided)
            setting_type: Type of setting (default: "general")
            default: Default value if setting not found
            
        Returns:
            Setting value or default if not found
        """
        settings = self.get_settings(user_id, setting_type)
        if settings and isinstance(settings, dict):
            return settings.get(key, default)
        return default
    
    def update_setting(self, key: str, value: Any, user_id: str = None,
                      setting_type: str = "general") -> bool:
        """
        Update a single setting value.
        
        Args:
            key: Setting key to update
            value: New value for the setting
            user_id: User ID (uses self.user_id if not provided)
            setting_type: Type of setting (default: "general")
            
        Returns:
            True if successful, False otherwise
        """
        user_id = user_id or self.user_id
        if not user_id:
            logger.error("user_id required for update_setting")
            return False
        
        try:
            # Get current settings
            settings = self.get_settings(user_id, setting_type) or {}
            
            # Update the specific key
            settings[key] = value
            
            # Save back
            return self.save_settings(settings, user_id, setting_type)
            
        except Exception as e:
            logger.error(f"Failed to update setting {key}: {e}")
            return False
    
    def delete_settings(self, user_id: str = None, 
                       setting_type: str = "general") -> bool:
        """
        Delete all settings for a user.
        
        Args:
            user_id: User ID (uses self.user_id if not provided)
            setting_type: Type of setting to delete
            
        Returns:
            True if successful, False otherwise
        """
        user_id = user_id or self.user_id
        if not user_id:
            logger.error("user_id required for delete_settings")
            return False
        
        try:
            user_db = os.path.join(self.base_data_dir, user_id, "sql_data", "chat_thread_processing.db")
            
            if not os.path.exists(user_db):
                logger.warning(f"Database not found for user {user_id}")
                return False
            
            conn = sqlite3.connect(user_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM user_settings
                WHERE user_id = ? AND setting_type = ?
            ''', (user_id, setting_type))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Deleted settings for user {user_id} (type: {setting_type})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete settings: {e}")
            return False
