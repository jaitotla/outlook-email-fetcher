#!/usr/bin/env python3
"""
Test script for attachment storage endpoint
Tests the /api/store-attachments endpoint with sample attachments
"""

import requests
import base64
import json
import os
from pathlib import Path

# Configuration
AGENT_URL = "http://localhost:8000"
STORE_ATTACHMENTS_ENDPOINT = f"{AGENT_URL}/api/store-attachments"

# Sample test data
TEST_USER = "test@example.com"
TEST_THREAD = "thread_12345"
TEST_MESSAGE = "msg_67890"

def create_test_pdf():
    """Create a minimal PDF content for testing"""
    # Minimal PDF: %PDF-1.0 header + basic object
    pdf_content = b"""%PDF-1.0
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /MediaBox [0 0 612 792] /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>
endobj
4 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
5 0 obj
<< >>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF) Tj
ET
endstream
endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000273 00000 n
0000000365 00000 n
trailer
<< /Size 6 /Root 1 0 R >>
startxref
470
%%EOF"""
    return pdf_content

def test_store_attachments():
    """Test the attachment storage endpoint"""
    
    print("=" * 60)
    print("Testing Attachment Storage")
    print("=" * 60)
    
    # Create test attachments
    test_files = {
        "test_document.pdf": create_test_pdf(),
        "test_data.txt": b"This is test data for attachment storage",
        "test_config.json": json.dumps({"key": "value", "test": True}).encode('utf-8')
    }
    
    # Prepare request payload
    attachments = []
    for filename, content in test_files.items():
        encoded_content = base64.b64encode(content).decode('utf-8')
        attachments.append({
            "filename": filename,
            "content": encoded_content,
            "mime_type": "application/octet-stream"
        })
    
    payload = {
        "user_id": TEST_USER,
        "thread_id": TEST_THREAD,
        "message_id": TEST_MESSAGE,
        "attachments": attachments
    }
    
    print("\n📤 Sending attachment storage request...")
    print(f"   User: {TEST_USER}")
    print(f"   Thread: {TEST_THREAD}")
    print(f"   Message: {TEST_MESSAGE}")
    print(f"   Attachments: {len(attachments)}")
    
    try:
        response = requests.post(STORE_ATTACHMENTS_ENDPOINT, json=payload, timeout=30)
        
        print(f"\n📨 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ SUCCESS: {result.get('message')}")
            
            print("\n📋 Saved Files:")
            for file_info in result.get('saved_files', []):
                print(f"   ✓ {file_info['filename']} ({file_info['size']} bytes)")
                print(f"     → {file_info['filepath']}")
            
            if result.get('errors'):
                print("\n⚠️ Errors:")
                for error in result['errors']:
                    print(f"   ✗ {error}")
            
            print(f"\n📂 Metadata: {result.get('metadata_file')}")
            
            # Verify files exist
            print("\n🔍 Verifying stored files...")
            metadata_file = result.get('metadata_file')
            if metadata_file and os.path.exists(metadata_file):
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                print(f"✅ Metadata file verified")
                print(f"   Timestamp: {metadata.get('timestamp')}")
                
                # Check actual files
                for file_info in result.get('saved_files', []):
                    filepath = file_info['filepath']
                    if os.path.exists(filepath):
                        actual_size = os.path.getsize(filepath)
                        print(f"✅ File exists: {file_info['filename']} ({actual_size} bytes)")
                    else:
                        print(f"❌ File missing: {file_info['filename']}")
            
            return True
        
        else:
            print(f"❌ FAILED: {response.status_code}")
            print(f"Error: {response.text}")
            return False
    
    except requests.exceptions.ConnectionError:
        print(f"❌ ERROR: Could not connect to {AGENT_URL}")
        print("   Make sure the FastAPI server is running on http://localhost:8000")
        return False
    
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_log_email():
    """Test the log-email endpoint"""
    
    print("\n" + "=" * 60)
    print("Testing Email Logging")
    print("=" * 60)
    
    email_log_endpoint = f"{AGENT_URL}/api/log-email"
    
    payload = {
        "user_id": TEST_USER,
        "thread_id": TEST_THREAD,
        "messages": [
            {
                "message_id": "msg_1",
                "from_address": "sender@example.com",
                "to": ["recipient@example.com"],
                "subject": "Test Email",
                "timestamp": "2026-01-29T10:00:00Z",
                "body": "This is a test email message."
            }
        ]
    }
    
    print("\n📤 Sending email log request...")
    
    try:
        response = requests.post(email_log_endpoint, json=payload, timeout=30)
        
        print(f"📨 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Email logged successfully")
            return True
        else:
            print(f"❌ Failed: {response.text}")
            return False
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


if __name__ == "__main__":
    print("\n🚀 Starting attachment storage tests...\n")
    
    # Test attachment storage
    attachment_result = test_store_attachments()
    
    # Test email logging
    email_result = test_log_email()
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"Attachment Storage: {'✅ PASSED' if attachment_result else '❌ FAILED'}")
    print(f"Email Logging: {'✅ PASSED' if email_result else '❌ FAILED'}")
    print("=" * 60 + "\n")
