# Slack App Setup Guide

## Step 1: Create Slack App

1. Go to https://api.slack.com/apps
2. Click **"Create New App"**
3. Choose **"From scratch"**
4. Enter:
   - **App Name**: OpenMailBot
   - **Workspace**: Select your development workspace
5. Click **"Create App"**

## Step 2: Configure OAuth & Permissions

1. In left sidebar, click **"OAuth & Permissions"**
2. Scroll to **"Redirect URLs"**
3. Click **"Add New Redirect URL"**
4. Enter: `http://localhost:5000/api/slack/auth/callback`
5. Click **"Add"** then **"Save URLs"**

## Step 3: Add Bot Token Scopes

Scroll to **"Scopes"** → **"Bot Token Scopes"** and add:

```
channels:history      # Read public channel messages
channels:read         # View public channels
groups:history        # Read private channel messages
groups:read           # View private channels
im:history           # Read DM messages
im:read              # View DMs
mpim:history         # Read group DM messages
mpim:read            # View group DMs
users:read           # View users
users:read.email     # View user emails
files:read           # Download files
links:read           # View links
chat:write           # Send messages (optional, for future features)
chat:write.public    # Send to public channels (optional)
```

## Step 4: Get Credentials

1. In left sidebar, click **"Basic Information"**
2. Scroll to **"App Credentials"**
3. Copy:
   - **Client ID**
   - **Client Secret**

## Step 5: Configure Environment Variables

Create/update `/workspaces/openmailbot/openmailbot/backend/.env`:

```bash
# Slack OAuth Configuration
SLACK_CLIENT_ID=1234567890.1234567890123
SLACK_CLIENT_SECRET=abcdef1234567890abcdef1234567890
SLACK_CALLBACK_URL=http://localhost:5000/api/slack/auth/callback
```

Create/update `/workspaces/openmailbot/openmailbot/frontend/.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:5000
```

## Step 6: Install App to Workspace (Optional for Testing)

1. In left sidebar, click **"Install App"**
2. Click **"Install to Workspace"**
3. Review permissions and click **"Allow"**
4. You'll get a **Bot User OAuth Token** - not needed for OAuth flow

## Step 7: Test OAuth Flow

1. Start your backend:
   ```bash
   cd /workspaces/openmailbot/openmailbot/backend
   npm start
   ```

2. Start your frontend:
   ```bash
   cd /workspaces/openmailbot/openmailbot/frontend
   npm run dev
   ```

3. Open http://localhost:3000/settings
4. Click **"Connect to Slack"**
5. Authorize the app
6. You should be redirected back to settings with a success message

## For Production

Update redirect URL to your production domain:
```
https://yourdomain.com/api/slack/auth/callback
```

Update environment variables:
```bash
SLACK_CALLBACK_URL=https://yourdomain.com/api/slack/auth/callback
NEXT_PUBLIC_API_URL=https://yourdomain.com
```

## Troubleshooting

**"invalid_redirect_uri" error**
- Make sure the callback URL in Slack app settings exactly matches `SLACK_CALLBACK_URL`
- No trailing slashes
- Include http:// or https://

**"invalid_client_id" error**
- Double-check Client ID in `.env`
- Make sure no extra spaces

**"Workspace not found" after auth**
- Check that backend is saving workspace correctly
- Verify MongoDB is connected
- Check backend logs for errors

**Frontend shows "Failed to load workspaces"**
- Verify `NEXT_PUBLIC_API_URL` is set correctly
- Check CORS is enabled in backend
- Make sure user is authenticated

## OAuth Flow Diagram

```
User clicks "Connect to Slack"
    ↓
Frontend: slackApi.connect()
    ↓
Redirect to: http://localhost:5000/api/slack/auth
    ↓
Backend: Passport initiates OAuth
    ↓
Redirect to: Slack OAuth page
    ↓
User authorizes app
    ↓
Slack redirects to: http://localhost:5000/api/slack/auth/callback?code=xxx
    ↓
Backend: Passport exchanges code for tokens
    ↓
Backend: Saves workspace to user.slackWorkspaces
    ↓
Backend: Redirects to frontend callback
    ↓
Frontend: /api/slack/callback/route.ts handles redirect
    ↓
Frontend: Redirects to /settings?slack_connected=true
    ↓
Settings page: Shows success message, loads workspaces
```

## Security Notes

- Never commit `.env` files to git
- Rotate Client Secret if exposed
- Use HTTPS in production
- Validate all user inputs in backend
- Implement rate limiting on OAuth endpoints
