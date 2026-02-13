#!/usr/bin/env python3
"""
Diagnostic script to check why Gmail add-on isn't storing attachments
"""

import json
import os
import subprocess

print("\n" + "="*80)
print("GMAIL ADD-ON ATTACHMENT STORAGE DIAGNOSTICS")
print("="*80)

# 1. Check if agent is running
print("\n1️⃣  Checking if Agent is running...")
try:
    import requests
    response = requests.get("http://localhost:8000/health", timeout=5)
    if response.status_code == 200:
        print("   ✅ Agent is running on http://localhost:8000")
    else:
        print(f"   ⚠️  Agent responded with status {response.status_code}")
except Exception as e:
    print(f"   ❌ Agent is NOT running: {e}")
    print("   → Start it with: cd agent && python main.py")

# 2. Check request log
print("\n2️⃣  Checking if Gmail add-on has sent ANY requests...")
log_file = "/home/ubuntu/openmailbot/openmailbot/agent_request_log.jsonl"
if os.path.exists(log_file):
    with open(log_file, 'r') as f:
        lines = f.readlines()
    print(f"   ✅ Found {len(lines)} logged requests")
    
    # Show recent requests
    if len(lines) > 0:
        print("\n   📋 Recent requests:")
        for line in lines[-5:]:
            try:
                req = json.loads(line.strip())
                print(f"      [{req.get('timestamp')}] {req.get('endpoint')} ({req.get('attachments_count')} attachments)")
            except:
                pass
else:
    print(f"   ❌ No requests logged yet")
    print(f"   → Log file location: {log_file}")

# 3. Check if attachments folder exists
print("\n3️⃣  Checking attachment storage folder...")
data_dir = "/home/ubuntu/openmailbot/openmailbot/agent/data"
if os.path.exists(data_dir):
    print(f"   ✅ Data directory exists: {data_dir}")
    
    # List user folders
    try:
        users = [d for d in os.listdir(data_dir) if os.path.isdir(os.path.join(data_dir, d))]
        print(f"   ℹ️  Users with data: {len(users)}")
        for user in users[:5]:
            user_attachments = os.path.join(data_dir, user, "store_attachments")
            if os.path.exists(user_attachments):
                threads = [d for d in os.listdir(user_attachments) if os.path.isdir(os.path.join(user_attachments, d))]
                print(f"      • {user}: {len(threads)} threads with attachments")
    except Exception as e:
        print(f"   ⚠️  Error reading data: {e}")
else:
    print(f"   ❌ Data directory does NOT exist: {data_dir}")

# 4. Check Gmail add-on configuration
print("\n4️⃣  Checking Gmail add-on configuration...")
addon_file = "/home/ubuntu/openmailbot/openmailbot/addon/gmail_summariser.gs"
if os.path.exists(addon_file):
    print(f"   ✅ Gmail add-on found: {addon_file}")
    
    # Check for FLASK_SERVER_URL references
    with open(addon_file, 'r') as f:
        content = f.read()
    
    if "FLASK_SERVER_URL" in content:
        print(f"   ✅ FLASK_SERVER_URL is referenced in code")
        print(f"      → Check if it's configured in App Script Properties")
    else:
        print(f"   ⚠️  FLASK_SERVER_URL not found in code")
    
    if "storeMessageAttachments" in content:
        print(f"   ✅ storeMessageAttachments() function exists")
    else:
        print(f"   ⚠️  storeMessageAttachments() function not found")
else:
    print(f"   ❌ Gmail add-on not found: {addon_file}")

# 5. Check allowed attachment types
print("\n5️⃣  Checking allowed attachment types in Gmail add-on...")
if os.path.exists(addon_file):
    with open(addon_file, 'r') as f:
        lines = f.readlines()
    
    for i, line in enumerate(lines):
        if "allowedExtensions" in line:
            print(f"   Line {i}: {line.strip()}")
            # Print next few lines to see the allowed extensions
            for j in range(1, 4):
                if i+j < len(lines):
                    print(f"   Line {i+j}: {lines[i+j].strip()}")
            break

# 6. Summary and next steps
print("\n" + "="*80)
print("NEXT STEPS")
print("="*80)

print("\n📋 Checklist:")
print("  [ ] Agent is running (http://localhost:8000)")
print("  [ ] Gmail add-on has FLASK_SERVER_URL configured")
print("  [ ] Email attachments have allowed extensions (.pdf, .csv, .pptx, .ppt)")
print("  [ ] At least one request appears in agent_request_log.jsonl")
print("  [ ] Files are created in agent/data/{user}/store_attachments/{thread}/")

print("\n🔍 To debug further:")
print("  1. Open Gmail add-on in Google Sheets")
print("  2. Check browser console (F12) for errors")
print("  3. Look for error messages about 'FLASK_SERVER_URL not configured'")
print("  4. Monitor server logs: tail -f agent output")
print("  5. Run: python agent_request_logger.py (to see recent requests)")

print("\n" + "="*80 + "\n")
