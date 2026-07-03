# Tone Pipeline Integration with Draft Pipeline

## Overview

The draft pipeline has been enhanced with tone-aware drafting capabilities. When generating an email reply, the system now:

1. **Identifies the recipient** from the email thread
2. **Retrieves the user's tone profile** for that recipient from the tone database
3. **Builds a style card** with aggregate tone metrics and recent examples
4. **Injects this context** into the LLM prompt to generate tone-matched replies

This ensures generated drafts maintain consistency with the user's established writing style and relationship level with each recipient.

## Architecture

### Data Flow

```
┌─ DraftPipeline initialized
├─ Loads SettingsManager → gets user LLM settings
├─ Loads TonePipelineManager → access to tone_db/ per-user
│
├─ process_email_request() called
├─ Load email thread JSON
├─ Extract attachments (CSV, PDF, etc.)
│
├─ _extract_primary_recipient()
│  └─ Find main correspondent from thread
│
├─ _build_tone_context()
│  ├─ Get aggregate profile from SQLite
│  ├─ Get recent 3 emails from ChromaDB
│  └─ Build style card
│
├─ generate_draft()
│  ├─ Inject tone context into system prompt
│  ├─ Call LLMService with tone-aware prompt
│  └─ Return generated draft
│
└─ Return result with processing_info
```

### Settings Manager Integration

```python
# Settings are retrieved the same way as in other pipelines
settings_manager = SettingsManager(user_id)
retrieved = settings_manager.get_settings(setting_type="general")
self.effective_settings = retrieved if retrieved else {}

# Passed to LLMService
self.llm_service = LLMService(effective_settings=self.effective_settings)
```

### Tone Manager Integration

```python
# Initialize TonePipelineManager (similar to SettingsManager)
tone_base_dir = os.path.join(...)  # backend/data
self.tone_manager = TonePipelineManager(user_id, tone_base_dir)

# Extract recipient and build tone context
recipient = self._extract_primary_recipient(thread_data)
tone_context = self._build_tone_context(recipient)

# Pass to generate_draft
draft = await self.generate_draft(
    email_data, attachment_context, thread_id,
    user_preferences,
    tone_context=tone_context  # NEW parameter
)
```

## Implementation Details

### 1. TonePipelineManager Initialization

**Location**: `DraftPipeline.__init__()`

```python
self.tone_manager = TonePipelineManager(user_id, tone_base_dir) if user_id else None
```

- Initialized per-user when DraftPipeline is created
- Non-fatal if initialization fails (drafting continues without tone context)
- Automatically creates `data/{user_id}/tone_db/` on first use

### 2. Recipient Extraction

**Method**: `_extract_primary_recipient(thread_data: Dict) -> Optional[str]`

Extracts the primary correspondent from the email thread:

```python
def _extract_primary_recipient(self, thread_data: Dict) -> Optional[str]:
    """
    Find the primary recipient from the thread.
    
    Logic:
    - Get most recent message where from != user_id
    - Return that person's email address
    """
    messages = thread_data.get('messages', [])
    for msg in reversed(messages):
        sender = msg.get('from', '').strip().lower()
        if sender and sender != self.user_id.lower():
            return msg.get('from')
    return None
```

**Returns**: Email address of primary correspondent, or None

### 3. Tone Context Building

**Method**: `_build_tone_context(recipient: str) -> str`

Retrieves and formats tone profile:

```python
def _build_tone_context(self, recipient: str) -> str:
    profile = self.tone_manager.get_style_profile_stats(recipient)
    recent_emails = self.tone_manager.get_recent_emails_for_recipient(recipient, n_results=3)
    tone_context = self._build_style_card(recipient, profile, recent_emails)
    return tone_context
```

**Returns**: Formatted style card string (or empty string if no profile)

### 4. Style Card Building

**Method**: `_build_style_card(recipient: str, profile: Dict, few_shot_examples: List[Dict]) -> str`

Formats tone data for system prompt:

```
━━━ TONE CONTEXT (based on 12 prior email(s) to this recipient) ━━━

Relationship: Professor (authority: Higher)

Writing Style:
  • tone: Formal
  • politeness: Very Polite
  • warmth: Neutral
  • directness: Indirect
  • professionalism: High
  • respectfulness: High

Recent examples of how you write to this recipient:
  [1] Dear Professor Sharma, thank you for your feedback. I have revised...
  [2] Thank you for taking the time to meet with me yesterday...
  [3] I am writing to request a brief extension...

━━━ END TONE CONTEXT ━━━
```

Features:
- Shows relationship type and authority level
- Lists writing style dimensions
- Flags "variable" dimensions if tone fluctuates
- Includes 3 recent email examples for few-shot learning

### 5. LLM Prompt Injection

**Method**: `generate_draft(..., tone_context: str = None)`

Tone context is injected into system prompt:

```python
system_prompt = f"""You are an AI email assistant...

[standard guidelines]

Output: A professional, concise, context-aware email reply...
"""

# Inject tone context if available
if tone_context:
    system_prompt += f"\n\n{tone_context}\n\n"
    system_prompt += "IMPORTANT: When drafting the reply, match the recipient-specific tone and style shown above."
```

**Effect**: LLM generates drafts that match the user's established writing style with that specific recipient

## Usage

### From API Call

```python
# Initialize pipeline
pipeline = DraftPipeline(user_id="student@university.edu")

# Process request
result = await pipeline.process_email_request(
    user_id="student@university.edu",
    thread_id="thread_abc123",
    user_preferences={
        "name": "Aditya",
        "position": "Graduate Student",
        "tone": "academic and formal",
        "custom_instructions": "Use proper citations"
    }
)

# Returns
{
    "success": True,
    "draft_content": "Dear Professor Sharma, thank you for your feedback...",
    "processing_info": {
        "attachments_found": 2,
        "tone_profile": {
            "recipient": "prof.sharma@university.edu",
            "has_context": True
        }
    }
}

# Clean up
pipeline.close()
```

### Error Handling

All tone operations are **non-fatal**:

```python
try:
    tone_context = self._build_tone_context(recipient)
except Exception as e:
    logger.warning(f"Tone extraction failed: {e}")
    tone_context = ""  # Continue with empty context

# Draft generation proceeds with or without tone context
draft = await self.generate_draft(..., tone_context=tone_context)
```

## Tone Profile Data Structure

### Retrieved from SQLite (get_all_emails_for_recipient)

```python
{
    "id": "msg_123",
    "recipient": "prof.sharma@university.edu",
    "email_text": "Dear Professor...",
    "relationship_type": "Professor",
    "familiarity": "Established",
    "authority": "Higher",
    "tone": "Formal",
    "politeness": "Very Polite",
    "warmth": "Neutral",
    "directness": "Indirect",
    "professionalism": "High",
    "respectfulness": "High",
    "confidence": "Moderate",
    "created_at": 1719014400.0
}
```

### Aggregate Profile (get_style_profile_stats)

```python
{
    "n_emails_observed": 12,
    "relationship_type": "Professor",
    "familiarity": "Established",
    "authority": "Higher",
    "tone": {
        "label": "Formal",
        "score": 2.5,
        "variance": 0.02,
        "stability": "stable"
    },
    "politeness": {
        "label": "Very Polite",
        "score": 3.1,
        "variance": 0.08,
        "stability": "stable"
    },
    # ... other style attributes
}
```

## Processing Info Output

The `processing_info` dict in the response includes tone data:

```python
{
    "attachments_found": 2,
    "tone_profile": {
        "recipient": "prof.sharma@university.edu",
        "has_context": True
    },
    "errors": []
}
```

Or if no recipient found:

```python
{
    "attachments_found": 0,
    "tone_profile": None,
    "errors": []
}
```

## Error Scenarios

### No Tone Manager

```python
if not self.tone_manager:
    tone_context = ""
    # Drafting continues with generic system prompt
```

**Trigger**: If `TonePipelineManager` fails to initialize (non-fatal)

### No Recipient Detected

```python
recipient = self._extract_primary_recipient(thread_data)
if not recipient:
    tone_context = ""
    # Drafting continues with generic system prompt
```

**Trigger**: If thread has no external sender (rare)

### No Tone Profile

```python
profile = self.tone_manager.get_style_profile_stats(recipient)
if not profile or profile.get('n_emails_observed', 0) == 0:
    tone_context = ""
    # First email or tone not yet captured
```

**Trigger**: First email to a new recipient (no historical data)

### Build Tone Context Fails

```python
try:
    tone_context = self._build_tone_context(recipient)
except Exception as e:
    logger.warning(f"Failed to build tone context: {e}")
    tone_context = ""
    # Drafting continues
```

**Trigger**: Database access errors, malformed profiles

## Performance Considerations

### Database Queries

- **SQLite read**: `O(log n)` — indexed on recipient
- **ChromaDB query**: `O(1)` — only 3 docs per recipient (fixed size)
- **Total overhead**: ~10-50ms depending on database size

### LLM Impact

- **Token cost**: +200-400 tokens for tone context (few examples + profile)
- **Generation time**: Negligible (modern LLMs handle context easily)
- **Quality gain**: Significant (tone-matched replies instead of generic)

## Integration Checklist

✅ Import `TonePipelineManager` in `draft_pipeline.py`  
✅ Initialize in `__init__()` with user_id and base data dir  
✅ Extract recipient from thread data  
✅ Build tone context from profile + recent emails  
✅ Inject into system prompt with clear instructions  
✅ Pass through `generate_draft()` parameter  
✅ Include tone profile info in response  
✅ Handle all error scenarios gracefully  
✅ Close tone_manager on pipeline destruction  
✅ Non-fatal errors logged only (don't break pipeline)  

## Testing

### Unit Test Structure

```python
# Test with mock tone profile
mock_profile = {
    "n_emails_observed": 5,
    "relationship_type": "Friend",
    "tone": {"label": "Casual"}
}

# Test recipient extraction
recipient = pipeline._extract_primary_recipient(thread_data)
assert recipient == "friend@gmail.com"

# Test style card building
style_card = pipeline._build_style_card(recipient, mock_profile, [])
assert "Friend" in style_card
assert "Casual" in style_card

# Test full flow
result = await pipeline.process_email_request(user_id, thread_id, prefs)
assert result["success"] == True
assert result["processing_info"]["tone_profile"]["recipient"] is not None
```

### Integration Test

```python
# Full pipeline with real tone data
pipeline = DraftPipeline(user_id="student@university.edu")
result = await pipeline.process_email_request(
    user_id="student@university.edu",
    thread_id="real_thread_id",
    user_preferences={"name": "Aditya"}
)

# Verify draft respects tone
assert "Dear Professor" in result["draft_content"]  # Formal, not "Hey Prof"
assert result["processing_info"]["tone_profile"]["has_context"] == True
```

## Migration Guide

### For Existing Code

No breaking changes. Existing calls work as-is:

```python
# Old code still works
draft = await pipeline.generate_draft(email_data, attachment_context, thread_id)

# New code with tone
draft = await pipeline.generate_draft(
    email_data, attachment_context, thread_id,
    tone_context=tone_context  # Optional parameter
)
```

### For New Features

Always extract recipient and build tone context:

```python
# Step 1: Extract recipient
recipient = pipeline._extract_primary_recipient(thread_data)

# Step 2: Build tone context (non-fatal if fails)
tone_context = pipeline._build_tone_context(recipient) if recipient else ""

# Step 3: Pass to generate_draft
draft = await pipeline.generate_draft(
    email_data, attachment_context, thread_id,
    user_preferences, tone_context=tone_context
)
```

## Related Files

- [EMAIL_TONE_INTEGRATION.md](EMAIL_TONE_INTEGRATION.md) — Tone pipeline architecture
- `agent/services/email_tone_pipeline.py` — Core tone service
- `agent/services/draft_pipeline.py` — Draft service (updated)
- `backend/main.py` — Label API that triggers tone capture

## FAQ

**Q: What if tone profile doesn't exist yet?**  
A: Drafting continues with generic system prompt (no error)

**Q: Does tone context slow down generation?**  
A: Minimal impact (~10-50ms for DB queries, negligible for LLM)

**Q: Can I turn off tone context?**  
A: Pass empty string for `tone_context` parameter

**Q: What if recipient is ambiguous?**  
A: Uses most recent external sender from thread

**Q: Does tone context work for all LLM providers?**  
A: Yes, it's injected into the system prompt (provider-agnostic)

---

**Status**: ✅ Production Ready  
**Last Updated**: 2026-07-03  
**Integration**: Complete (tone capture + draft enhancement)
