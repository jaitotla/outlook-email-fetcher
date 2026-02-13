#!/usr/bin/env python3
"""
Debug script to test attachment storage with detailed output
"""

import requests
import base64
import json

AGENT_URL = "http://localhost:8000"
ENDPOINT ='http://43.204.98.38:8000/api/store-attachments'

# Real user email from your workspace
USER_EMAIL = "patilswapnil5090@gmail.com"
THREAD_ID = "test_thread_debug_001"
MESSAGE_ID = "msg_debug_001"

# Create simple text attachment
text_content = b"This is a test attachment for debugging"
encoded_content = base64.b64encode(text_content).decode('utf-8')

payload = {
    "user_id": USER_EMAIL,
    "thread_id": THREAD_ID,
    "message_id": MESSAGE_ID,
    "attachments": [
        {
            "filename": "debug_test.txt",
            "content": encoded_content,
            "mime_type": "text/plain"
        }
    ]
}

print("\n" + "="*70)
print("SENDING DEBUG REQUEST TO STORE-ATTACHMENTS")
print("="*70)
print(f"\nPayload:")
print(json.dumps({
    "user_id": USER_EMAIL,
    "thread_id": THREAD_ID,
    "message_id": MESSAGE_ID,
    "attachments": [
        {
            "filename": "debug_test.txt",
            "content": f"{encoded_content[:50]}... ({len(encoded_content)} bytes)",
            "mime_type": "text/plain"
        }
    ]
}, indent=2))

try:
    print(f"\n\n📤 Sending POST request to {ENDPOINT}")
    print("Waiting for response...\n")
    
    response = requests.post(ENDPOINT, json=payload, timeout=30)
    
    print(f"Response Status: {response.status_code}")
    print(f"\nResponse Body:")
    print(json.dumps(response.json(), indent=2))
    
    if response.status_code == 200:
        result = response.json()
        filepath = result.get('metadata_file')
        print(f"\n\n📂 Checking if files exist...")
        
        import os
        if filepath and os.path.exists(filepath):
            print(f"✅ Metadata file exists: {filepath}")
            with open(filepath, 'r') as f:
                metadata = json.load(f)
            print(f"\nMetadata content:")
            print(json.dumps(metadata, indent=2))
        else:
            print(f"❌ Metadata file not found: {filepath}")
            
        # Check for actual files
        for file_info in result.get('saved_files', []):
            filepath = file_info.get('filepath')
            print(f"\nChecking file: {filepath}")
            if os.path.exists(filepath):
                print(f"✅ File exists ({os.path.getsize(filepath)} bytes)")
            else:
                print(f"❌ File does NOT exist")
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70 + "\n")
