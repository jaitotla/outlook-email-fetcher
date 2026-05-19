"""
IMAP Credentials Database Manager
Stores and manages user IMAP credentials (email and app password) in SQLite
"""
import sqlite3
import os
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import threading


class IMAPDatabaseManager:
    """
    Manages IMAP user credentials in SQLite database.
    Supports multi-user storage and retrieval.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize IMAP database manager.
        
        Parameters
        ----------
        db_path : Optional[str]
            Path to SQLite database file. If None, uses default in backend folder.
        """
        if db_path is None:
            # Default: store in backend folder
            backend_dir = os.path.dirname(os.path.dirname(__file__))
            db_path = os.path.join(backend_dir, "imap_users.db")
        
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_database()
    
    def _init_database(self):
        """Create database tables if they don't exist"""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                
                # Create users table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS imap_users (
                        user_id TEXT PRIMARY KEY,
                        email TEXT NOT NULL,
                        app_password TEXT NOT NULL,
                        imap_host TEXT DEFAULT 'imap.gmail.com',
                        imap_port INTEGER DEFAULT 993,
                        enabled BOOLEAN DEFAULT 1,
                        last_check TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create index on email for faster lookups
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_email ON imap_users(email)
                """)
                
                conn.commit()
                print(f"✅ IMAP database initialized: {self.db_path}")
            finally:
                conn.close()
    
    def add_or_update_user(
        self,
        user_id: str,
        email: str,
        app_password: str,
        imap_host: str = "imap.gmail.com",
        imap_port: int = 993,
        enabled: bool = True
    ) -> bool:
        """
        Add new user or update existing user credentials.
        
        Parameters
        ----------
        user_id : str
            Unique user identifier (usually email)
        email : str
            Email address for IMAP login
        app_password : str
            IMAP app password
        imap_host : str
            IMAP server hostname
        imap_port : int
            IMAP SSL port
        enabled : bool
            Whether IMAP fetching is enabled for this user
        
        Returns
        -------
        bool
            True if successful
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                
                # Check if user exists
                cursor.execute("SELECT user_id FROM imap_users WHERE user_id = ?", (user_id,))
                exists = cursor.fetchone() is not None
                
                if exists:
                    # Update existing user
                    cursor.execute("""
                        UPDATE imap_users 
                        SET email = ?, 
                            app_password = ?, 
                            imap_host = ?, 
                            imap_port = ?,
                            enabled = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = ?
                    """, (email, app_password, imap_host, imap_port, enabled, user_id))
                    print(f"✅ Updated IMAP user: {user_id}")
                else:
                    # Insert new user
                    cursor.execute("""
                        INSERT INTO imap_users 
                        (user_id, email, app_password, imap_host, imap_port, enabled)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (user_id, email, app_password, imap_host, imap_port, enabled))
                    print(f"✅ Added new IMAP user: {user_id}")
                
                conn.commit()
                return True
            except Exception as e:
                print(f"❌ Error adding/updating IMAP user {user_id}: {e}")
                return False
            finally:
                conn.close()
    
    def get_user(self, user_id: str) -> Optional[Dict]:
        """
        Get user credentials by user_id.
        
        Returns
        -------
        Optional[Dict]
            User data dict or None if not found
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT user_id, email, app_password, imap_host, imap_port, 
                           enabled, last_check, created_at, updated_at
                    FROM imap_users 
                    WHERE user_id = ?
                """, (user_id,))
                
                row = cursor.fetchone()
                if row:
                    return {
                        "user_id": row[0],
                        "email": row[1],
                        "app_password": row[2],
                        "imap_host": row[3],
                        "imap_port": row[4],
                        "enabled": bool(row[5]),
                        "last_check": row[6],
                        "created_at": row[7],
                        "updated_at": row[8]
                    }
                return None
            finally:
                conn.close()
    
    def get_all_enabled_users(self) -> List[Dict]:
        """
        Get all users with IMAP enabled.
        
        Returns
        -------
        List[Dict]
            List of user data dictionaries
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT user_id, email, app_password, imap_host, imap_port, 
                           enabled, last_check, created_at, updated_at
                    FROM imap_users 
                    WHERE enabled = 1
                    ORDER BY user_id
                """)
                
                rows = cursor.fetchall()
                users = []
                for row in rows:
                    users.append({
                        "user_id": row[0],
                        "email": row[1],
                        "app_password": row[2],
                        "imap_host": row[3],
                        "imap_port": row[4],
                        "enabled": bool(row[5]),
                        "last_check": row[6],
                        "created_at": row[7],
                        "updated_at": row[8]
                    })
                return users
            finally:
                conn.close()
    
    def update_last_check(self, user_id: str, timestamp: Optional[datetime] = None):
        """
        Update the last_check timestamp for a user.
        
        Parameters
        ----------
        user_id : str
            User identifier
        timestamp : Optional[datetime]
            Timestamp to set. If None, uses current time.
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE imap_users 
                    SET last_check = ?
                    WHERE user_id = ?
                """, (timestamp.isoformat(), user_id))
                conn.commit()
            finally:
                conn.close()
    
    def disable_user(self, user_id: str) -> bool:
        """
        Disable IMAP fetching for a user.
        
        Returns
        -------
        bool
            True if successful
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE imap_users 
                    SET enabled = 0, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """, (user_id,))
                conn.commit()
                print(f"✅ Disabled IMAP for user: {user_id}")
                return True
            except Exception as e:
                print(f"❌ Error disabling IMAP for user {user_id}: {e}")
                return False
            finally:
                conn.close()
    
    def enable_user(self, user_id: str) -> bool:
        """
        Enable IMAP fetching for a user.
        
        Returns
        -------
        bool
            True if successful
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE imap_users 
                    SET enabled = 1, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """, (user_id,))
                conn.commit()
                print(f"✅ Enabled IMAP for user: {user_id}")
                return True
            except Exception as e:
                print(f"❌ Error enabling IMAP for user {user_id}: {e}")
                return False
            finally:
                conn.close()
    
    def delete_user(self, user_id: str) -> bool:
        """
        Delete a user from the database.
        
        Returns
        -------
        bool
            True if successful
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM imap_users WHERE user_id = ?", (user_id,))
                conn.commit()
                print(f"✅ Deleted IMAP user: {user_id}")
                return True
            except Exception as e:
                print(f"❌ Error deleting IMAP user {user_id}: {e}")
                return False
            finally:
                conn.close()
