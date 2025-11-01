# Gmail Add-on (Google Apps Script)

Conversational AI interface inside Gmail using CardService.

## Features

### Core Capabilities
- **Summarize email threads** - Get instant summaries of email conversations
- **Generate context-aware replies** - AI-powered reply drafting based on tone and hierarchy
- **Natural language queries** - Ask questions about emails in plain language
- **Related threads** - Discover related email conversations
- **Conversational onboarding** - Step-by-step setup within Gmail

### Onboarding Flow
Users configure their OpenMailBot preferences directly in Gmail:
1. Choose Vector DB (Pinecone or Local FAISS)
2. Select LLM provider (OpenAI, Gemini, or Ollama)
3. Set default tone (Professional, Semi-Professional, Casual, Personal)

### Tone & Hierarchy
The add-on adapts reply generation based on:
- **Tone**: professional, semi-professional, casual, personal
- **Direction**: upward (to boss), sideways (to peers), downward (to team)

## Files

- `Code.gs` - Main add-on logic
- `appsscript.json` - Manifest configuration with OAuth scopes

## Setup

### 1. Create Google Apps Script Project

1. Go to [Google Apps Script](https://script.google.com)
2. Create a new project named "OpenMailBot"
3. Copy the contents of `Code.gs` into the script editor
4. Copy the contents of `appsscript.json` into the manifest

### 2. Update Configuration

In `Code.gs`, update the backend API URL:
```javascript
const BACKEND_API_URL = 'https://api.openmailbot.com';
```

### 3. Deploy as Gmail Add-on

1. In the Apps Script editor, go to **Deploy** > **Test deployments**
2. Select **Gmail add-on** as the deployment type
3. Install the test add-on in your Gmail

### 4. Publish to Google Workspace Marketplace (Optional)

For production:
1. Complete the OAuth consent screen in Google Cloud Console
2. Submit for Google Workspace Marketplace review
3. Follow Google's add-on publishing guidelines

## OAuth Scopes

The add-on requires these OAuth scopes (configured in `appsscript.json`):
- `https://www.googleapis.com/auth/gmail.readonly` - Read email content
- `https://www.googleapis.com/auth/gmail.modify` - Mark emails as read/replied
- `https://www.googleapis.com/auth/userinfo.email` - Access user email
- `https://www.googleapis.com/auth/script.external_request` - Call backend API

## API Integration

The add-on communicates with the Node.js backend via these endpoints:
- `POST /api/summarize` - Summarize email thread
- `POST /api/generate-reply` - Generate reply
- `POST /api/query` - Handle user queries
- `POST /api/related-threads` - Get related threads

## User Experience

1. User opens an email in Gmail
2. OpenMailBot card appears in the sidebar
3. Quick actions available:
   - Summarize Thread
   - Generate Reply
   - Ask custom questions
   - View related threads
4. Chat input for natural language queries
5. Settings button for configuration

## Development

Test the add-on locally:
```bash
# In Apps Script editor
# Run > Test as add-on
# Select Gmail and test with sample emails
```

## Architecture

```
Gmail → Add-on (Apps Script) → Backend API → Python Agent → LLM/Vector DB
```

The add-on acts as the UI layer, with all AI processing handled by the backend and Python agent.