#!/usr/bin/env python3
"""
Debug script to diagnose attachment embedding issues
"""

import os
import json
import sys
from pathlib import Path
from llama_index.core import SimpleDirectoryReader
from llama_index.readers.file import PDFReader, CSVReader, PptxReader

# Add agent to path
sys.path.insert(0, "/home/ubuntu/openmailbot/openmailbot/agent")

from services.chat_pipeline import ChatWithThreadPipeline

FILE_EXTRACTOR = {
    ".pdf": PDFReader(),
    ".csv": CSVReader(),
    ".pptx": PptxReader(),
    ".ppt": PptxReader(),
}

def debug_attachment_extraction():
    """Test attachment content extraction"""
    
    user_id = "patilswapnil5090@gmail.com"
    thread_id = "19bdef3df3674e27"
    attachment_path = "/home/ubuntu/openmailbot/openmailbot/agent/data/patilswapnil5090@gmail.com/store_attachments/19bdef3df3674e27/19bdef43712fd2bb_Hotel Appointment Booking Website 2.pdf"
    
    print("=" * 80)
    print("🔍 ATTACHMENT EMBEDDING DEBUG")
    print("=" * 80)
    
    # Check 1: File exists?
    print(f"\n✓ File exists: {os.path.exists(attachment_path)}")
    print(f"  Path: {attachment_path}")
    if os.path.exists(attachment_path):
        file_size = os.path.getsize(attachment_path)
        print(f"  Size: {file_size} bytes")
    
    # Check 2: Try extracting content with SimpleDirectoryReader
    print(f"\n🔄 Attempting content extraction...")
    try:
        documents = SimpleDirectoryReader(
            input_files=[attachment_path],
            file_extractor=FILE_EXTRACTOR
        ).load_data()
        
        print(f"✓ Documents loaded: {len(documents)} document(s)")
        
        if documents:
            for idx, doc in enumerate(documents):
                text_length = len(doc.text) if doc.text else 0
                print(f"\n  📄 Document {idx}:")
                print(f"     - Text length: {text_length} characters")
                print(f"     - Metadata: {doc.metadata if hasattr(doc, 'metadata') else 'None'}")
                
                if text_length > 0:
                    print(f"     - Preview (first 200 chars):")
                    print(f"       {doc.text[:200]}...")
                else:
                    print(f"     ⚠️  WARNING: Document has NO text content!")
        else:
            print("⚠️  WARNING: No documents extracted from file!")
            
    except Exception as e:
        print(f"✗ Content extraction FAILED: {e}")
        import traceback
        traceback.print_exc()
    
    # Check 3: Try embedding API
    print(f"\n🔄 Testing embedding API...")
    try:
        pipeline = ChatWithThreadPipeline(user_id=user_id)
        
        # Test with sample text
        test_text = "This is a test embedding"
        embedding = pipeline.call_embed_api(test_text)
        
        print(f"✓ Embedding API works!")
        print(f"  Embedding dimension: {len(embedding)}")
        print(f"  Sample values: {embedding[:5]}")
        
    except Exception as e:
        print(f"✗ Embedding API FAILED: {e}")
        import traceback
        traceback.print_exc()
    
    # Check 4: Check ChromaDB storage
    print(f"\n🔄 Checking ChromaDB storage...")
    try:
        pipeline = ChatWithThreadPipeline(user_id=user_id)
        collection = pipeline.get_user_collection(user_id)
        
        # Query for attachment data from this thread
        results = collection.get(
            where={
                "$and": [
                    {"thread_id": thread_id},
                    {"type": "attachment_data"}
                ]
            },
            include=["documents", "metadatas"]
        )
        
        num_attachments = len(results.get("ids", []))
        print(f"✓ ChromaDB query successful!")
        print(f"  Stored attachment chunks: {num_attachments}")
        
        if num_attachments > 0:
            metadatas = results.get("metadatas", [])
            for idx, meta in enumerate(metadatas[:3]):  # Show first 3
                print(f"\n  📌 Chunk {idx}:")
                print(f"     - Filename: {meta.get('filename')}")
                print(f"     - Chunk index: {meta.get('chunk_index')}")
                print(f"     - Document preview: {meta.get('document', '')[:100]}...")
        else:
            print("⚠️  WARNING: No attachment data stored in ChromaDB!")
            
    except Exception as e:
        print(f"✗ ChromaDB check FAILED: {e}")
        import traceback
        traceback.print_exc()
    
    # Check 5: Verify metadata file
    print(f"\n🔄 Checking metadata file...")
    metadata_path = "/home/ubuntu/openmailbot/openmailbot/agent/data/patilswapnil5090@gmail.com/store_attachments/19bdef3df3674e27/19bdef43712fd2bb_metadata.json"
    
    try:
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        print(f"✓ Metadata file loaded")
        print(f"  Attachments in metadata: {len(metadata.get('attachments', []))}")
        
        for att in metadata.get('attachments', []):
            print(f"\n  📎 {att.get('filename')}")
            print(f"     - Size: {att.get('size')} bytes")
            print(f"     - MIME type: {att.get('mime_type')}")
            
            if 'error' in att:
                print(f"     - ERROR: {att['error']}")
            
    except Exception as e:
        print(f"✗ Metadata check FAILED: {e}")
    
    print("\n" + "=" * 80)
    print("📋 SUMMARY")
    print("=" * 80)
    print("""
Possible causes of embedding failure:

1. ✓ File extraction: PDFReader not extracting text properly
   → Check if pypdf or pdfplumber is installed
   → Check if PDF is password-protected or image-only

2. ✓ Empty documents: SimpleDirectoryReader returns docs with no text
   → Check doc.text length after extraction

3. ✓ Embedding API: call_embed_api() returns errors silently
   → Check FLASK_EMBED_URL is accessible
   → Check request/response format

4. ✓ ChromaDB storage: Embeddings not being stored
   → Check if collection.add() is failing silently
   → Check metadata structure

5. ✓ Search retrieval: Embeddings stored but search fails
   → Check if where clause matches metadata
   → Check if search query returns empty results
    """)

if __name__ == "__main__":
    debug_attachment_extraction()
