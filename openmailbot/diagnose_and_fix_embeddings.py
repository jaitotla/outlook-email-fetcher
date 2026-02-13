#!/usr/bin/env python3
"""
Comprehensive diagnostic and remediation script for attachment embedding issues.
Identifies and fixes all problems preventing proper embedding and storage of attachments.
"""

import os
import json
import sys
import sqlite3
from pathlib import Path

# Add agent to path
sys.path.insert(0, "/home/ubuntu/openmailbot/openmailbot/agent")

from services.chat_pipeline import ChatWithThreadPipeline
from llama_index.core import SimpleDirectoryReader
from llama_index.readers.file import PDFReader, CSVReader, PptxReader

FILE_EXTRACTOR = {
    ".pdf": PDFReader(),
    ".csv": CSVReader(),
    ".pptx": PptxReader(),
    ".ppt": PptxReader(),
}

def check_pdf_extraction():
    """Check if PDF extraction works"""
    print("\n" + "="*80)
    print("1️⃣  PDF EXTRACTION CHECK")
    print("="*80)
    
    pdf_path = "/home/ubuntu/openmailbot/openmailbot/agent/data/patilswapnil5090@gmail.com/store_attachments/19bdef3df3674e27/19bdef43712fd2bb_Hotel Appointment Booking Website 2.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"❌ PDF file not found: {pdf_path}")
        return False
    
    print(f"✓ PDF exists: {os.path.getsize(pdf_path)} bytes")
    
    try:
        print("🔄 Attempting SimpleDirectoryReader extraction...")
        documents = SimpleDirectoryReader(
            input_files=[pdf_path],
            file_extractor=FILE_EXTRACTOR
        ).load_data()
        
        print(f"✓ Extracted {len(documents)} document(s)")
        
        total_chars = 0
        for idx, doc in enumerate(documents):
            text_len = len(doc.text) if doc.text else 0
            total_chars += text_len
            print(f"  📄 Doc {idx}: {text_len} characters")
            
            if text_len == 0:
                print(f"     ⚠️  EMPTY! This chunk will be skipped.")
            else:
                print(f"     Preview: {doc.text[:100]}...")
        
        print(f"\n✓ Total content: {total_chars} characters")
        
        if total_chars == 0:
            print("❌ PDF extraction produced NO usable content!")
            print("   → Try installing: pip install pypdf pdfplumber")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_embedding_api():
    """Check if embedding API is working"""
    print("\n" + "="*80)
    print("2️⃣  EMBEDDING API CHECK")
    print("="*80)
    
    user_id = "patilswapnil5090@gmail.com"
    
    try:
        pipeline = ChatWithThreadPipeline(user_id=user_id)
        
        # Test embedding
        test_text = "This is a test document for embedding"
        print(f"Testing with: '{test_text}'")
        
        embedding = pipeline.call_embed_api(test_text)
        
        print(f"✓ Embedding API works!")
        print(f"  Embedding dimension: {len(embedding)}")
        print(f"  Sample values: {embedding[:5]}")
        
        return True
        
    except Exception as e:
        print(f"❌ Embedding API failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_chromadb_storage():
    """Check if ChromaDB storage works"""
    print("\n" + "="*80)
    print("3️⃣  CHROMADB STORAGE CHECK")
    print("="*80)
    
    user_id = "patilswapnil5090@gmail.com"
    thread_id = "19bdef3df3674e27"
    
    try:
        pipeline = ChatWithThreadPipeline(user_id=user_id)
        collection = pipeline.get_user_collection(user_id)
        
        print(f"✓ ChromaDB collection created: 'email_threads'")
        print(f"  Collection path: {os.path.join('/home/ubuntu/openmailbot/openmailbot/agent/data', user_id, 'vector_db')}")
        
        # Query for attachment data
        results = collection.get(
            where={
                "$and": [
                    {"thread_id": thread_id},
                    {"type": "attachment_data"}
                ]
            }
        )
        
        chunk_count = len(results.get("ids", []))
        print(f"\n  Stored chunks: {chunk_count}")
        
        if chunk_count > 0:
            print(f"  ✓ Attachments ARE stored in ChromaDB")
            return True
        else:
            print(f"  ⚠️  NO chunks stored for this thread yet")
            return None
        
    except Exception as e:
        print(f"❌ ChromaDB check failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_database_records():
    """Check if attachment processing is tracked in SQLite"""
    print("\n" + "="*80)
    print("4️⃣  DATABASE TRACKING CHECK")
    print("="*80)
    
    user_id = "patilswapnil5090@gmail.com"
    thread_id = "19bdef3df3674e27"
    
    user_db = os.path.join("/home/ubuntu/openmailbot/openmailbot/agent/data", user_id, "sql_data", "chat_thread_processing.db")
    
    if not os.path.exists(user_db):
        print(f"⚠️  Database doesn't exist yet: {user_db}")
        return None
    
    try:
        conn = sqlite3.connect(user_db)
        cursor = conn.cursor()
        
        # Check attachment records
        cursor.execute('''
            SELECT id, attachment_id, processed_status FROM attachment_processing
            WHERE user_id = ? AND thread_id = ?
        ''', (user_id, thread_id))
        
        records = cursor.fetchall()
        
        print(f"✓ Database query successful")
        print(f"  Attachment records: {len(records)}")
        
        for record_id, att_id, status in records:
            print(f"    - {att_id}: {status}")
        
        conn.close()
        
        return len(records) > 0
        
    except Exception as e:
        print(f"❌ Database check failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def manual_reprocess_attachment():
    """Manually reprocess attachment to test flow"""
    print("\n" + "="*80)
    print("5️⃣  MANUAL ATTACHMENT REPROCESSING TEST")
    print("="*80)
    
    user_id = "patilswapnil5090@gmail.com"
    thread_id = "19bdef3df3674e27"
    message_id = "19bdef43712fd2bb"
    attachment_path = "/home/ubuntu/openmailbot/openmailbot/agent/data/patilswapnil5090@gmail.com/store_attachments/19bdef3df3674e27/19bdef43712fd2bb_Hotel Appointment Booking Website 2.pdf"
    attachment_id = "19bdef43712fd2bb_Hotel Appointment Booking Website 2.pdf"
    
    try:
        pipeline = ChatWithThreadPipeline(user_id=user_id)
        
        print(f"Reprocessing attachment...")
        print(f"  User: {user_id}")
        print(f"  Thread: {thread_id}")
        print(f"  Attachment: {attachment_id}")
        
        # Clear existing records
        user_db = os.path.join("/home/ubuntu/openmailbot/openmailbot/agent/data", user_id, "sql_data", "chat_thread_processing.db")
        if os.path.exists(user_db):
            conn = sqlite3.connect(user_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM attachment_processing
                WHERE user_id = ? AND thread_id = ? AND attachment_id = ?
            ''', (user_id, thread_id, attachment_id))
            
            conn.commit()
            conn.close()
            print("  ✓ Cleared previous records from DB")
        
        # Process attachment
        pipeline.process_attachment(user_id, thread_id, message_id, attachment_path, attachment_id)
        
        print("  ✓ Attachment processed successfully!")
        
        # Verify storage
        collection = pipeline.get_user_collection(user_id)
        results = collection.get(
            where={
                "$and": [
                    {"thread_id": thread_id},
                    {"attachment_id": attachment_id},
                    {"type": "attachment_data"}
                ]
            }
        )
        
        chunk_count = len(results.get("ids", []))
        print(f"\n  ✓ Chunks stored: {chunk_count}")
        
        if chunk_count > 0:
            for idx, metadata in enumerate(results.get("metadatas", [])[:2]):
                print(f"\n    Chunk {idx}:")
                print(f"      - Filename: {metadata.get('filename')}")
                print(f"      - Size: {len(metadata.get('document', ''))} chars")
                print(f"      - Preview: {metadata.get('document', '')[:80]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Reprocessing failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_search():
    """Test if embeddings can be searched"""
    print("\n" + "="*80)
    print("6️⃣  SEARCH FUNCTIONALITY TEST")
    print("="*80)
    
    user_id = "patilswapnil5090@gmail.com"
    thread_id = "19bdef3df3674e27"
    
    try:
        pipeline = ChatWithThreadPipeline(user_id=user_id)
        
        query = "hotel booking appointment"
        print(f"Searching for: '{query}'")
        
        result = pipeline._search_attachments_internal(user_id, thread_id, query, k=3)
        
        print(f"✓ Search completed")
        print(f"\nResults:\n{result[:500]}...")
        
        if "No relevant information" in result:
            print("\n⚠️  No results found - embeddings may not be properly stored")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Search test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\n" + "#"*80)
    print("# ATTACHMENT EMBEDDING DIAGNOSTIC & REMEDIATION")
    print("#"*80)
    
    results = {
        "pdf_extraction": check_pdf_extraction(),
        "embedding_api": check_embedding_api(),
        "chromadb_storage": check_chromadb_storage(),
        "database_tracking": check_database_records(),
        "search_test": test_search(),
    }
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    for check, result in results.items():
        status = "✓" if result is True else ("?" if result is None else "✗")
        print(f"{status} {check.replace('_', ' ').title()}: {result}")
    
    # If all checks pass, offer to reprocess
    if results["pdf_extraction"] and results["embedding_api"] and results["chromadb_storage"]:
        print("\n" + "="*80)
        print("ATTEMPTING MANUAL REPROCESSING...")
        print("="*80)
        reprocess_result = manual_reprocess_attachment()
        
        if reprocess_result:
            print("\n✅ REPROCESSING SUCCESSFUL!")
            print("   Attachment embeddings should now be searchable.")
    
    print("\n" + "#"*80)
    print("# RECOMMENDATIONS")
    print("#"*80)
    
    if not results["pdf_extraction"]:
        print("→ Install PDF extraction tools: pip install pypdf pdfplumber")
    
    if not results["embedding_api"]:
        print("→ Check FLASK_URL and FLASK_EMBED_URL in config.json")
        print("→ Ensure Flask embeddings service is running")
    
    if results["pdf_extraction"] and results["embedding_api"]:
        print("→ Run: python debug_attachment_embedding.py")
        print("→ Then reprocess threads in your application")

if __name__ == "__main__":
    main()
