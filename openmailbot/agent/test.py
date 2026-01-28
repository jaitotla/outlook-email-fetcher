import requests
import json

url = "http://localhost:8000/chat-with-thread"

payload = {
    "user_id": "test_user",
    "thread_id": "19b3b6bd4843dd1d",
    "question": "Summarize this thread"
}

try:
    response = requests.post(url, json=payload, timeout=30)
    
    print(f"Status: {response.status_code}")
    
    # Handle response based on status code
    if response.status_code == 200:
        print("✅ Success")
        data = response.json()
        print(json.dumps(data, indent=2))
    
    elif response.status_code == 400:
        print("❌ Bad Request")
        print(response.text)
    
    elif response.status_code == 404:
        print("❌ Not Found")
        print(response.text)
    
    elif response.status_code == 500:
        print("❌ Server Error")
        print(response.text)
    
    else:
        print(f"⚠️  Unexpected status: {response.status_code}")
        print(response.text)

except requests.exceptions.ConnectionError:
    print("❌ Connection Error: Agent not running at http://localhost:8000")
except requests.exceptions.Timeout:
    print("❌ Timeout: Request took too long")
except Exception as e:
    print(f"❌ Error: {e}")