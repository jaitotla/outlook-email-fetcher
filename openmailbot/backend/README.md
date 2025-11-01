# Backend (Node.js + Express)

Handles API, authentication, analytics, and admin/user management for OpenMailBot.

## Features
- Google & Microsoft OAuth authentication
- Multi-tenant user management
- Group/department management
- Email metadata storage and retrieval
- Analytics (personal, group, company-wide)
- User/tenant settings management
- Gmail Add-on API endpoints

## API Endpoints

### Authentication
- `POST /auth/google` - Google OAuth login
- `POST /auth/microsoft` - Microsoft OAuth login
- `GET /auth/google/callback` - Google OAuth callback
- `GET /auth/microsoft/callback` - Microsoft OAuth callback
- `POST /auth/logout` - Logout

### Users
- `GET /api/users` - Get all users (admin only)
- `GET /api/users/:id` - Get user by ID
- `PUT /api/users/:id` - Update user
- `DELETE /api/users/:id` - Deactivate user (admin only)

### Groups
- `GET /api/groups` - Get all groups for tenant
- `POST /api/groups` - Create group (admin/manager only)
- `GET /api/groups/:id` - Get group by ID
- `PUT /api/groups/:id` - Update group
- `DELETE /api/groups/:id` - Delete group (admin only)

### Emails
- `GET /api/emails` - Get user's emails (with pagination, filters)
- `GET /api/emails/:id` - Get email by ID
- `GET /api/emails/thread/:threadId` - Get emails by thread
- `PATCH /api/emails/:id/read` - Mark email as read
- `PATCH /api/emails/:id/replied` - Mark email as replied
- `PATCH /api/emails/:id/labels` - Add labels to email

### Analytics
- `GET /api/analytics/personal` - Get personal analytics
- `GET /api/analytics/group/:groupId` - Get group analytics
- `GET /api/analytics/company` - Get company-wide analytics (admin only)

### Settings
- `GET /api/settings` - Get user settings
- `PUT /api/settings` - Update user settings
- `GET /api/settings/tenant` - Get tenant settings (admin only)
- `PUT /api/settings/tenant` - Update tenant settings (admin only)

### Gmail Add-on Endpoints
- `POST /api/summarize` - Summarize email thread
- `POST /api/generate-reply` - Generate reply
- `POST /api/query` - Handle natural language query
- `POST /api/related-threads` - Get related threads

## Setup

1. Install dependencies:
```bash
npm install
```

2. Create `.env` file from `.env.example`:
```bash
cp .env.example .env
```

3. Update `.env` with your configuration:
   - MongoDB URI
   - Google OAuth credentials
   - Microsoft OAuth credentials
   - JWT secret
   - Agent API URL

4. Start the server:
```bash
npm start
```

For development with auto-reload:
```bash
npm run dev
```

## Environment Variables

See `.env.example` for all required environment variables.

## Dependencies

- **express** - Web framework
- **mongoose** - MongoDB ODM
- **passport** - Authentication middleware
- **passport-google-oauth20** - Google OAuth strategy
- **passport-microsoft** - Microsoft OAuth strategy
- **jsonwebtoken** - JWT tokens
- **axios** - HTTP client for agent communication
- **helmet** - Security middleware
- **cors** - CORS middleware
- **morgan** - Request logging

## Architecture

The backend connects to:
1. **MongoDB** - User, tenant, group, and email metadata storage
2. **Python Agent** (FastAPI) - AI processing (embeddings, RAG, LLM)
3. **Frontend** (Next.js) - Web portal
4. **Gmail Add-on** - Google Apps Script

## Security

- OAuth-based authentication (no password storage)
- JWT tokens for session management
- Helmet for security headers
- Rate limiting (optional)
- Data encryption in transit and at rest
- Tenant isolation enforced at all levels