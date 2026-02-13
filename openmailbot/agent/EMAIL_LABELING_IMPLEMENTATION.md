# Email Preprocessing and Labeling Pipeline

## Overview

This implementation adds two new pipelines to the OpenMailBot agent:

1. **Email Preprocessing Pipeline** - Cleans and deduplicates email content
2. **Email Label Pipeline** - Automatically categorizes emails using rules and LLM

## What Was Created

### 1. Preprocessing Pipeline (`agent/services/preprocessing_emails.py`)

**Purpose**: Clean raw email data before storage or analysis

**Features**:
- Removes HTML tags, scripts, and styles
- Strips all URLs and links
- Removes email disclaimers and signatures
- Extracts only new content (removes quoted/nested emails)
- Normalizes whitespace

**Usage**:
```python
from services.preprocessing_emails import EmailPreprocessingPipeline

pipeline = EmailPreprocessingPipeline()
processed_messages = pipeline.process(raw_messages)
```

### 2. Label Pipeline (`agent/services/label_pipeline.py`)

**Purpose**: Automatically categorize emails into predefined labels

**Approach**:
- **Rule-based first**: Fast pattern matching for common cases
- **LLM fallback**: Uses GPT-4o-mini for complex cases
- **Structured output**: Uses Pydantic and Langchain for reliable results

**Labels** (10 categories):
- `finance` - Invoices, payments, billing
- `meeting` - Meetings, calendar, scheduling
- `fyi` - Information only, no action needed
- `awaiting_reply` - Waiting for response
- `urgent` - Time-sensitive matters
- `action_required` - Tasks needing action
- `newsletter` - Newsletters, announcements
- `social` - Social media notifications
- `promotion` - Marketing emails, offers
- `general` - General correspondence

**Rule Examples**:
```python
# Rule 1: Subject contains ["invoice", "payment"] → finance
# Rule 2: Subject contains ["meeting", "schedule"] → meeting
# Rule 3: Body contains "FYI" → fyi
# Rule 4: Subject starts with "Re:" → awaiting_reply
# Rule 5: Subject contains "urgent" → urgent
# ... (10 rules total)
```

**Usage**:
```python
from services.label_pipeline import EmailLabelPipeline

pipeline = EmailLabelPipeline(openai_api_key="sk-...")
label = pipeline.label_email(email_data)
# Returns: "meeting"
```

### 3. New API Endpoint: `/api/label-email`

**Purpose**: Label email threads by processing them through both pipelines

**Request**:
```json
{
  "user_id": "user@example.com",
  "thread_id": "thread_xxx",
  "messages": [
    {
      "message_id": "msg_123",
      "from_address": "sender@example.com",
      "to": ["recipient@example.com"],
      "subject": "Invoice #12345",
      "timestamp": "2026-02-06T10:00:00Z",
      "body": "<html>...</html>"
    }
  ]
}
```

**Response**:
```json
{
  "success": true,
  "label": "finance",
  "user_id": "user@example.com",
  "thread_id": "thread_xxx",
  "messages_processed": 1,
  "classification_method": "rule-based"
}
```

**Processing Flow**:
1. Receives raw email messages
2. Converts to dict format
3. **Preprocessing**: Cleans HTML, removes quotes, etc.
4. **Labeling**: Applies rules first, falls back to LLM if needed
5. **Focus on last message**: For threads, the most recent message determines the label
6. Returns single label string

**Key Features**:
- ✅ Handles multiple messages (uses last message for threads)
- ✅ Works without OpenAI API key (rule-based only mode)
- ✅ Tries to get API key from user settings if not in environment
- ✅ Detailed logging for debugging
- ✅ Returns classification method used (rule-based vs llm)

## Testing

Run the test script to verify functionality:

```bash
cd /home/ubuntu/openmailbot/openmailbot/agent
python test_label_pipeline.py
```

**Test coverage**:
- ✅ Email preprocessing (HTML cleaning, deduplication)
- ✅ Rule-based labeling (10 rules)
- ✅ Thread labeling (focuses on last message)
- ✅ LLM labeling (requires `OPENAI_API_KEY`)

## Configuration

### OpenAI API Key

The label pipeline tries to get the API key in this order:

1. Environment variable: `OPENAI_API_KEY`
2. User settings: `llm_api_key` or `openai_api_key`
3. If no key found: Uses rule-based only (no error)

Set the API key:

```bash
export OPENAI_API_KEY="sk-..."
```

Or configure in user settings via `/api/settings` endpoint.

## Integration Points

### Updated Files:
1. ✅ `agent/services/preprocessing_emails.py` - NEW
2. ✅ `agent/services/label_pipeline.py` - NEW
3. ✅ `agent/services/__init__.py` - Updated imports
4. ✅ `agent/main.py` - Added imports and `/api/label-email` route
5. ✅ `agent/test_label_pipeline.py` - NEW test file

### Dependencies:
All required packages already in `requirements.txt`:
- ✅ `langchain==0.0.340`
- ✅ `langchain-openai==0.1.0`
- ✅ `pydantic==2.5.0`
- ✅ `openai==1.3.5`

## Example Usage

### Curl Example:
```bash
curl -X POST http://localhost:8000/api/label-email \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user@example.com",
    "thread_id": "thread_123",
    "messages": [
      {
        "message_id": "msg_1",
        "from_address": "hr@company.com",
        "to": ["user@example.com"],
        "subject": "Meeting Schedule - Q1 Planning",
        "timestamp": "2026-02-06T10:00:00Z",
        "body": "Let'\''s schedule our quarterly planning meeting for next week."
      }
    ]
  }'
```

**Response**:
```json
{
  "success": true,
  "label": "meeting",
  "user_id": "user@example.com",
  "thread_id": "thread_123",
  "messages_processed": 1,
  "classification_method": "rule-based"
}
```

## Design Decisions

### Why Last Message Focus?
For email threads, the most recent message is most important because:
- It represents the current state of the conversation
- It determines what action is needed now
- Earlier messages in a thread might have different context

### Why Rule-Based First?
- **Fast**: Instant classification, no API calls
- **Free**: No costs for common patterns
- **Reliable**: Deterministic results for clear cases
- **Fallback available**: LLM used only when rules don't match

### Why Structured Output?
Using Pydantic + Langchain ensures:
- Type safety
- Validation of labels
- Confidence scores (if needed later)
- Easy to extend with more fields

## Future Enhancements

Potential improvements:
- [ ] Add confidence scores to rule-based labels
- [ ] Add more labels (travel, legal, HR, etc.)
- [ ] Add multi-label support (one email, multiple categories)
- [ ] Cache LLM results to reduce API calls
- [ ] Add label history/analytics per user
- [ ] Add custom rule support per user

## Troubleshooting

### Issue: "No OpenAI API key found"
**Solution**: Set `OPENAI_API_KEY` environment variable or configure in user settings. Rule-based labeling will still work.

### Issue: Import errors for langchain
**Solution**: Install dependencies:
```bash
pip install langchain langchain-openai langchain-core
```

### Issue: Label always returns "general"
**Solution**: Check if:
1. Rules are matching correctly (see logs)
2. OpenAI API key is valid
3. Email data has subject/body fields populated

## Summary

✅ **Created**: Two new pipelines for preprocessing and labeling emails  
✅ **Added**: New API endpoint `/api/label-email`  
✅ **Rules**: 10 rule-based patterns for common email types  
✅ **Smart**: LLM fallback for complex cases  
✅ **Efficient**: Focuses on last message for threads  
✅ **Tested**: Test script provided for validation  

The system is ready to automatically categorize incoming emails with high accuracy and minimal latency!
