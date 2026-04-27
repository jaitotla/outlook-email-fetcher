"""
Standalone script to check user settings in encrypted SQLite database
"""
import os
import sys
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.settings_manager import SettingsManager

def check_settings(user_id):
    """Check settings for a specific user"""
    print(f"\n{'='*80}")
    print(f"CHECKING SETTINGS FOR USER: {user_id}")
    print(f"{'='*80}\n")
    
    try:
        # Initialize settings manager
        settings_manager = SettingsManager(user_id)
        
        # Check database path
        db_path = os.path.join(
            os.path.dirname(__file__),
            "data",
            user_id,
            "sql_data",
            "chat_thread_processing.db"
        )
        print(f"📂 Expected database location:")
        print(f"   {db_path}")
        print(f"   Exists: {os.path.exists(db_path)}\n")
        
        # Try to get settings
        print("🔍 Attempting to retrieve settings (type: general)...")
        settings = settings_manager.get_settings(user_id, "general")
        
        if settings:
            print(f"✅ Settings found!\n")
            print(f"📋 Settings content:")
            print(json.dumps(settings, indent=2))
            print(f"\n📊 Settings summary:")
            print(f"   - LLM Provider: {settings.get('llm_provider', 'NOT SET')}")
            print(f"   - LLM Model: {settings.get('llm_model', 'NOT SET')}")
            print(f"   - Embedding Provider: {settings.get('embedding_provider', 'NOT SET')}")
            print(f"   - Embedding Model: {settings.get('embedding_model', 'NOT SET')}")
            print(f"   - Vector Provider: {settings.get('vector_provider', 'NOT SET')}")
            print(f"   - Mode: {settings.get('mode', 'NOT SET')}")
        else:
            print(f"❌ No settings found (returned None)")
            print(f"\nPossible reasons:")
            print(f"   1. Database file doesn't exist")
            print(f"   2. No settings saved for this user")
            print(f"   3. Database is empty")
        
    except Exception as e:
        print(f"❌ Error checking settings: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    # Check for multiple users if needed
    users_to_check = [
        "patilswapnil5090@gmail.com",
        "patilswapnil1606@gmail.com"
    ]
    
    for user_id in users_to_check:
        check_settings(user_id)
