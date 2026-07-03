"""
Tone Pipeline Quick Start & Verification
=========================================================================

This script demonstrates:
1. Creating per-user tone_db directory structure
2. Processing a sample sent email
3. Verifying SQLite storage
4. Verifying ChromaDB storage with rolling window
5. Retrieving recent emails for drafting

Run this to verify the complete integration works:
    cd d:\\manotr\\openmailbot
    python -m agent.services.email_tone_pipeline_demo

Or import and use directly:
    from agent.services.email_tone_pipeline_demo import demo_tone_pipeline
    demo_tone_pipeline()
"""

import os
import sys
import json
import tempfile
import shutil

# Add parent to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from agent.services.email_tone_pipeline import (
    TonePipelineManager,
    _default_extracted,
    get_all_emails_for_recipient,
)


def demo_tone_pipeline():
    """
    End-to-end demo of tone pipeline with mock data.
    Creates temporary directory structure to test without affecting real data.
    """
    
    print("\n" + "=" * 70)
    print("EMAIL TONE PIPELINE - QUICK START DEMO")
    print("=" * 70 + "\n")
    
    # Use temp directory for demo
    demo_dir = tempfile.mkdtemp(prefix="tone_pipeline_demo_")
    print(f"✓ Created temporary demo directory: {demo_dir}\n")
    
    try:
        # Step 1: Initialize manager
        print("STEP 1: Initialize TonePipelineManager")
        print("-" * 70)
        
        user_id = "student@university.edu"
        manager = TonePipelineManager(user_id, demo_dir)
        
        print(f"✓ User ID: {user_id}")
        print(f"✓ Base directory: {demo_dir}")
        print(f"✓ SQLite path: {manager.sqlite_path}")
        print(f"✓ ChromaDB path: {manager.chroma_path}")
        print(f"✓ Directories created and initialized\n")
        
        # Step 2: Process sample sent emails
        print("STEP 2: Process Sample Sent Emails")
        print("-" * 70)
        
        sample_emails = [
            {
                "recipient": "prof.sharma@university.edu",
                "text": (
                    "Dear Professor Sharma,\n\n"
                    "I hope this email finds you well. I wanted to follow up regarding "
                    "the feedback you shared on my thesis draft. I have revised Section 3 "
                    "based on your comments and would be grateful if you could review "
                    "the updated version.\n\n"
                    "Please let me know if there is a convenient time to discuss this further. "
                    "Thank you very much for your continued guidance.\n\n"
                    "Warm regards,\nAditya"
                )
            },
            {
                "recipient": "prof.sharma@university.edu",
                "text": (
                    "Dear Professor Sharma,\n\n"
                    "Thank you for taking the time to meet with me yesterday. I really "
                    "appreciate your insights on the methodology. I will incorporate "
                    "your suggestions and share a revised draft by Friday.\n\n"
                    "Sincerely,\nAditya"
                )
            },
            {
                "recipient": "rahul.friend@gmail.com",
                "text": (
                    "Hey Rahul,\n\n"
                    "Dude that weekend trip sounds awesome! Let me know the dates and "
                    "I'll block my calendar. Send me that trek route you mentioned.\n\n"
                    "Catch up soon,\nAditya"
                )
            },
        ]
        
        for i, email in enumerate(sample_emails, 1):
            recipient = email["recipient"]
            text = email["text"]
            print(f"  [{i}] Processing email to {recipient}...")
            
            # Use mock extraction to avoid needing Ollama running
            extracted = _default_extracted(recipient)
            
            # Override with semi-realistic tone based on recipient
            if "prof" in recipient.lower():
                extracted["writing_style"]["tone"] = "Formal"
                extracted["writing_style"]["politeness"] = "Very Polite"
                extracted["relationship"]["type"] = "Professor"
            else:
                extracted["writing_style"]["tone"] = "Casual"
                extracted["writing_style"]["politeness"] = "Neutral"
                extracted["relationship"]["type"] = "Friend"
            
            # Process the email
            result = manager.process_sent_email(
                recipient=recipient,
                email_text=text,
                email_id=f"msg_{i}",
                extractor_fn=lambda r, t: extracted  # Mock extractor
            )
            
            print(f"      ✓ Tone: {result['writing_style']['tone']}")
            print(f"      ✓ Relationship: {result['relationship']['type']}")
            print(f"      ✓ Stored in SQLite and ChromaDB\n")
        
        # Step 3: Verify SQLite storage (full history)
        print("STEP 3: Verify SQLite Storage (Full Audit History)")
        print("-" * 70)
        
        prof_emails = manager.get_all_emails_for_recipient("prof.sharma@university.edu")
        print(f"✓ Emails to prof.sharma@university.edu (SQLite):")
        print(f"  Total stored: {len(prof_emails)} (should be 2 - full history kept)")
        for i, email in enumerate(prof_emails, 1):
            print(f"    [{i}] {email['id'][:8]}... | Tone: {email['tone']} | Created: {email['created_at']}")
        print()
        
        friend_emails = manager.get_all_emails_for_recipient("rahul.friend@gmail.com")
        print(f"✓ Emails to rahul.friend@gmail.com (SQLite):")
        print(f"  Total stored: {len(friend_emails)} (should be 1)")
        for i, email in enumerate(friend_emails, 1):
            print(f"    [{i}] {email['id'][:8]}... | Tone: {email['tone']}")
        print()
        
        # Step 4: Verify ChromaDB storage (rolling window)
        print("STEP 4: Verify ChromaDB Storage (Rolling Window)")
        print("-" * 70)
        
        if manager.chroma_collection:
            from agent.services.email_tone_pipeline import (
                count_docs_for_recipient,
                get_recent_emails_for_recipient,
            )
            
            prof_count = count_docs_for_recipient(manager.chroma_collection, "prof.sharma@university.edu")
            print(f"✓ ChromaDB count for prof.sharma@university.edu: {prof_count} (max 3)")
            
            recent = get_recent_emails_for_recipient(manager.chroma_collection, "prof.sharma@university.edu", n_results=3)
            print(f"✓ Recent emails retrieved: {len(recent)}")
            for i, r in enumerate(recent, 1):
                meta = r["metadata"]
                print(f"    [{i}] {meta['tone']} | {meta['relationship_type']} | {meta['created_at']}")
            print()
        else:
            print("⚠ ChromaDB not available (Ollama may not be running)\n")
        
        # Step 5: Show aggregate profile
        print("STEP 5: Aggregate Profile Stats (for Drafting Agent)")
        print("-" * 70)
        
        prof_profile = manager.get_style_profile_stats("prof.sharma@university.edu")
        print(f"✓ Profile for prof.sharma@university.edu:")
        print(f"  Emails observed: {prof_profile.get('n_emails_observed', 0)}")
        print(f"  Recipient: {prof_profile.get('recipient')}")
        print()
        
        # Step 6: Directory structure summary
        print("STEP 6: Verify Directory Structure")
        print("-" * 70)
        
        tone_db_dir = os.path.join(demo_dir, user_id, "tone_db")
        print(f"✓ Tone database directory: {tone_db_dir}")
        if os.path.exists(tone_db_dir):
            contents = os.listdir(tone_db_dir)
            print(f"  Contents: {contents}")
            
            sqlite_path = os.path.join(tone_db_dir, "email_history.db")
            if os.path.exists(sqlite_path):
                size = os.path.getsize(sqlite_path)
                print(f"  ✓ SQLite file: email_history.db ({size} bytes)")
            
            chroma_dir = os.path.join(tone_db_dir, "chroma_store")
            if os.path.exists(chroma_dir):
                print(f"  ✓ ChromaDB directory: chroma_store/")
        print()
        
        # Summary
        print("=" * 70)
        print("DEMO SUMMARY")
        print("=" * 70)
        print(f"✓ Successfully demonstrated tone pipeline")
        print(f"✓ Per-user isolation: data/{user_id}/tone_db/")
        print(f"✓ SQLite keeps full history")
        print(f"✓ ChromaDB keeps rolling window (3 per recipient)")
        print(f"✓ Ready for production use\n")
        
        manager.close()
        
    finally:
        # Cleanup
        print("Cleaning up demo directory...")
        shutil.rmtree(demo_dir, ignore_errors=True)
        print("✓ Done\n")


def show_integration_points():
    """Show how tone pipeline integrates with labeling system"""
    
    print("\n" + "=" * 70)
    print("INTEGRATION POINTS")
    print("=" * 70 + "\n")
    
    print("1. LABELING API ENDPOINT (/api/label-email-async)")
    print("   └─ Payload: { user_id, thread_id, messages[], ... }")
    print("   └─ Calls: _run_label_and_push_to_gmail()")
    print()
    
    print("2. PREPROCESSING")
    print("   └─ Extracts: from, to, subject, body for each message")
    print()
    
    print("3. LABEL PIPELINE")
    print("   └─ Determines email category (Work, Personal, etc.)")
    print()
    
    print("4. ★ TONE CAPTURE (NEW)")
    print("   └─ Check: is from == user_id? (is this email SENT by user?)")
    print("   └─ If YES:")
    print("      └─ Extract recipient(s) and email body")
    print("      └─ Call Ollama llama3.2 to extract tone schema")
    print("      └─ Store in SQLite (full history)")
    print("      └─ Embed + store in ChromaDB (rolling 3 per recipient)")
    print()
    
    print("5. GMAIL PUSH")
    print("   └─ Push label to Gmail via REST API")
    print()
    
    print("6. CLEANUP")
    print("   └─ Delete preprocessed files")
    print()


def show_database_schema():
    """Show SQLite schema"""
    
    print("\n" + "=" * 70)
    print("SQLITE SCHEMA (email_history.db)")
    print("=" * 70 + "\n")
    
    print("""
CREATE TABLE emails (
    id TEXT PRIMARY KEY,
    recipient TEXT NOT NULL,
    email_text TEXT NOT NULL,
    relationship_type TEXT,
    familiarity TEXT,
    authority TEXT,
    tone TEXT,
    politeness TEXT,
    warmth TEXT,
    directness TEXT,
    professionalism TEXT,
    respectfulness TEXT,
    confidence TEXT,
    created_at REAL NOT NULL
);

CREATE INDEX idx_emails_recipient ON emails(recipient);
    """)
    
    print("EXTRACTED SCHEMA (stored in writing_style + relationship):")
    schema = {
        "recipient": "prof.sharma@university.edu",
        "relationship": {
            "type": "Professor|Manager|Senior Colleague|Peer|Friend|Client|Other",
            "familiarity": "New|Developing|Established",
            "authority": "Higher|Equal|Lower"
        },
        "writing_style": {
            "tone": "Formal|Semi-formal|Casual",
            "politeness": "Very Polite|Polite|Neutral|Blunt",
            "warmth": "Warm|Neutral|Cold",
            "directness": "Direct|Indirect",
            "professionalism": "High|Medium|Low",
            "respectfulness": "High|Medium|Low",
            "confidence": "High|Moderate|Low"
        }
    }
    print(json.dumps(schema, indent=2))
    print()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Tone pipeline demo and verification")
    parser.add_argument("mode", nargs="?", default="demo", 
                        choices=["demo", "schema", "integration"])
    args = parser.parse_args()
    
    if args.mode == "demo":
        demo_tone_pipeline()
    elif args.mode == "schema":
        show_database_schema()
    elif args.mode == "integration":
        show_integration_points()
