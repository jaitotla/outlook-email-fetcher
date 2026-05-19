import httpx
import json
import sys
import traceback

BASE_URL = "http://localhost:5051"
USER_ID = "patilswapnil1606@gmail.com"

print(f"\n🔗 Testing connection to {BASE_URL}")
try:
    test_conn = httpx.get(f"{BASE_URL}/docs")
    print(f"✅ Backend is reachable (status: {test_conn.status_code})")
except Exception as e:
    print(f"❌ Cannot reach backend: {e}")
    sys.exit(1)

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

def test_get_settings():
    """Test GET /api/settings endpoint"""
    print("\n" + "="*70)
    print("TEST 1: GET /api/settings (fetch existing settings)")
    print("="*70)
    
    try:
        print(f"Making GET request to: {BASE_URL}/api/settings?user_id={USER_ID}")
        response = httpx.get(
            f"{BASE_URL}/api/settings",
            params={"user_id": USER_ID},
            timeout=15.0  # Increased timeout
        )
        print(f"✅ Request sent successfully")
        print(f"Status Code: {response.status_code}")
        print(f"Response:\n{json.dumps(response.json(), indent=2)}")
    except httpx.ConnectError as e:
        print(f"❌ Connection Error: {e}")
        traceback.print_exc()
    except Exception as e:
        print(f"❌ Error: {e}")
        traceback.print_exc()

def test_post_settings():
    """Test POST /api/settings endpoint"""
    print("\n" + "="*70)
    print("TEST 2: POST /api/settings (save settings)")
    print("="*70)
    
    payload = {
        "user_id": USER_ID,
        "settings": settings_data
    }
    
    print(f"Sending payload:\n{json.dumps(payload, indent=2)}")
    print()
    
    try:
        print(f"Making POST request to: {BASE_URL}/api/settings")
        response = httpx.post(
            f"{BASE_URL}/api/settings",
            json=payload,
            timeout=30.0  # Increased timeout for IMAP async task
        )
        print(f"✅ Request sent successfully")
        print(f"Status Code: {response.status_code}")
        print(f"Response:\n{json.dumps(response.json(), indent=2)}")
    except httpx.ConnectError as e:
        print(f"❌ Connection Error: {e}")
        traceback.print_exc()
    except Exception as e:
        print(f"❌ Error: {e}")
        traceback.print_exc()

def test_get_settings_by_path():
    """Test GET /api/settings/{user_id} endpoint"""
    print("\n" + "="*70)
    print("TEST 3: GET /api/settings/{user_id} (fetch by path parameter)")
    print("="*70)
    
    try:
        print(f"Making GET request to: {BASE_URL}/api/settings/{USER_ID}")
        response = httpx.get(
            f"{BASE_URL}/api/settings/{USER_ID}",
            timeout=15.0  # Increased timeout
        )
        print(f"✅ Request sent successfully")
        print(f"Status Code: {response.status_code}")
        print(f"Response:\n{json.dumps(response.json(), indent=2)}")
    except httpx.ConnectError as e:
        print(f"❌ Connection Error: {e}")
        traceback.print_exc()
    except Exception as e:
        print(f"❌ Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    print("\n🚀 Starting API Tests for /api/settings endpoint\n")
    
    test_post_settings()
    test_get_settings()
    test_get_settings_by_path()
    
    print("\n" + "="*70)
    print("✅ All tests completed")
    print("="*70 + "\n")
