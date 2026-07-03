"""
Email Tone Pipeline - Integration Guide & Architecture
=======================================================================

OVERVIEW
The email tone/relationship personalization pipeline captures and stores the user's
writing style when they send emails. This data is later used by the drafting agent
to generate replies that match the user's established tone with each recipient.

ARCHITECTURE
=========================================================================

Per-User Data Structure:
    data/
    └── {user_id}/
        ├── sql_data/                    ← Chat/Draft processing (existing)
        │   ├── chat_thread_processing.db
        │   └── draft_processing.db
        ├── tone_db/                     ← NEW: Tone pipeline storage
        │   ├── email_history.db         ← Full audit history (SQLite)
        │   └── chroma_store/            ← Rolling embeddings (ChromaDB)
        │       └── ... (ChromaDB internals)
        ├── log_emails/                  ← Preprocessed emails (existing)
        ├── store_attachments/           ← Email attachments (existing)
        └── vector_db/                   ← Email embeddings (existing)


FLOW
=========================================================================

1. EMAIL RECEIVED → Labeling API Called
   ├─ POST /api/label-email-async
   └─ Payload: { user_id, thread_id, messages[], access_token, ... }

2. PREPROCESSING
   ├─ Extract from, to, subject, body for each message
   └─ Normalize thread_id for consistent keying

3. LABEL PIPELINE
   ├─ Run LLM-based label classification
   └─ Determine email category (e.g., "Work", "Personal", etc.)

4. ★ TONE CAPTURE (NEW) ★
   ├─ Check each message: is from == user_id?
   ├─ If YES → extract recipient(s) and email body
   ├─ Call Ollama llama3.2 to extract structured tone:
   │   └─ relationship (type, familiarity, authority)
   │   └─ writing_style (tone, politeness, warmth, directness, etc.)
   ├─ Store in SQLite email_history.db (full audit)
   ├─ Embed with nomic-embed-text → ChromaDB
   ├─ Enforce: only 3 most recent emails per recipient kept in ChromaDB
   └─ All errors are non-fatal (don't break labeling)

5. GMAIL PUSH
   ├─ Push label to Gmail via REST API
   └─ User sees it in their inbox

6. CLEANUP
   └─ Delete preprocessed email files after pipeline completes


TONE EXTRACTION SCHEMA
=========================================================================

Extracted by llama3.2 for each sent email:

{
  "recipient": "prof.sharma@university.edu",
  "relationship": {
    "type": "<Professor|Manager|Senior Colleague|Peer|Friend|Client|Other>",
    "familiarity": "<New|Developing|Established>",
    "authority": "<Higher|Equal|Lower>"
  },
  "writing_style": {
    "tone": "<Formal|Semi-formal|Casual>",
    "politeness": "<Very Polite|Polite|Neutral|Blunt>",
    "warmth": "<Warm|Neutral|Cold>",
    "directness": "<Direct|Indirect>",
    "professionalism": "<High|Medium|Low>",
    "respectfulness": "<High|Medium|Low>",
    "confidence": "<High|Moderate|Low>"
  }
}

DATABASE SCHEMA - SQLite (email_history.db)
=========================================================================

Table: emails
  id                  TEXT PRIMARY KEY (UUID)
  recipient           TEXT NOT NULL (email address)
  email_text          TEXT NOT NULL (full email body)
  relationship_type   TEXT (Professor|Manager|...)
  familiarity         TEXT (New|Developing|Established)
  authority           TEXT (Higher|Equal|Lower)
  tone                TEXT (Formal|Semi-formal|Casual)
  politeness          TEXT (Very Polite|Polite|Neutral|Blunt)
  warmth              TEXT (Warm|Neutral|Cold)
  directness          TEXT (Direct|Indirect)
  professionalism     TEXT (High|Medium|Low)
  respectfulness      TEXT (High|Medium|Low)
  confidence          TEXT (High|Moderate|Low)
  created_at          REAL (Unix timestamp)

Index: idx_emails_recipient (for fast per-recipient queries)


DATABASE SCHEMA - ChromaDB (chroma_store/)
=========================================================================

Collection: recipient_style_emails
  Storage: Vector embeddings (nomic-embed-text:latest)
  Retention: Only 3 most recent emails per recipient
  
  Document: email_text (the full email body, embedded)
  Metadata: 
    - recipient (email address)
    - created_at (Unix timestamp, used for sorting)
    - relationship_type, familiarity, authority, tone, politeness, warmth, etc.
    - extracted_json (full extraction as JSON string)


USAGE FROM CODE
=========================================================================

Standalone (for testing):

    from agent.services.email_tone_pipeline import TonePipelineManager
    
    manager = TonePipelineManager(
        user_id="student@university.edu",
        base_data_dir="/path/to/data"
    )
    
    extracted = manager.process_sent_email(
        recipient="prof.sharma@university.edu",
        email_text="Dear Professor Sharma, thank you for..."
    )
    
    # extracted = {
    #   "recipient": "prof.sharma@university.edu",
    #   "relationship": {"type": "Professor", "familiarity": "Established", ...},
    #   "writing_style": {"tone": "Formal", "politeness": "Very Polite", ...}
    # }
    
    manager.close()


From Labeling Pipeline (automatic):

    # Called automatically in _run_label_and_push_to_gmail()
    tone_result = _capture_tone_for_sent_emails(
        user_id=request.user_id,
        thread_id=thread_id,
        processed_messages=processed_messages,
        logger=logger
    )
    
    # tone_result = {
    #   "captured": 2,  ← 2 sent emails processed
    #   "errors": [],
    #   "details": [
    #     {"recipient": "...", "tone": "Formal", "relationship": "Professor"},
    #     {"recipient": "...", "tone": "Casual", "relationship": "Friend"}
    #   ]
    # }


RETRIEVAL FOR DRAFTING AGENT
=========================================================================

Later, when the drafting agent needs to write a reply:

    manager = TonePipelineManager(user_id="student@university.edu", ...)
    
    # Get full history (for aggregate profiling)
    all_emails = manager.get_all_emails_for_recipient("prof.sharma@university.edu")
    
    # Get recent 3 examples (for few-shot examples in prompt)
    recent = manager.get_recent_emails_for_recipient("prof.sharma@university.edu", n_results=3)
    
    # Get aggregate profile (recency-weighted stats)
    profile = manager.get_style_profile_stats("prof.sharma@university.edu")


OLLAMA REQUIREMENTS
=========================================================================

For full functionality (automatic tone extraction):

    # Install & run Ollama locally
    ollama pull llama3.2
    ollama pull nomic-embed-text:latest
    ollama serve
    
    # Verify running at http://localhost:11434


FALLBACK BEHAVIOR
=========================================================================

If Ollama is unavailable:
  ✓ Tone pipeline gracefully falls back to safe defaults
  ✓ Labeling pipeline still completes successfully
  ✓ No exceptions propagate to the caller
  ✓ Error is logged as WARNING (non-fatal)

This allows the system to work in any environment (CI, sandbox, etc.)
without requiring a live LLM server.


INTEGRATION POINTS
=========================================================================

1. main.py: /api/label-email-async endpoint
   └─ Calls _capture_tone_for_sent_emails() after label is determined
   └─ Non-fatal errors logged only, don't break the flow

2. main.py: _run_label_and_push_to_gmail() background task
   └─ Orchestrates the full label + tone pipeline
   └─ Called via BackgroundTasks.add_task()

3. email_tone_pipeline.py: TonePipelineManager class
   └─ Per-user manager for tone storage/retrieval
   └─ Handles SQLite + ChromaDB initialization
   └─ Enforces per-recipient rolling window (3 emails max per recipient)


TESTING
=========================================================================

Unit tests included in email_tone_pipeline.py:

    python email_tone_pipeline.py test
    
  - Verifies SQLite storage (full history kept)
  - Verifies ChromaDB eviction (only 3 per recipient in Chroma)
  - Tests extraction schema validation
  - Tests per-recipient isolation
  
Note: Tests SKIP (not fail) if Ollama server/model is unavailable.


ADMIN NOTES
=========================================================================

Database Cleanup:
  - SQLite: rm data/{user_id}/tone_db/email_history.db
  - ChromaDB: rm -rf data/{user_id}/tone_db/chroma_store

Exporting History:
  - All tone data is in SQLite (full audit trail)
  - Query: SELECT * FROM emails WHERE recipient = ?
  - Use standard Python sqlite3 module

Monitoring:
  - Check /api/label-email/metrics for labeling counts
  - Check application logs for [tone] capture status
  - ChromaDB logs stored in chroma_store/logs/ (if configured)


=======================================================================
End of Integration Guide
"""
