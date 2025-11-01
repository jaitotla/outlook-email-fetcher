# OpenMailBot - Quick Start Guide

## Overview

OpenMailBot is a complete AI email assistant platform with:
- Gmail Add-on for in-Gmail AI assistance
- Web portal for Google/Outlook account management
- Backend API (Node.js)
- AI Agent (Python - coming soon)
- Multi-tenant architecture

## Project Structure

```
openmailbot/
├── addon/          # Gmail Add-on (Google Apps Script)
├── backend/        # Node.js + Express API
├── agent/          # Python + FastAPI AI agent (TBD)
├── frontend/       # Next.js web portal (TBD)
├── db/             # Database schemas
├── vector/         # Vector DB integration stubs
├── graph/          # Graph DB integration stubs
├── docker/         # Deployment configs
└── docs/           # API documentation
```

## Prerequisites

- Node.js >= 18.0.0
- MongoDB (local or cloud)
- Google Cloud Console project (for OAuth)
- Microsoft Azure app (for Outlook OAuth)
- Python 3.9+ (for agent)

## Backend Setup

1. Navigate to backend:
```bash
cd openmailbot/backend
```

2. Install dependencies:
```bash
npm install
```

3. Create `.env` from template:
```bash
cp .env.example .env
```

4. Update `.env` with your credentials:
   - MongoDB URI
   - Google OAuth credentials
   - Microsoft OAuth credentials
   - JWT secret

5. Start the server:
```bash
npm start
# or for development:
npm run dev
```

The backend will be available at `http://localhost:3000`.

## Gmail Add-on Setup

1. Go to [Google Apps Script](https://script.google.com)
2. Create new project: "OpenMailBot"
3. Copy `addon/Code.gs` content to script editor
4. Copy `addon/appsscript.json` content to manifest
5. Update `BACKEND_API_URL` in `Code.gs` to your backend URL
6. Deploy > Test deployments > Install as Gmail add-on
7. Open Gmail and test with an email

## Database Setup

### MongoDB

The backend automatically connects to MongoDB. Ensure your `MONGODB_URI` is correct in `.env`.

Collections created automatically:
- `users` - User accounts
- `tenants` - Organizations
- `groups` - Departments/teams
- `emailmetadata` - Email metadata and embeddings

### Indexes (Optional)

For better performance, create indexes:
```javascript
db.emailmetadata.createIndex({ userId: 1, timestamp: -1 })
db.emailmetadata.createIndex({ tenantId: 1, threadId: 1 })
db.users.createIndex({ email: 1 }, { unique: true })
```

## OAuth Setup

### Google OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create new project or select existing
3. Enable Gmail API
4. Configure OAuth consent screen
5. Create OAuth 2.0 credentials (Web application)
6. Add authorized redirect URIs:
   - `http://localhost:3000/auth/google/callback` (dev)
   - `https://yourdomain.com/auth/google/callback` (prod)
7. Copy Client ID and Secret to `.env`

### Microsoft OAuth (Outlook)

1. Go to [Azure Portal](https://portal.azure.com)
2. Register new application
3. Add redirect URI: `http://localhost:3000/auth/microsoft/callback`
4. Create client secret
5. Add API permissions:
   - Microsoft Graph > Mail.Read
   - Microsoft Graph > Mail.ReadWrite
6. Copy Application (client) ID and secret to `.env`

## API Endpoints

### Authentication
- `POST /auth/google` - Google OAuth
- `POST /auth/microsoft` - Microsoft OAuth

### Users & Groups
- `GET /api/users` - List users
- `GET /api/groups` - List groups
- `POST /api/groups` - Create group

### Emails
- `GET /api/emails` - List emails
- `GET /api/emails/:id` - Get email
- `PATCH /api/emails/:id/read` - Mark read

### Analytics
- `GET /api/analytics/personal` - Personal stats
- `GET /api/analytics/group/:id` - Group stats
- `GET /api/analytics/company` - Company stats

### Gmail Add-on
- `POST /api/summarize` - Summarize thread
- `POST /api/generate-reply` - Generate reply
- `POST /api/query` - Natural language query

See `docs/API.md` for complete documentation.

## Testing

### Backend Tests
```bash
cd backend
npm test
```

### Manual Testing

1. Start backend: `npm start`
2. Test health: `curl http://localhost:3000/health`
3. Test OAuth: Navigate to `http://localhost:3000/auth/google`
4. Test Gmail add-on: Open Gmail and interact with add-on

## Deployment

### Docker

```bash
cd docker
docker build -t openmailbot-backend ..
docker run -p 3000:3000 --env-file ../backend/.env openmailbot-backend
```

### Production Checklist

- [ ] Set `NODE_ENV=production` in `.env`
- [ ] Use secure session secrets
- [ ] Enable HTTPS
- [ ] Configure MongoDB with authentication
- [ ] Set up proper CORS origins
- [ ] Enable rate limiting
- [ ] Configure logging and monitoring
- [ ] Set up backup strategy
- [ ] Review OAuth redirect URIs

## Architecture

```
┌─────────────┐
│   Gmail     │
│   Add-on    │◄────┐
└─────────────┘     │
                    │
┌─────────────┐     │
│    Web      │     │    ┌──────────────┐
│   Portal    │◄────┼───►│   Backend    │
│  (Next.js)  │     │    │  (Node.js)   │
└─────────────┘     │    └──────┬───────┘
                    │           │
┌─────────────┐     │           ▼
│   Mobile    │◄────┘    ┌──────────────┐
│    App      │          │  AI Agent    │
└─────────────┘          │  (Python)    │
                         └──────┬───────┘
                                │
                    ┌───────────┼───────────┐
                    ▼           ▼           ▼
              ┌─────────┐ ┌─────────┐ ┌─────────┐
              │MongoDB  │ │ Vector  │ │  Graph  │
              │         │ │   DB    │ │   DB    │
              └─────────┘ └─────────┘ └─────────┘
```

## Next Steps

1. **Complete Python Agent** - Implement FastAPI service for:
   - Email ingestion
   - Embedding generation
   - RAG queries
   - LLM integration

2. **Build Frontend** - Create Next.js web portal for:
   - User onboarding
   - Dashboard
   - Analytics
   - Settings
   - Chatbot UI

3. **Vector DB Integration** - Implement:
   - Pinecone client
   - Local FAISS fallback
   - Embedding storage/retrieval

4. **Graph DB Integration** - Implement:
   - Neo4j client
   - Thread relationship tracking
   - Contact network analysis

5. **Testing** - Add:
   - Unit tests
   - Integration tests
   - E2E tests

## Support

- GitHub: https://github.com/openmailbot/openmailbot
- Docs: https://openmailbot.com/docs
- Issues: https://github.com/openmailbot/openmailbot/issues

## License

MIT License - see LICENSE file for details.
