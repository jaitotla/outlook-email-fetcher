"""
Script to call /api/settings endpoint with user settings
"""
import requests
import json

# Settings from test.py
settings_data = {
    "mode": "local",
    "agent_url": "m15.lsdiedb39c.pagekite.me",
    "llm_provider": "manotr",
    "llm_api_key": "",
    "llm_model": "gpt-4o-mini",
    "llm_base_url": "",
    "llm_ollama_api_key": "",
    "embedding_provider": "manotr",
    "embedding_api_key": "",
    "embedding_model": "text-embedding-3-small",
    "embedding_base_url": "",
    "embedding_ollama_api_key": "",
    "vector_provider": "manotr",
    "vector_url": "",
    "vector_api_key": "",
    "user_name": "swa",
    "user_position": "pm",
    "user_tone": "professional",
    "system_prompt": "",
    "imap_app_password": "vcjx frxi nwqr kwvu",
    "run_imap_server": True,
    "imap_email": "patilswapnil1606@gmail.com",
}

# API endpoint configuration
BACKEND_URL = "http://localhost:5051"  # Default backend port
USER_ID = "patilswapnil1606@gmail.com"  # Use IMAP email as user_id

def call_settings_api():
    """
    POST settings to /api/settings endpoint
    """
    url = f"{BACKEND_URL}/api/settings"
    
    payload = {
        "user_id": USER_ID,
        "settings": settings_data
    }
    
    print(f"📤 Calling POST {url}")
    print(f"👤 User ID: {USER_ID}")
    print(f"📋 Settings: {len(settings_data)} fields")
    print("-" * 60)
    
    try:
        response = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        print(f"✅ Status Code: {response.status_code}")
        print("-" * 60)
        
        if response.status_code == 200:
            result = response.json()
            print("📥 Response:")
            print(json.dumps(result, indent=2))
            
            if result.get("success"):
                print("\n✅ Settings saved successfully!")
                if "settings" in result:
                    print(f"   Saved {len(result['settings'])} settings")
                if "source" in result:
                    print(f"   Storage: {result['source']}")
            else:
                print("\n⚠️  API returned success=false")
        else:
            print(f"❌ Error Response:")
            print(response.text)
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Backend server is not running")
        print(f"   Make sure the backend is running on {BACKEND_URL}")
        print(f"   Run: cd openmailbot/backend && python main.py")
    except requests.exceptions.Timeout:
        print("❌ Timeout: Backend server did not respond in 10 seconds")
    except Exception as e:
        print(f"❌ Unexpected Error: {type(e).__name__}: {str(e)}")

def get_settings_api():
    """
    GET settings from /api/settings/{user_id} endpoint
    """
    url = f"{BACKEND_URL}/api/settings/{USER_ID}"
    
    print(f"\n📤 Calling GET {url}")
    print("-" * 60)
    
    try:
        response = requests.get(url, timeout=10)
        
        print(f"✅ Status Code: {response.status_code}")
        print("-" * 60)
        
        if response.status_code == 200:
            result = response.json()
            print("📥 Current Settings:")
            print(json.dumps(result, indent=2))
        else:
            print(f"❌ Error Response:")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {str(e)}")

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 OpenMailBot - Settings API Caller")
    print("=" * 60)
    
    # First, save settings
    call_settings_api()
    
    # Then, retrieve settings to verify
    print("\n" + "=" * 60)
    print("🔍 Verifying saved settings...")
    print("=" * 60)
    get_settings_api()
