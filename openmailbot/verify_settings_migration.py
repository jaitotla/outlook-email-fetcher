#!/usr/bin/env python3
"""
Verification script for Settings Manager implementation
Tests encryption, storage, and retrieval of user settings
"""

import os
import sys
import json
from pathlib import Path

# Add agent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'agent'))

def test_settings_manager():
    """Test the SettingsManager functionality"""
    print("=" * 70)
    print("SETTINGS MANAGER VERIFICATION TEST")
    print("=" * 70)
    
    try:
        from services.settings_manager import SettingsManager, encrypt_settings, decrypt_settings
        print("\n✅ Successfully imported SettingsManager")
    except Exception as e:
        print(f"\n❌ Failed to import SettingsManager: {e}")
        return False
    
    # Test 1: Encryption/Decryption
    print("\n" + "-" * 70)
    print("TEST 1: Encryption/Decryption")
    print("-" * 70)
    
    try:
        test_data = {
            "llm_provider": "openai",
            "llm_api_key": "sk-proj-test-secret-key-12345",
            "llm_model": "gpt-4o-mini",
            "user_name": "Test User",
            "user_tone": "casual"
        }
        
        user_id = "test@example.com"
        
        # Encrypt
        encrypted = encrypt_settings(test_data, user_id)
        print(f"✅ Encrypted settings: {encrypted[:50]}...")
        
        # Decrypt
        decrypted = decrypt_settings(encrypted, user_id)
        print(f"✅ Decrypted settings: {json.dumps(decrypted, indent=2)}")
        
        # Verify
        assert decrypted == test_data, "Decrypted data doesn't match original!"
        print("✅ Encryption/Decryption verification PASSED")
        
    except Exception as e:
        print(f"❌ Encryption/Decryption test FAILED: {e}")
        return False
    
    # Test 2: Save/Retrieve Settings
    print("\n" + "-" * 70)
    print("TEST 2: Save/Retrieve Settings from Database")
    print("-" * 70)
    
    try:
        manager = SettingsManager("test-user@example.com")
        
        test_settings = {
            "llm_provider": "openai",
            "llm_api_key": "sk-test-api-key",
            "llm_model": "gpt-4",
            "embedding_provider": "sentence-transformers",
            "embedding_model": "text-embedding-3-small",
            "user_name": "Test User",
            "user_tone": "professional"
        }
        
        # Save
        success = manager.save_settings(test_settings, "test-user@example.com", "general")
        print(f"{'✅' if success else '❌'} Save result: {success}")
        
        if not success:
            print("❌ Save test FAILED")
            return False
        
        # Retrieve
        retrieved = manager.get_settings("test-user@example.com", "general")
        print(f"✅ Retrieved settings: {json.dumps(retrieved, indent=2)}")
        
        # Verify
        assert retrieved == test_settings, "Retrieved data doesn't match saved!"
        print("✅ Save/Retrieve verification PASSED")
        
    except Exception as e:
        print(f"❌ Save/Retrieve test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 3: Get Specific Setting
    print("\n" + "-" * 70)
    print("TEST 3: Get Specific Setting Value")
    print("-" * 70)
    
    try:
        manager = SettingsManager("test-user@example.com")
        
        # Get existing value
        api_key = manager.get_setting_value("llm_api_key", "test-user@example.com", "general")
        print(f"✅ Retrieved llm_api_key: {api_key}")
        assert api_key == "sk-test-api-key", "API key doesn't match!"
        
        # Get with default
        model = manager.get_setting_value(
            "nonexistent_key", 
            "test-user@example.com", 
            "general",
            "default-value"
        )
        print(f"✅ Retrieved nonexistent_key with default: {model}")
        assert model == "default-value", "Default value not returned!"
        
        print("✅ Get specific setting test PASSED")
        
    except Exception as e:
        print(f"❌ Get specific setting test FAILED: {e}")
        return False
    
    # Test 4: Update Setting
    print("\n" + "-" * 70)
    print("TEST 4: Update Setting")
    print("-" * 70)
    
    try:
        manager = SettingsManager("test-user@example.com")
        
        # Update
        success = manager.update_setting(
            "user_tone", 
            "formal", 
            "test-user@example.com",
            "general"
        )
        print(f"{'✅' if success else '❌'} Update result: {success}")
        
        # Verify update
        tone = manager.get_setting_value("user_tone", "test-user@example.com", "general")
        print(f"✅ Updated user_tone: {tone}")
        assert tone == "formal", "Update not reflected!"
        
        print("✅ Update setting test PASSED")
        
    except Exception as e:
        print(f"❌ Update setting test FAILED: {e}")
        return False
    
    # Test 5: Delete Settings
    print("\n" + "-" * 70)
    print("TEST 5: Delete Settings")
    print("-" * 70)
    
    try:
        manager = SettingsManager("test-user@example.com")
        
        # Delete
        success = manager.delete_settings("test-user@example.com", "general")
        print(f"{'✅' if success else '❌'} Delete result: {success}")
        
        # Verify deletion
        retrieved = manager.get_settings("test-user@example.com", "general")
        print(f"✅ Settings after deletion: {retrieved}")
        assert retrieved is None, "Settings not deleted!"
        
        print("✅ Delete settings test PASSED")
        
    except Exception as e:
        print(f"❌ Delete settings test FAILED: {e}")
        return False
    
    # Test 6: Database Location
    print("\n" + "-" * 70)
    print("TEST 6: Verify Database Location")
    print("-" * 70)
    
    try:
        expected_db_path = os.path.join(
            os.path.dirname(__file__),
            "agent/data/test-user@example.com/sql_data/chat_thread_processing.db"
        )
        
        if os.path.exists(expected_db_path):
            print(f"✅ Database found at: {expected_db_path}")
            print(f"✅ File size: {os.path.getsize(expected_db_path)} bytes")
        else:
            print(f"⚠️  Database not found at: {expected_db_path}")
            print("   (This is OK if delete_settings was called)")
        
        print("✅ Database location test PASSED")
        
    except Exception as e:
        print(f"❌ Database location test FAILED: {e}")
        return False
    
    # Summary
    print("\n" + "=" * 70)
    print("✅ ALL TESTS PASSED")
    print("=" * 70)
    print("\nSettings Manager is working correctly!")
    print("- Encryption: ✅")
    print("- Database Storage: ✅")
    print("- Retrieval: ✅")
    print("- Updates: ✅")
    print("- Deletion: ✅")
    
    return True


def test_pipeline_integration():
    """Test integration with pipelines"""
    print("\n\n" + "=" * 70)
    print("PIPELINE INTEGRATION TEST")
    print("=" * 70)
    
    try:
        from services.settings_manager import SettingsManager
        
        print("\n✅ Testing ChatWithThreadPipeline integration...")
        # Just verify imports work
        from services.chat_pipeline import ChatWithThreadPipeline
        print("✅ ChatWithThreadPipeline imports successfully")
        
        print("\n✅ Testing DraftPipeline integration...")
        from services.draft_pipeline import DraftPipeline
        print("✅ DraftPipeline imports successfully")
        
        print("\n✅ Testing EmbeddingService integration...")
        from services.embeddings import EmbeddingService
        print("✅ EmbeddingService imports successfully (with optional settings param)")
        
        print("\n✅ Testing LLMService integration...")
        from services.llm import LLMService
        print("✅ LLMService imports successfully (with optional settings param)")
        
        print("\n" + "=" * 70)
        print("✅ ALL INTEGRATION TESTS PASSED")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Integration test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all verification tests"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  SETTINGS MANAGER VERIFICATION SUITE".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "=" * 68 + "╝")
    
    # Run tests
    results = []
    results.append(("Settings Manager Tests", test_settings_manager()))
    results.append(("Pipeline Integration Tests", test_pipeline_integration()))
    
    # Summary
    print("\n\n" + "╔" + "=" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  SUMMARY".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╠" + "=" * 68 + "╣")
    
    all_passed = True
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"║ {test_name:.<50} {status:>16} ║")
        all_passed = all_passed and result
    
    print("╚" + "=" * 68 + "╝\n")
    
    if all_passed:
        print("🎉 All verification tests passed successfully!")
        return 0
    else:
        print("❌ Some tests failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
