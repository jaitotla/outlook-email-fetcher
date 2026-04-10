#!/usr/bin/env python3
"""
Test script for Settings Management API
Demonstrates how to update, retrieve, and persist settings
"""
import requests
import json
import time

BASE_URL = "http://m15.lsdiedb39c.pagekite.me"

def test_get_settings():
    """Test getting current settings"""
    print("\n" + "="*60)
    print("TEST 1: Get Current Settings")
    print("="*60)
    
    try:
        response = requests.get(f"{BASE_URL}/api/settings")
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ Status: {response.status_code}")
        print(f"✅ Settings retrieved ({len(data['settings'])} items)")
        print(f"\nSample settings:")
        sample = {k: data['settings'][k] for k in list(data['settings'].keys())[:5]}
        print(json.dumps(sample, indent=2, default=str))
        
        return data['settings']
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def test_update_settings():
    """Test updating settings"""
    print("\n" + "="*60)
    print("TEST 2: Update Settings")
    print("="*60)
    
    update_payload = {
        "LLM_PROVIDER": "openai",
        "TEMPERATURE": 0.5,
        "MAX_TOKENS": 4096
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/settings",
            json=update_payload
        )
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ Status: {response.status_code}")
        print(f"✅ {data['message']}")
        print(f"✅ Saved to: {data['saved_file']}")
        print(f"\nUpdated settings:")
        print(json.dumps(data['updated_settings'], indent=2))
        
        return data
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def test_verify_update():
    """Verify that settings were actually updated"""
    print("\n" + "="*60)
    print("TEST 3: Verify Update Persisted")
    print("="*60)
    
    try:
        response = requests.get(f"{BASE_URL}/api/settings")
        response.raise_for_status()
        
        data = response.json()
        settings = data['settings']
        
        print(f"✅ Status: {response.status_code}")
        print(f"✅ LLM_PROVIDER = {settings.get('LLM_PROVIDER')}")
        print(f"✅ TEMPERATURE = {settings.get('TEMPERATURE')}")
        print(f"✅ MAX_TOKENS = {settings.get('MAX_TOKENS')}")
        
        # Check if updates were applied
        if (settings.get('LLM_PROVIDER') == 'openai' and 
            settings.get('TEMPERATURE') == 0.5 and 
            settings.get('MAX_TOKENS') == 4096):
            print("\n✅ ALL UPDATES VERIFIED!")
        else:
            print("\n⚠️  Some updates may not have been applied")
            
    except Exception as e:
        print(f"❌ Error: {e}")


def test_reload_settings():
    """Test reloading settings from file"""
    print("\n" + "="*60)
    print("TEST 4: Reload Settings from File")
    print("="*60)
    
    try:
        response = requests.get(f"{BASE_URL}/api/settings/reload")
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ Status: {response.status_code}")
        print(f"✅ {data['message']}")
        print(f"✅ Settings reloaded ({len(data['settings'])} items)")
        
    except Exception as e:
        print(f"❌ Error: {e}")


def test_save_settings():
    """Test explicitly saving settings"""
    print("\n" + "="*60)
    print("TEST 5: Explicitly Save Settings")
    print("="*60)
    
    try:
        response = requests.post(f"{BASE_URL}/api/settings/save")
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ Status: {response.status_code}")
        print(f"✅ {data['message']}")
        print(f"✅ File: {data['file']}")
        
    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    """Run all tests"""
    print("\n" + "🔧 "*30)
    print("Settings Management API Tests")
    print("🔧 "*30)
    
    print(f"\nTarget: {BASE_URL}")
    print("Make sure the agent is running: python main.py\n")
    
    # Test sequence
    initial_settings = test_get_settings()
    
    time.sleep(0.5)
    test_update_settings()
    
    time.sleep(0.5)
    test_verify_update()
    
    time.sleep(0.5)
    test_reload_settings()
    
    time.sleep(0.5)
    test_save_settings()
    
    print("\n" + "="*60)
    print("All tests completed!")
    print("="*60)
    print("\nCheck agent/config_settings.json to see persisted settings")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTests cancelled by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
