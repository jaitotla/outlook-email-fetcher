#!/usr/bin/env python3
"""
Query settings from encrypted database for a user
"""
import sys
import os
import sqlite3
import json
import base64

# Add the agent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.settings_manager import decrypt_settings, SettingsManager

def query_user_settings(user_id):
    """Query and display user settings from encrypted database"""
    print(f"\n{'='*70}")
    print(f"Querying Settings Database for User: {user_id}")
    print(f"{'='*70}\n")
    
    # Get the database path - point to backend/data
    # From: openmailbot/agent/scripts/test.py
    # To: openmailbot/backend/data
    base_data_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),  # openmailbot/
        "backend",
        "data"
    )
    user_db = os.path.join(base_data_dir, user_id, "sql_data", "chat_thread_processing.db")
    
    # Check if database exists
    if not os.path.exists(user_db):
        print(f"❌ Database not found at: {user_db}")
        print(f"   Database path should be: data/{user_id}/sql_data/chat_thread_processing.db")
        return False
    
    print(f"✅ Database found at: {user_db}")
    print(f"   File size: {os.path.getsize(user_db)} bytes\n")
    
    try:
        # Connect to database
        conn = sqlite3.connect(user_db)
        cursor = conn.cursor()
        
        # Check if user_settings table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='user_settings'
        """)
        table_exists = cursor.fetchone()
        
        if not table_exists:
            print("❌ user_settings table not found in database")
            conn.close()
            return False
        
        print("✅ user_settings table found\n")
        
        # Query all settings for this user
        cursor.execute('''
            SELECT id, setting_key, encrypted_value, setting_type, 
                   timestamp, updated_timestamp
            FROM user_settings
            WHERE user_id = ?
            ORDER BY updated_timestamp DESC
        ''', (user_id,))
        
        rows = cursor.fetchall()
        
        if not rows:
            print(f"⚠️  No settings found for user {user_id}")
            conn.close()
            return False
        
        print(f"✅ Found {len(rows)} setting(s) in database\n")
        print(f"{'-'*70}")
        
        # Display raw database entries
        print("\n📋 Raw Database Entries:")
        print(f"{'-'*70}\n")
        
        for row in rows:
            id_, key, encrypted_val, setting_type, timestamp, updated_ts = row
            print(f"ID: {id_}")
            print(f"Key: {key}")
            print(f"Type: {setting_type}")
            print(f"Timestamp: {timestamp}")
            print(f"Updated: {updated_ts}")
            print(f"Encrypted Value (first 50 chars): {encrypted_val[:50]}...")
            print()
        
        # Try to decrypt settings
        print(f"{'-'*70}")
        print("\n🔐 Decrypted Settings:")
        print(f"{'-'*70}\n")
        
        manager = SettingsManager(user_id)
        settings = manager.get_settings(user_id, "general")
        
        if settings:
            print(json.dumps(settings, indent=2))
            print(f"\n✅ Total settings retrieved: {len(settings)}")
            print(f"   Settings: {', '.join(settings.keys())}")
        else:
            print("❌ Failed to retrieve/decrypt settings")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error querying database: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    user_email = "patilswapnil5090@gmail.com"
    success = query_user_settings(user_email)
    
    if success:
        print(f"\n✅ Query completed successfully")
    else:
        print(f"\n❌ Query failed")
    
    sys.exit(0 if success else 1)


