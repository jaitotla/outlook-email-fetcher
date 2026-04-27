# OpenMailBot - Zoho Extension Development Guide

## Overview

This guide covers development, testing, and deployment of the OpenMailBot Zoho Mail extension.

## Architecture

### Extension Structure
```
zoho-extension/
├── manifest.json          # Extension metadata and permissions
├── src/
│   ├── index.js          # Main extension logic
│   └── styles.css        # UI styling
├── settings/
│   ├── settings.html     # Settings interface
│   └── settings.js       # Settings management
├── assets/               # Icons and images
├── build.sh             # Build script
└── README.md            # User documentation
```

### Key APIs Used

#### Zoho Mail Extension API
- `ZMAIL.extension.*` - Extension lifecycle
- `ZMAIL.messages.*` - Email access
- `ZMAIL.composer.*` - Compose window manipulation
- `ZMAIL.storage.*` - Local data storage

#### Compose API Integration
```javascript
await ZMAIL.composer.open({
  type: 'reply',        // 'reply', 'replyAll', 'forward'
  messageId: messageId, // Original message ID
  subject: subject,     // Pre-filled subject
  body: bodyHtml,       // Pre-filled HTML body
  format: 'html'        // 'html' or 'text'
});
```

## Development Setup

### Prerequisites
- Zoho Mail account (free or paid)
- Modern web browser (Chrome, Firefox, Edge)
- Basic knowledge of JavaScript

### Local Development

1. **Enable Developer Mode**
   ```
   Zoho Mail → Settings → Extensions → Developer Mode → Enable
   ```

2. **Load Extension**
   ```
   Developer Mode → Load Unpacked Extension → Select zoho-extension folder
   ```

3. **Test Changes**
   - Edit code in `src/index.js`
   - Reload extension in Zoho Mail
   - Test features in inbox

### Debugging

#### Browser DevTools
```javascript
// Add console logs
console.log('OpenMailBot: Feature triggered');

// Inspect errors
try {
  await someFunction();
} catch (error) {
  console.error('OpenMailBot Error:', error);
}
```

#### Zoho Mail Console
- Right-click extension panel → Inspect
- Check Console tab for logs
- Monitor Network tab for API calls

## Features Implementation

### 1. Email Summarization

**Flow:**
1. User clicks "Summarize Thread"
2. Extension fetches email data via `ZMAIL.messages.get()`
3. Sends to backend `/api/summarize`
4. Displays summary in results panel

**Code:**
```javascript
async function summarizeEmail(messageId) {
  const emailData = await getEmailData(messageId);
  const response = await callAPI('/api/summarize', { emailData });
  showResults('Summary', response.summary);
}
```

### 2. Reply Generation with Compose Integration

**Flow:**
1. User clicks "Generate Reply"
2. Extension generates AI reply via backend
3. User clicks "Insert into Reply"
4. Extension opens compose window with pre-filled content

**Code:**
```javascript
async function insertReply(messageId, replyType) {
  const replyText = getGeneratedReply();
  const emailData = await getEmailData(messageId);
  
  await ZMAIL.composer.open({
    type: replyType,
    messageId: messageId,
    subject: 'Re: ' + emailData.subject,
    body: replyText,
    format: 'html'
  });
}
```

**Key Advantages:**
- No manual copy-paste needed
- Native Zoho Mail compose features available
- User can edit before sending
- Preserves reply headers and threading

### 3. Semantic Search

**Flow:**
1. User clicks "Find Related"
2. Extension extracts email context
3. Sends to backend `/api/related-threads`
4. Displays similar conversations

**Implementation:**
```javascript
async function findRelated(messageId) {
  const emailData = await getEmailData(messageId);
  const response = await callAPI('/api/related-threads', {
    subject: emailData.subject,
    from: emailData.from
  });
  displayRelatedEmails(response.threads);
}
```

### 4. Sentiment Analysis

**Flow:**
1. User clicks "Analyze Sentiment"
2. Extension sends email body to backend
3. Receives sentiment label and score
4. Displays with emoji visualization

### 5. Interactive Q&A

**Flow:**
1. User types question in chat box
2. Extension sends query + email context
3. Backend uses RAG to answer
4. Displays answer in results

## API Integration

### Backend Communication

All API calls go through the centralized `callAPI()` function:

```javascript
async function callAPI(endpoint, data) {
  const settings = await getSettings();
  
  const response = await fetch(CONFIG.AGENT_URL + endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${settings.apiKey}`
    },
    body: JSON.stringify(data)
  });
  
  return await response.json();
}
```

### Error Handling

```javascript
try {
  const result = await callAPI('/api/endpoint', data);
  showResults('Success', result);
} catch (error) {
  showError('Operation failed: ' + error.message);
}
```

## Testing

### Manual Testing Checklist

- [ ] Extension loads without errors
- [ ] Settings can be saved and loaded
- [ ] Email summarization works
- [ ] Reply generation creates valid responses
- [ ] Insert into Reply opens compose window
- [ ] Insert into Reply All includes all recipients
- [ ] Related emails found correctly
- [ ] Sentiment analysis accurate
- [ ] Q&A returns relevant answers
- [ ] Error messages display properly

### Test Cases

#### Test Case 1: Reply Insertion
1. Select any email
2. Click "Generate Reply"
3. Wait for AI response
4. Click "Insert into Reply"
5. **Expected**: Compose window opens with reply text
6. **Expected**: Subject is "Re: [original subject]"
7. **Expected**: To/CC fields populated correctly

#### Test Case 2: Settings Persistence
1. Open settings
2. Enter API key and preferences
3. Save settings
4. Reload extension
5. Open settings again
6. **Expected**: All settings retained

#### Test Case 3: Error Handling
1. Enter invalid API key
2. Try to generate reply
3. **Expected**: Clear error message shown
4. **Expected**: Extension doesn't crash

## Building for Production

### Build Process

```bash
# Run build script
./build.sh

# Output: build/openmailbot-zoho-[timestamp].zip
```

### Build Script Steps
1. Clean previous build
2. Copy extension files
3. Validate manifest.json
4. Create ZIP package

### Manual Build

```bash
cd zoho-extension
zip -r openmailbot-zoho.zip \
  manifest.json \
  src/ \
  settings/ \
  assets/ \
  README.md
```

## Deployment

### Zoho Marketplace Submission

1. **Prepare Package**
   - Run build script
   - Test package in developer mode
   - Ensure all features work

2. **Create Listing**
   - Go to [Zoho Marketplace Developer Portal](https://marketplace.zoho.com/developer)
   - Create new extension
   - Fill in details (name, description, category)
   - Upload package ZIP

3. **Provide Assets**
   - Icon (128x128, 256x256)
   - Screenshots (1280x800)
   - Demo video (optional)

4. **Submit for Review**
   - Complete submission form
   - Wait for Zoho review (typically 3-5 days)
   - Address any feedback

### Private Deployment

For enterprise/private use:

```bash
# Share build package directly
cp build/openmailbot-zoho-*.zip /path/to/share/

# Users load via Developer Mode
# No marketplace approval needed
```

## Permissions & Security

### Required Permissions

```json
{
  "scope": "ZohoMail.messages.READ,ZohoMail.messages.CREATE,ZohoMail.accounts.READ"
}
```

- `messages.READ`: Access email content
- `messages.CREATE`: Create drafts and send
- `accounts.READ`: Get user account info

### Security Best Practices

1. **API Key Storage**
   - Store in Zoho Mail secure storage
   - Never log or expose keys
   - Use HTTPS for all API calls

2. **Input Validation**
   ```javascript
   if (!apiKey || apiKey.length < 10) {
     throw new Error('Invalid API key');
   }
   ```

3. **Content Security**
   - Sanitize HTML before display
   - Escape user input
   - Validate API responses

## Troubleshooting

### Common Issues

#### Extension Not Loading
- **Cause**: Manifest errors
- **Fix**: Validate manifest.json with jq
- **Command**: `jq empty manifest.json`

#### Compose Window Not Opening
- **Cause**: Missing composer permission
- **Fix**: Add to manifest scope
- **Code**: `"scope": "...ZohoMail.messages.CREATE..."`

#### API Calls Failing
- **Cause**: CORS or network issues
- **Fix**: Check backend CORS settings
- **Debug**: Monitor browser Network tab

#### Settings Not Saving
- **Cause**: Storage API errors
- **Fix**: Check browser console for errors
- **Code**: Add try-catch around ZMAIL.storage.set()

### Debug Mode

Enable verbose logging:

```javascript
// At top of index.js
const DEBUG = true;

function debugLog(...args) {
  if (DEBUG) {
    console.log('[OpenMailBot]', ...args);
  }
}

// Use throughout code
debugLog('Fetching email:', messageId);
```

## Performance Optimization

### Caching Strategy

```javascript
// Cache email data
const emailCache = new Map();

async function getEmailData(messageId) {
  if (emailCache.has(messageId)) {
    return emailCache.get(messageId);
  }
  
  const data = await ZMAIL.messages.get(messageId);
  emailCache.set(messageId, data);
  return data;
}
```

### Lazy Loading

```javascript
// Load settings only when needed
let cachedSettings = null;

async function getSettings() {
  if (!cachedSettings) {
    cachedSettings = await ZMAIL.storage.get([...]);
  }
  return cachedSettings;
}
```

## Version Management

### Versioning Scheme
- **Major.Minor.Patch** (e.g., 1.0.0)
- **Major**: Breaking changes
- **Minor**: New features
- **Patch**: Bug fixes

### Release Process

1. Update version in manifest.json
2. Update CHANGELOG.md
3. Build package
4. Test thoroughly
5. Submit to marketplace
6. Tag release in git

```bash
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

## Resources

- [Zoho Mail Extensions Documentation](https://www.zoho.com/mail/help/extensions-api.html)
- [Zoho Marketplace Developer Guide](https://marketplace.zoho.com/developer/guide)
- [OpenMailBot Backend API](../docs/API.md)
- [OpenMailBot Main Repository](https://github.com/ankitgoel2004/openmailbot)

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for contribution guidelines.

## Support

- **Issues**: GitHub Issues
- **Email**: dev@openmailbot.com
- **Docs**: https://docs.openmailbot.com

---

Last updated: 2024
