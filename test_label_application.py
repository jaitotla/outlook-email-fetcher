"""
Test script to apply FYI label to the provided email
Uses /api/label-email-async to actually apply labels to Gmail
"""
import requests
import json
from datetime import datetime

# ⚠️  TO GET THESE VALUES:
# 1. gmail_thread_id: Open email in Gmail, check URL: mail.google.com/mail/u/0/#inbox/xxxxxxxxxx
#    The 'xxxxxxxxxx' is your gmail_thread_id (usually 16 hex chars)
# 2. access_token: This comes from Google OAuth. For testing, you can:
#    - Use the Gmail Add-on's built-in token (it gets this automatically)
#    - Or manually authorize and get a fresh token from Google OAuth

# Email data from user - UPDATED FOR ASYNC ENDPOINT
email_data = {
    "user_id": "patilswapnil1606@gmail.com",
    "thread_id": "69f30526.170a0220.2a884b.c56bSMTPIN_ADDED_MISSING@mx.google.com",
    "gmail_thread_id": "18b3d4f5c8a9b2e1",  # ← Replace with actual Gmail thread ID from URL
    "access_token": "ya29.YOUR_OAUTH_TOKEN_HERE",  # ← Replace with actual OAuth token
    "messages": [
        {
            "message_id": "69f30526.170a0220.2a884b.c56bSMTPIN_ADDED_MISSING@mx.google.com",
            "from_address": "praveenYmx1YnJpZGdlLmNvbQ==@naukri.com",
            "to": ["patilswapnil1606@gmail.com"],
            "subject": "✉️ Job | Ai Ml Engineer (Freshers) in Chennai",
            "timestamp": "2026-04-30 07:30:44",
            "body": "apply these"
        }
    ]
}

# API endpoint - NOW USING ASYNC (applies labels to Gmail!)
API_URL = "http://m15.lsdiedb39c.pagekite.me/api/label-email-async"

print("=" * 80)
print("📨 LABEL APPLICATION TEST (ASYNC - Actually applies to Gmail)")
print("=" * 80)
print(f"\n⚠️  BEFORE RUNNING THIS TEST:")
print(f"   1. Replace 'gmail_thread_id' with the actual ID from Gmail URL")
print(f"   2. Replace 'access_token' with your Gmail OAuth token")
print(f"   3. You can get the OAuth token from the Gmail Add-on automatically")
print(f"\n📝 How to get gmail_thread_id:")
print(f"   - Open the email in Gmail")
print(f"   - Look at the URL: mail.google.com/mail/u/0/#inbox/XXXXXXXX")
print(f"   - The 'XXXXXXXX' is your gmail_thread_id (usually 16 hex chars)")
print(f"\n🎯 Target Email:")
print(f"   From: {email_data['messages'][0]['from_address']}")
print(f"   Subject: {email_data['messages'][0]['subject']}")
print(f"   Body: {email_data['messages'][0]['body']}")
print(f"   Message ID: {email_data['messages'][0]['message_id']}")
print(f"\n📤 Sending to: {API_URL}")
print(f"\n📋 Request payload:")
print(json.dumps(email_data, indent=2))

try:
    response = requests.post(API_URL, json=email_data, timeout=30)
    
    print(f"\n✅ Response Status: {response.status_code}")
    print(f"\n📥 Response:")
    result = response.json()
    print(json.dumps(result, indent=2))
    
    # Handle both 200 (sync) and 202 (async accepted)
    if response.status_code == 202:
        print(f"\n✨ Job Submitted Successfully (Async Processing)!")
        print(f"   Job ID: {result.get('job_id')}")
        print(f"   Status: {result.get('status')}")
        print(f"   Message: {result.get('message')}")
        print(f"\n   ⏳ Label is being applied to Gmail in the background...")
        print(f"   📋 You can check status with: GET /api/job-status/{result.get('job_id')}")
    elif response.status_code == 200:
        print(f"\n✨ Label Applied Successfully!")
        print(f"   Assigned Label: {result.get('label')}")
        print(f"   Category: {result.get('category')}")
        print(f"   Topic: {result.get('topic')}")
        print(f"   Subtopic: {result.get('subtopic')}")
    else:
        print(f"\n❌ Error: {result.get('detail', 'Unknown error')}")
        
except requests.exceptions.ConnectionError:
    print(f"\n❌ ERROR: Could not connect to {API_URL}")
    print(f"   Make sure the agent backend is running on port 5051")
    print(f"   Run: python agent/main.py")
except Exception as e:
    print(f"\n❌ ERROR: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
