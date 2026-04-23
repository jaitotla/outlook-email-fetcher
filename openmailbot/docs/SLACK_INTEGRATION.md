# Slack Integration - Technical Documentation

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Data Model](#data-model)
4. [Functionalities](#functionalities)
5. [API Endpoints](#api-endpoints)
6. [Frontend Components](#frontend-components)
7. [Backend Services](#backend-services)
8. [Data Flow](#data-flow)
9. [AI/LLM Features](#aillm-features)
10. [Security & Privacy](#security--privacy)

---

## Overview

The Slack integration enables OpenMailBot to ingest, process, and analyze Slack workspace communications alongside email data, providing a unified knowledge base for AI-powered insights and retrieval.

### Key Capabilities
- **Multi-workspace support** - Connect multiple Slack workspaces per user
- **OAuth 2.0 authentication** - Secure workspace connection
- **Selective sync** - Choose specific channels and DMs
- **AI-powered filtering** - Automatically filter out casual chat
- **File processing** - Extract text from PDFs, documents, and images (OCR)
- **Conversation summarization** - Generate actionable insights from discussions
- **Topic identification** - Auto-categorize conversations
- **Sentiment analysis** - Track conversation tone and mood

---

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js)                    │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Settings Page → Slack Integration Section            │  │
│  │    - ConnectionButton                                 │  │
│  │    - WorkspaceCard (grid)                            │  │
│  │    - WorkspaceConfigModal                            │  │
│  │      ├─ ChannelSelector (all/selected DMs)           │  │
│  │      ├─ SyncConfigPanel                              │  │
│  │      └─ FileTypeSettings                             │  │
│  └───────────────────────────────────────────────────────┘  │
│                           ↓ API calls                        │
└─────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────┐
│                    Backend (Node.js/Express)                 │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Routes: /api/slack/*                                 │  │
│  │    - OAuth (Passport.js)                              │  │
│  │    - Workspace management                             │  │
│  │    - Channel/DM retrieval                             │  │
│  │    - Configuration updates                            │  │
│  │    - Sync triggers                                    │  │
│  └───────────────────────────────────────────────────────┘  │
│                           ↓                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Data Models (MongoDB)                                │  │
│  │    - User (slackWorkspaces[])                         │  │
│  │    - SlackMetadata                                    │  │
│  │    - ConversationPoint                                │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────┐
│                    Agent (Python/FastAPI)                    │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  SlackIngestionService                                │  │
│  │    1. Fetch channels & DMs from Slack API             │  │
│  │    2. Retrieve message history with pagination        │  │
│  │    3. Filter casual chat using LLM                    │  │
│  │    4. Process file attachments                        │  │
│  │    5. Summarize conversations                         │  │
│  │    6. Identify topics & sentiment                     │  │
│  │    7. Save to backend (SlackMetadata + ConversationPoint) │
│  └───────────────────────────────────────────────────────┘  │
│                           ↓                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Dependencies                                         │  │
│  │    - LLMService (OpenAI/Anthropic/Ollama)            │  │
│  │    - FileProcessor (PDF/DOCX/OCR)                    │  │
│  │    - EmbeddingService (text-embedding-ada-002)       │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────┐
│                External Systems                              │
│  - Slack API (conversations, files, users)                  │
│  - Vector DB (Pinecone/FAISS) - embeddings                  │
│  - Graph DB (Neo4j) - relationships                         │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Model

### 1. User Model Extension

**Collection:** `users`

```javascript
{
  _id: ObjectId,
  email: String,
  // ... other user fields
  
  slackWorkspaces: [{
    workspaceId: String,              // Slack team ID
    workspaceName: String,            // Team name
    accessToken: String,              // OAuth access token (encrypted)
    refreshToken: String,             // OAuth refresh token (encrypted)
    botToken: String,                 // Bot user token (if installed)
    connectedAt: Date,                // First connection timestamp
    lastSyncedAt: Date,               // Last successful sync
    
    syncConfig: {
      enabled: Boolean,               // Master enable/disable
      syncDays: Number,               // Days of history to sync (default: 7)
      selectedChannels: [String],     // Array of channel IDs
      selectedDMs: [String],          // Array of DM conversation IDs
      includePublicChannels: Boolean, // Sync public channels
      includePrivateChannels: Boolean,// Sync private channels (if member)
      includeDMs: Boolean,            // Sync direct messages
      dmSelection: String,            // 'all' or 'selected'
      autoSync: Boolean,              // Auto-sync enabled
      syncInterval: Number            // Seconds between syncs (default: 3600)
    },
    
    fileProcessing: {
      processPDFs: Boolean,           // Extract text from PDFs
      processDocs: Boolean,           // Process Word/text documents
      processImages: Boolean,         // OCR for images
      maxFileSize: Number             // Max file size in bytes (default: 10MB)
    }
  }]
}
```

### 2. SlackMetadata Model

**Collection:** `slackmetadata`

```javascript
{
  _id: ObjectId,
  userId: ObjectId,                   // Ref: User
  tenantId: ObjectId,                 // Ref: Tenant
  workspaceId: String,                // Slack team ID
  workspaceName: String,              // Team name
  
  channelId: String,                  // Slack channel/DM ID
  channelName: String,                // Channel name (null for DMs)
  channelType: String,                // 'public_channel' | 'private_channel' | 'im' | 'mpim'
  
  messageType: String,                // 'channel_message' | 'direct_message' | 'thread_reply'
  threadTs: String,                   // Thread timestamp (for replies)
  isThreadParent: Boolean,            // Is this the parent message of a thread?
  
  date: Date,                         // Day of messages (midnight UTC)
  dateRange: {
    start: Date,                      // First message timestamp
    end: Date                         // Last message timestamp
  },
  
  messages: [{
    ts: String,                       // Slack message timestamp (unique ID)
    userId: String,                   // Slack user ID
    userName: String,                 // User's display name
    text: String,                     // Message text
    timestamp: Date,                  // Parsed timestamp
    
    reactions: [{
      emoji: String,                  // Reaction emoji name
      count: Number,                  // Number of reactions
      users: [String]                 // User IDs who reacted
    }],
    
    attachments: [{
      type: String,                   // 'file' | 'link' | 'image'
      name: String,                   // File name
      url: String,                    // File URL
      mimeType: String,               // MIME type
      size: Number,                   // File size in bytes
      extractedText: String,          // Extracted text content
      ocrText: String,                // OCR text (for images)
      processed: Boolean              // Processing complete?
    }]
  }],
  
  conversationPointId: ObjectId,      // Ref: ConversationPoint (summarized view)
  linkedEmailThreads: [ObjectId],     // Ref: EmailMetadata (cross-references)
  
  rawData: Mixed,                     // Original Slack API response (excluded by default)
  
  syncStatus: {
    lastSyncedAt: Date,               // Last sync timestamp
    status: String,                   // 'pending' | 'processing' | 'completed' | 'failed'
    error: String                     // Error message if failed
  },
  
  createdAt: Date,
  updatedAt: Date
}
```

**Indexes:**
- `{ userId: 1, tenantId: 1 }`
- `{ workspaceId: 1, date: -1 }`
- `{ channelId: 1, date: -1 }`
- `{ messageType: 1, date: -1 }`

### 3. ConversationPoint Model

**Collection:** `conversationpoints`

```javascript
{
  _id: ObjectId,
  userId: ObjectId,                   // Ref: User
  tenantId: ObjectId,                 // Ref: Tenant
  
  streamType: String,                 // 'email' | 'slack'
  date: Date,                         // Conversation date
  
  summary: String,                    // AI-generated summary (2-3 sentences)
  
  points: [{
    text: String,                     // Key point or action item
    importance: String,               // 'high' | 'medium' | 'low'
    actionable: Boolean,              // Is this an action item?
    completed: Boolean,               // User marked as done
    assignedTo: String                // User ID if assigned
  }],
  
  topics: [String],                   // Identified topics/projects
  
  sentiment: {
    overall: String,                  // 'positive' | 'neutral' | 'negative' | 'mixed'
    score: Number                     // -1 (negative) to +1 (positive)
  },
  
  participants: [{
    id: String,                       // Slack user ID or email
    name: String,                     // Display name
    email: String                     // Email address
  }],
  
  sourceMetadata: {
    metadataId: ObjectId,             // Ref: SlackMetadata or EmailMetadata
    metadataType: String              // 'SlackMetadata' | 'EmailMetadata'
  },
  
  embeddings: [Number],               // Vector embeddings for semantic search
  
  createdAt: Date,
  updatedAt: Date
}
```

**Indexes:**
- `{ userId: 1, streamType: 1, date: -1 }`
- `{ topics: 1 }`
- `{ 'points.actionable': 1, 'points.completed': 1 }`

---

## Functionalities

### 1. Workspace Connection (OAuth 2.0)

**User Journey:**
1. User clicks "Connect to Slack" in settings
2. Redirects to Slack OAuth page
3. User authorizes workspace access
4. Slack redirects back with authorization code
5. Backend exchanges code for access tokens
6. Workspace saved to `user.slackWorkspaces[]`

**OAuth Scopes Required:**
- `channels:history` - Read public channel messages
- `channels:read` - View public channels
- `groups:history` - Read private channel messages
- `groups:read` - View private channels
- `im:history` - Read DM messages
- `im:read` - View DMs
- `mpim:history` - Read group DM messages
- `mpim:read` - View group DMs
- `users:read` - View user information
- `users:read.email` - View user emails
- `files:read` - Download file attachments
- `links:read` - View shared links

### 2. Channel & DM Selection

**Public Channels:**
- Fetched via `conversations.list` API (type: `public_channel`)
- Users can toggle inclusion of all public channels
- Individual selection available

**Private Channels:**
- Only channels where bot is a member
- Requires explicit invitation
- Users can toggle inclusion

**Direct Messages:**
- **Mode 1: All DMs** - Automatically sync all direct messages
- **Mode 2: Selected DMs** - User chooses specific conversations
- Fetched via `conversations.list` API (type: `im`, `mpim`)

### 3. Message Ingestion

**Process:**
1. Fetch channel list based on user configuration
2. For each channel/DM:
   - Retrieve message history (`conversations.history`)
   - Paginate through results (100 messages per request)
   - Group messages by day
3. Process each day's messages through AI pipeline

**Pagination Handling:**
```python
cursor = None
while True:
    response = slack_api.conversations_history(
        channel=channel_id,
        oldest=start_timestamp,
        latest=end_timestamp,
        limit=100,
        cursor=cursor
    )
    messages.extend(response['messages'])
    if not response['has_more']:
        break
    cursor = response['response_metadata']['next_cursor']
```

### 4. AI-Powered Message Filtering

**Purpose:** Filter out casual greetings, "+1" reactions, and non-work-related chat

**Algorithm:**
1. Combine first 50 messages into conversation text
2. Send to LLM with classification prompt:
   ```
   Classify each message as:
   - KEEP: Work-related, decisions, questions, discussions
   - FILTER: Greetings, small talk, emoji-only, "thanks", "lol"
   ```
3. LLM returns indices of messages to keep
4. Discard filtered messages

**Example:**
```
Input: ["Hi everyone!", "Good morning", "Let's discuss the Q1 roadmap", "+1"]
LLM Output: {"keep": [2]}  # Only keeps "Let's discuss..."
```

### 5. File Processing

**Supported File Types:**

| Type | MIME Types | Processing |
|------|------------|------------|
| **PDFs** | `application/pdf` | PyPDF2/pdfplumber text extraction |
| **Documents** | `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `text/plain` | python-docx, plain text read |
| **Images** | `image/png`, `image/jpeg`, `image/gif` | Tesseract OCR |

**Process:**
1. Check file size against `maxFileSize` limit
2. Check file type against enabled types
3. Download file using `url_private` + access token
4. Extract text using appropriate processor
5. Store extracted text in `messages[].attachments[].extractedText`

### 6. Conversation Summarization

**LLM Prompt:**
```
Summarize this Slack conversation from #channel-name on 2026-01-05.

Provide:
1. A brief summary (2-3 sentences)
2. Key points as a list (decisions, action items)
3. Mark each point as high/medium/low importance
4. Indicate if actionable

Conversation:
[messages with timestamps and usernames]

Return JSON:
{
  "summary": "Brief overview...",
  "points": [
    {"text": "Point 1", "importance": "high", "actionable": true},
    ...
  ]
}
```

### 7. Topic Identification

**LLM Prompt:**
```
Identify 1-3 main topics or projects discussed in this summary.
Return topics as a JSON array of strings.

Summary: [conversation summary]

Example: {"topics": ["project-alpha", "budget-review"]}
```

### 8. Sentiment Analysis

**LLM Prompt:**
```
Analyze the sentiment and tone of this conversation.

Messages: [sample of 20 messages]

Return JSON:
{
  "overall": "positive|neutral|negative|mixed",
  "score": 0.5  // -1 (negative) to +1 (positive)
}
```

### 9. Automatic Sync Scheduling

**Backend Implementation:**
- Cron job runs every minute
- Checks all users with `autoSync: true`
- For each workspace:
  - If `now - lastSyncedAt > syncInterval`, trigger sync
  - Call Python agent ingestion endpoint
  - Update `lastSyncedAt` on completion

**Agent Endpoint:**
```
POST /api/slack/ingest
{
  "userId": "...",
  "workspaceId": "...",
  "accessToken": "...",
  "syncDays": 7,
  "selectedChannels": [...],
  ...
}
```

---

## API Endpoints

### Backend (Node.js/Express)

#### OAuth Endpoints

**`GET /api/slack/auth`**
- **Description:** Initiate Slack OAuth flow
- **Auth:** Required (user must be logged in)
- **Handler:** Passport.js SlackStrategy
- **Response:** Redirect to Slack authorization page

**`GET /api/slack/auth/callback`**
- **Description:** OAuth callback endpoint
- **Query Params:** `code` (authorization code)
- **Handler:** Passport.js SlackStrategy
- **Process:**
  1. Exchange code for tokens
  2. Fetch user profile and team info
  3. Save/update workspace in `user.slackWorkspaces`
  4. Redirect to frontend callback
- **Redirect:** `http://frontend/api/slack/callback?code=...`

#### Workspace Management

**`GET /api/slack/workspaces`**
- **Description:** Get all connected workspaces
- **Auth:** Required
- **Response:**
  ```json
  {
    "workspaces": [{
      "workspaceId": "T123456",
      "workspaceName": "Acme Corp",
      "connectedAt": "2026-01-01T00:00:00Z",
      "lastSyncedAt": "2026-01-05T10:00:00Z",
      "syncConfig": { ... },
      "fileProcessing": { ... }
    }]
  }
  ```

**`GET /api/slack/workspaces/:workspaceId/channels`**
- **Description:** Get channels and DMs for a workspace
- **Auth:** Required
- **Process:**
  1. Find workspace in user profile
  2. Call Slack API `conversations.list` with access token
  3. Return formatted channel/DM lists
- **Response:**
  ```json
  {
    "channels": [{
      "id": "C123456",
      "name": "general",
      "is_private": false,
      "is_member": true,
      "num_members": 42
    }],
    "dms": [{
      "id": "D123456",
      "user": "U123456",
      "user_name": "John Doe"
    }]
  }
  ```

**`PUT /api/slack/workspaces/:workspaceId/config`**
- **Description:** Update workspace sync configuration
- **Auth:** Required
- **Body:**
  ```json
  {
    "syncConfig": {
      "selectedChannels": ["C123", "C456"],
      "dmSelection": "all",
      "autoSync": true,
      ...
    },
    "fileProcessing": {
      "processPDFs": true,
      ...
    }
  }
  ```
- **Response:**
  ```json
  {
    "success": true,
    "message": "Sync configuration updated"
  }
  ```

**`POST /api/slack/workspaces/:workspaceId/sync`**
- **Description:** Trigger manual sync
- **Auth:** Required
- **Body:** `{ "syncDays": 7 }` (optional)
- **Process:**
  1. Find workspace in user profile
  2. Call Python agent ingestion endpoint
  3. Update `lastSyncedAt`
- **Response:**
  ```json
  {
    "success": true,
    "message": "Sync started successfully",
    "result": {
      "channels_processed": 5,
      "dms_processed": 3,
      "messages_ingested": 127,
      "files_processed": 8,
      "errors": []
    }
  }
  ```

**`DELETE /api/slack/workspaces/:workspaceId`**
- **Description:** Disconnect workspace
- **Auth:** Required
- **Process:**
  1. Remove workspace from `user.slackWorkspaces`
  2. Optionally: Delete associated SlackMetadata records
- **Response:**
  ```json
  {
    "success": true,
    "message": "Workspace disconnected successfully"
  }
  ```

**`POST /api/slack/metadata`**
- **Description:** Save Slack metadata (called by Python agent)
- **Auth:** Internal (agent API key)
- **Body:** SlackMetadata document
- **Response:**
  ```json
  {
    "success": true,
    "id": "objectId"
  }
  ```

### Agent (Python/FastAPI)

**`POST /api/slack/ingest`**
- **Description:** Ingest Slack workspace messages
- **Body:**
  ```json
  {
    "userId": "...",
    "workspaceId": "...",
    "accessToken": "...",
    "botToken": "...",
    "syncDays": 7,
    "selectedChannels": [...],
    "selectedDMs": [...],
    "includePublic": true,
    "includePrivate": false,
    "includeDMs": true,
    "fileConfig": { ... }
  }
  ```
- **Response:**
  ```json
  {
    "channels_processed": 5,
    "dms_processed": 3,
    "messages_ingested": 127,
    "files_processed": 8,
    "errors": []
  }
  ```

**`POST /api/slack/channels`**
- **Description:** Fetch channels from Slack API
- **Body:** `{ "accessToken": "..." }`
- **Response:**
  ```json
  {
    "channels": [...],
    "dms": [...]
  }
  ```

---

## Frontend Components

### Component Hierarchy

```
SettingsPage
  └─ SlackIntegration Section
      ├─ ConnectionButton (if no workspaces)
      ├─ WorkspaceCard[] (for each workspace)
      │   ├─ Slack icon + workspace name
      │   ├─ Sync status indicator
      │   ├─ Channel/DM count
      │   ├─ Last synced time
      │   ├─ Configure button → Opens modal
      │   ├─ Sync button → Triggers sync
      │   └─ Disconnect button
      └─ WorkspaceConfigModal
          ├─ ChannelSelector
          │   ├─ Tabs: Channels | DMs
          │   ├─ Search bar
          │   ├─ Public channels (toggle + checkboxes)
          │   ├─ Private channels (toggle + checkboxes)
          │   └─ DMs (radio: all/selected + checkboxes)
          ├─ SyncConfigPanel
          │   ├─ Auto-sync toggle
          │   ├─ Sync interval dropdown
          │   ├─ Sync days input
          │   └─ Enabled toggle
          └─ FileTypeSettings
              ├─ Process PDFs checkbox
              ├─ Process docs checkbox
              ├─ Process images checkbox
              └─ Max file size input
```

### Component Details

#### ConnectionButton
- **Props:** `onConnect: () => void`
- **Style:** Slack brand purple (#4A154B)
- **Icon:** Slack logo
- **Action:** Redirects to `/api/slack/auth`

#### WorkspaceCard
- **Props:**
  - `workspace: SlackWorkspace`
  - `onConfigure: (id) => void`
  - `onSync: (id) => void`
  - `onDisconnect: (id) => void`
- **Displays:**
  - Workspace name
  - Active/Paused status (green/gray dot)
  - Channel count, DM count
  - Last synced time (relative: "2m ago")
- **Actions:**
  - Configure → Opens modal
  - Sync → Triggers manual sync (with spinner)
  - Trash icon → Disconnects (with confirmation)

#### ChannelSelector
- **Props:**
  - `channels: SlackChannel[]`
  - `dms: SlackDM[]`
  - `selectedChannels: string[]`
  - `selectedDMs: string[]`
  - `dmSelection: 'all' | 'selected'`
  - `includePublicChannels: boolean`
  - `includePrivateChannels: boolean`
  - `includeDMs: boolean`
  - `onChange: (updates) => void`
- **Features:**
  - Tab switching (Channels | DMs)
  - Search with real-time filtering
  - Public/private toggles
  - DM mode selection (radio buttons)
  - Select all / Deselect all buttons
  - Icons: # (public), 🔒 (private), 💬 (DMs)

#### SyncConfigPanel
- **Props:**
  - `syncConfig: SyncConfig`
  - `onChange: (updates) => void`
- **Controls:**
  - Auto-sync toggle
  - Sync interval dropdown (15m to daily)
  - Sync days number input (1-365)
  - Master enabled toggle

#### FileTypeSettings
- **Props:**
  - `fileProcessing: FileProcessing`
  - `onChange: (updates) => void`
- **Controls:**
  - Process PDFs checkbox
  - Process documents checkbox
  - Process images (OCR) checkbox
  - Max file size (MB) input

#### WorkspaceConfigModal
- **Props:**
  - `workspace: SlackWorkspace`
  - `isOpen: boolean`
  - `onClose: () => void`
  - `onSave: () => void`
- **Layout:** Full-screen modal with:
  - Header: Back button, workspace name, close X
  - Body: Scrollable sections (channels, sync, files)
  - Footer: "Sync Now" + "Cancel" + "Save Changes"

---

## Backend Services

### SlackController (Node.js)

**Location:** `backend/controllers/slackController.js`

**Methods:**
- `connectWorkspace()` - OAuth success handler
- `getWorkspaces()` - List user's workspaces
- `getChannels(workspaceId)` - Fetch channels from Slack API
- `updateSyncConfig(workspaceId)` - Update configuration
- `syncWorkspace(workspaceId)` - Trigger manual sync
- `disconnectWorkspace(workspaceId)` - Remove workspace
- `saveMetadata()` - Save SlackMetadata (for agent)
- `getConversations()` - Query conversations

### SlackIngestionService (Python)

**Location:** `agent/services/slack_ingestion.py`

**Main Method:** `ingest_workspace()`

**Flow:**
1. Calculate date range (last N days)
2. Fetch channels based on config
3. For each channel:
   - Fetch message history with pagination
   - Group messages by day
   - Process each day:
     - Filter casual chat (LLM)
     - Process file attachments
     - Summarize conversation (LLM)
     - Identify topics (LLM)
     - Analyze sentiment (LLM)
     - Extract participants
     - Save to backend
4. Return summary stats

**Helper Methods:**
- `_fetch_channels()` - Get channel list from Slack
- `_fetch_dms()` - Get DM list from Slack
- `_process_channel()` - Process single channel
- `_process_day_messages()` - Process messages for one day
- `_filter_general_chat()` - LLM-based filtering
- `_process_message_file()` - Download and extract file text
- `_summarize_conversation()` - LLM summarization
- `_identify_topics()` - LLM topic extraction
- `_analyze_sentiment()` - LLM sentiment analysis
- `_extract_participants()` - Parse user information
- `_save_slack_data()` - Save to MongoDB

---

## Data Flow

### 1. OAuth Connection Flow

```
User clicks "Connect to Slack"
    ↓
Frontend: window.location.href = '/api/slack/auth'
    ↓
Backend: GET /api/slack/auth
    ↓
Passport.authenticate('slack')
    ↓
Redirect to: https://slack.com/oauth/v2/authorize?client_id=...&scope=...
    ↓
User authorizes app in Slack
    ↓
Slack redirects: /api/slack/auth/callback?code=xyz&state=abc
    ↓
Backend: Passport exchanges code for tokens
    ↓
Slack returns: { access_token, refresh_token, team: { id, name }, bot: { token } }
    ↓
Backend: Save to user.slackWorkspaces[]
    ↓
Backend: Redirect to frontend callback
    ↓
Frontend: /api/slack/callback/route.ts
    ↓
Frontend: Redirect to /settings?slack_connected=true
    ↓
Settings page: Show success toast, reload workspaces
```

### 2. Message Ingestion Flow

```
User clicks "Sync Now"
    ↓
Frontend: POST /api/slack/workspaces/:id/sync
    ↓
Backend: Find workspace, prepare payload
    ↓
Backend: POST http://agent:8000/api/slack/ingest
    ↓
Agent: SlackIngestionService.ingest_workspace()
    ↓
Agent: Fetch channels from Slack API
    ↓
For each channel:
    ↓
    Agent: conversations.history (paginated)
    ↓
    Agent: Group messages by day
    ↓
    For each day:
        ↓
        Agent: Filter casual chat (LLM)
        ↓
        Agent: Process files (download + extract)
        ↓
        Agent: Summarize conversation (LLM)
        ↓
        Agent: Identify topics (LLM)
        ↓
        Agent: Analyze sentiment (LLM)
        ↓
        Agent: POST /api/slack/metadata (save SlackMetadata)
        ↓
        Agent: POST /api/conversations/points (save ConversationPoint)
        ↓
    Return to channel loop
    ↓
Return to workspace
    ↓
Agent: Return summary { channels_processed, messages_ingested, ... }
    ↓
Backend: Update workspace.lastSyncedAt
    ↓
Backend: Return success to frontend
    ↓
Frontend: Show success toast, refresh workspace data
```

### 3. Search/Retrieval Flow

```
User searches: "budget discussion"
    ↓
Frontend: GET /api/search?q=budget+discussion
    ↓
Backend: Generate query embedding
    ↓
Backend: Vector search in Pinecone/FAISS
    ↓
Return top K conversation points (email + Slack)
    ↓
Backend: Populate source metadata
    ↓
Frontend: Display unified results:
    - Email threads
    - Slack conversations
    - Grouped by date/topic
```

---

## AI/LLM Features

### 1. Casual Chat Filtering

**Goal:** Reduce noise by removing "hi", "thanks", "+1", emoji-only messages

**Implementation:**
```python
prompt = f"""
Analyze this Slack conversation and classify each message.

KEEP: Work-related info, decisions, questions, discussions
FILTER: Greetings, small talk, emoji-only, "+1", "thanks", "lol"

Conversation:
{messages}

Return JSON: {{"keep": [0, 2, 5, 7]}}  # 0-indexed message IDs
"""

response = llm.generate(prompt)
keep_indices = json.loads(response)['keep']
filtered = [msg for i, msg in enumerate(messages) if i in keep_indices]
```

**Benefits:**
- Reduces storage by ~40%
- Improves search relevance
- Focuses AI on meaningful content

### 2. Conversation Summarization

**Goal:** Create concise, actionable summaries

**Prompt Template:**
```
Summarize this Slack conversation from #channel-name on YYYY-MM-DD.

Provide:
1. Brief summary (2-3 sentences)
2. Key points with:
   - Text description
   - Importance (high/medium/low)
   - Is actionable? (yes/no)

Conversation:
[user1 (10:15)]: Let's finalize the Q1 roadmap today
[user2 (10:17)]: Agreed. Priority: API v2 and mobile app
[user1 (10:20)]: I'll draft the timeline by EOD
...

Return JSON:
{
  "summary": "Team discussed Q1 roadmap priorities...",
  "points": [
    {
      "text": "API v2 is top priority for Q1",
      "importance": "high",
      "actionable": false
    },
    {
      "text": "user1 to draft timeline by EOD",
      "importance": "high",
      "actionable": true
    }
  ]
}
```

### 3. Topic Identification

**Goal:** Auto-categorize conversations by project/topic

**Prompt:**
```
Identify 1-3 main topics/projects in this summary.
Use lowercase, hyphenated format.

Summary: Team discussed Q1 roadmap priorities...

Example output: {"topics": ["q1-roadmap", "api-v2", "mobile-app"]}
```

**Use Cases:**
- Group conversations by topic
- Filter searches by project
- Identify trending discussions

### 4. Sentiment Analysis

**Goal:** Track team mood and conversation tone

**Prompt:**
```
Analyze sentiment of this conversation.

Messages:
[sample of 20 messages]

Return:
{
  "overall": "positive|neutral|negative|mixed",
  "score": 0.5  // -1 to +1
}
```

**Use Cases:**
- Identify contentious discussions
- Track team morale trends
- Highlight urgent/negative conversations

### 5. Embedding Generation

**Process:**
1. Combine summary + key points into single text
2. Generate embedding using `text-embedding-ada-002` or similar
3. Store in `ConversationPoint.embeddings[]`
4. Index in vector database (Pinecone/FAISS)

**Search:**
```python
query = "budget planning"
query_embedding = embedding_service.embed(query)
results = vector_db.search(query_embedding, top_k=10)
# Returns: ConversationPoints from both email and Slack
```

---

## Security & Privacy

### 1. Token Storage

**Encryption:**
- Access tokens encrypted at rest in MongoDB
- Use AES-256-GCM with per-user encryption keys
- Keys stored in secure key management service (AWS KMS, HashiCorp Vault)

**Implementation:**
```javascript
// Before saving
user.slackWorkspaces[0].accessToken = encrypt(token, user.encryptionKey);

// Before using
const decryptedToken = decrypt(user.slackWorkspaces[0].accessToken, user.encryptionKey);
```

### 2. OAuth Security

- State parameter validation (CSRF protection)
- HTTPS required in production
- Short-lived authorization codes
- Refresh token rotation
- Scope validation (only request needed permissions)

### 3. Data Access Control

**Tenant Isolation:**
- All queries include `tenantId` filter
- Users can only access their own workspaces
- Middleware validates user ownership before sync

**Example:**
```javascript
const workspace = user.slackWorkspaces.find(w => w.workspaceId === req.params.id);
if (!workspace) {
  return res.status(404).json({ error: 'Workspace not found' });
}
```

### 4. API Authentication

**User Endpoints:**
- Session-based auth (Passport.js)
- CSRF token validation
- Rate limiting (100 req/min per user)

**Agent Endpoints:**
- Internal API key required
- IP whitelist (only agent container)
- Separate authentication middleware

### 5. Data Retention

**User Control:**
- Users can disconnect workspace (deletes tokens)
- Option to delete historical data
- GDPR compliance: full data export and deletion

**Automatic Cleanup:**
- Expired tokens purged weekly
- Failed sync records deleted after 30 days
- Raw Slack data (`rawData` field) excluded from backups

### 6. File Processing Security

**Validation:**
- File size limits enforced
- MIME type validation
- Malware scanning (ClamAV) before processing
- Sandboxed processing environment

**Storage:**
- Extracted text only (original files not stored long-term)
- Temporary file cleanup after processing
- No execution of file contents

### 7. Compliance

**GDPR:**
- User consent for Slack access
- Right to export data
- Right to delete data
- Privacy policy disclosure

**SOC 2:**
- Audit logging for all data access
- Encryption in transit (TLS 1.3)
- Encryption at rest
- Access control monitoring

---

## Performance Optimizations

### 1. Pagination Strategy

- Slack API: 100 messages per request (max)
- Cursor-based pagination (no offset skipping)
- Parallel channel processing (asyncio)

### 2. Caching

**Channel Lists:**
- Cache for 1 hour per workspace
- Invalidate on manual refresh
- Stored in Redis

**User Profiles:**
- Cache Slack user info for 24 hours
- Reduces API calls during ingestion

### 3. Batch Processing

**Database Writes:**
- Batch insert messages (100 at a time)
- Single transaction per day's messages
- Reduces MongoDB load

**LLM Calls:**
- Batch summarization when possible
- Reuse embeddings for similar content

### 4. Rate Limiting

**Slack API:**
- Respect `Retry-After` headers
- Exponential backoff on errors
- Max 1 req/second per workspace (Tier 3 limit)

**LLM API:**
- Queue requests with rate limiting
- Parallel processing with concurrency limits
- Fallback to simpler models if quota exceeded

---

## Monitoring & Logging

### 1. Metrics

**Ingestion Metrics:**
- Messages ingested per hour
- Average processing time per channel
- LLM API latency
- File processing success rate

**User Metrics:**
- Active workspaces
- Daily sync triggers
- Average channels per workspace
- Storage usage per tenant

### 2. Logging

**Structured Logs:**
```json
{
  "timestamp": "2026-01-05T10:00:00Z",
  "level": "INFO",
  "service": "slack-ingestion",
  "userId": "user123",
  "workspaceId": "T123456",
  "channelId": "C123456",
  "action": "process_day",
  "messagesProcessed": 45,
  "filesProcessed": 3,
  "duration": 12.5
}
```

**Error Tracking:**
- Sentry integration for exceptions
- Slack API errors logged with context
- Failed syncs flagged for retry

### 3. Alerts

**Critical:**
- OAuth token refresh failures
- Sync failures > 5 consecutive
- LLM API quota exceeded
- Database connection errors

**Warning:**
- Sync duration > 10 minutes
- File processing failures > 10%
- API rate limit approaching

---

## Future Enhancements

### 1. Real-time Message Streaming

- Slack Events API integration
- WebSocket connection for live updates
- Instant message processing (no sync delay)

### 2. Thread Awareness

- Better handling of threaded conversations
- Parent-child relationship tracking
- Thread summarization

### 3. Reactions Analysis

- Track emoji reactions as sentiment signals
- Identify highly engaged discussions
- User engagement metrics

### 4. Cross-Platform Linking

- Auto-detect email threads mentioned in Slack
- Link Slack discussions to email conversations
- Unified thread view

### 5. Smart Notifications

- AI-powered notification prioritization
- "Important for you" based on role/projects
- Digest summaries of missed conversations

### 6. Advanced Search

- Natural language queries across email + Slack
- Date range filters
- Participant filters
- File type filters

### 7. Collaboration Features

- Shared conversation points
- Team dashboards
- Action item tracking
- Auto-assignment based on @mentions

---

## Troubleshooting

### Common Issues

**1. OAuth "invalid_redirect_uri"**
- **Cause:** Callback URL mismatch
- **Fix:** Ensure `SLACK_CALLBACK_URL` matches Slack app settings exactly

**2. "Workspace not found" after auth**
- **Cause:** Database save failed
- **Fix:** Check MongoDB connection, verify user session

**3. Sync returns "No channels found"**
- **Cause:** Bot not invited to private channels
- **Fix:** Invite bot to channels, or enable only public channels

**4. File processing timeout**
- **Cause:** Large files, slow OCR
- **Fix:** Increase timeout, reduce `maxFileSize`, disable image OCR

**5. LLM rate limit errors**
- **Cause:** Too many API calls
- **Fix:** Enable caching, reduce sync frequency, use cheaper model for filtering

### Debug Mode

**Enable verbose logging:**
```bash
# Backend
DEBUG=slack:* npm start

# Agent
LOG_LEVEL=DEBUG python main.py
```

**Test individual components:**
```python
# Test Slack API connection
python -c "from services.slack_ingestion import SlackIngestionService; \
  service = SlackIngestionService(); \
  channels = await service._fetch_channels('token', True, False, None)"
```

---

## Conclusion

The Slack integration provides a comprehensive solution for ingesting, processing, and analyzing Slack communications using AI. Key strengths:

✅ **Scalable architecture** - Handles multiple workspaces, thousands of messages
✅ **AI-powered intelligence** - Filtering, summarization, topic extraction
✅ **User control** - Granular channel/DM selection, sync configuration
✅ **Security-first** - Encrypted tokens, tenant isolation, GDPR compliance
✅ **Unified experience** - Seamlessly integrated with email data

The system transforms scattered Slack conversations into organized, searchable, actionable knowledge.
