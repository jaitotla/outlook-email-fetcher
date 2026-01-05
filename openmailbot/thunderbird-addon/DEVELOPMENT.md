# OpenMailBot Thunderbird Add-on - Development Guide

## Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/ankitgoel2004/openmailbot.git
   cd openmailbot/openmailbot/thunderbird-addon
   ```

2. **Create icons:**
   - Add icon files to the `icons/` directory
   - See `icons/README.md` for specifications

3. **Load add-on in Thunderbird:**
   - Open Thunderbird
   - Go to `Tools` → `Developer Tools` → `Debug Add-ons`
   - Click `Load Temporary Add-on`
   - Select `manifest.json`

## File Structure

```
thunderbird-addon/
├── manifest.json          # Add-on configuration
├── background.js          # Background service worker
├── popup/                 # Popup UI (when clicking toolbar icon)
│   ├── popup.html
│   ├── popup.css
│   └── popup.js
├── options/              # Settings page
│   ├── options.html
│   ├── options.css
│   └── options.js
├── icons/                # Add-on icons (16, 32, 48, 128px)
├── build.sh             # Build script
└── README.md            # User documentation
```

## API Integration

The add-on communicates with the OpenMailBot backend/agent via REST API:

### Endpoints Used:
- `POST /api/summarize` - Email summarization
- `POST /api/generate-reply` - Reply generation
- `POST /api/related-threads` - Find related emails
- `POST /api/analyze-sentiment` - Sentiment analysis
- `GET /health` - Health check

### Request Format:
```javascript
{
  subject: "Email subject",
  from: "sender@example.com",
  to: ["recipient@example.com"],
  content: "Email content...",
  timestamp: "2026-01-05T12:00:00Z",
  provider: "openai",
  model: "gpt-4"
}
```

## Key Components

### Background Script (background.js)
- Handles API communication
- Manages settings storage
- Processes email content
- Provides message handlers for popup

### Popup (popup/)
- Main user interface
- Quick action buttons
- Results display
- Reply generation UI

### Options (options/)
- Settings configuration
- Connection testing
- API provider selection
- Tone preferences

## Thunderbird APIs Used

### Messages API
- `browser.messageDisplay.getDisplayedMessage()` - Get current email
- `browser.messages.getFull()` - Get complete email content

### Storage API
- `browser.storage.local.get()` - Load settings
- `browser.storage.local.set()` - Save settings

### Runtime API
- `browser.runtime.sendMessage()` - Communication between popup and background
- `browser.runtime.onMessage.addListener()` - Handle messages

### Menus API
- `browser.menus.create()` - Create context menu items

## Testing

### Manual Testing
1. Load add-on in Thunderbird
2. Open any email
3. Click OpenMailBot toolbar icon
4. Test each feature:
   - Summarize
   - Generate Reply
   - Find Related
   - Analyze Sentiment

### Testing with Backend
1. Start backend: `cd backend && npm start`
2. Start agent: `cd agent && python main.py`
3. Configure URLs in add-on settings
4. Click "Test Connection"
5. Test features on real emails

### Testing Offline
- The add-on gracefully handles offline scenarios
- Error messages guide users to start backend/agent

## Building for Distribution

```bash
# Run build script
./build.sh

# This creates openmailbot.xpi
# Users can install it via:
# Tools → Add-ons → Install from file
```

## Debugging

### Enable Debug Logs
In Thunderbird:
1. `Tools` → `Developer Tools` → `Debug Add-ons`
2. Click `Inspect` next to OpenMailBot
3. View console logs

### Common Issues

**"No message displayed"**
- User needs to have an email selected
- Check `browser.messageDisplay.getDisplayedMessage()` returns data

**"Failed to connect"**
- Backend/agent not running
- Check URLs in settings
- Verify CORS headers

**Settings not saving**
- Check `browser.storage.local.set()` errors
- Verify manifest has `storage` permission

## Making Changes

1. **Edit code:**
   - Modify HTML/CSS/JS files
   - Save changes

2. **Reload add-on:**
   - Go to `Debug Add-ons`
   - Click `Reload` button
   - Or remove and re-add the add-on

3. **Test changes:**
   - Open an email
   - Test affected functionality

## Publishing

To publish on Thunderbird Add-ons (ATN):

1. **Create account:** https://addons.thunderbird.net/
2. **Submit add-on:**
   - Upload `openmailbot.xpi`
   - Fill in metadata
   - Submit for review
3. **Review process:**
   - Usually takes a few days
   - Address any feedback
4. **Publish:**
   - Once approved, add-on is live

## Best Practices

- Keep popup lightweight (loads quickly)
- Cache settings in memory
- Show loading states
- Handle errors gracefully
- Provide clear error messages
- Test with various email formats
- Support both light and dark themes

## WebExtension APIs

Thunderbird supports standard WebExtension APIs plus Thunderbird-specific APIs:

- **Standard:** runtime, storage, tabs, menus
- **Thunderbird:** messages, messageDisplay, accounts, compose

Documentation: https://webextension-api.thunderbird.net/

## Version Updates

Update version in `manifest.json`:
```json
{
  "version": "1.1.0"
}
```

Follow semantic versioning:
- **1.0.0** → **1.0.1** - Bug fixes
- **1.0.0** → **1.1.0** - New features
- **1.0.0** → **2.0.0** - Breaking changes

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

---

**Happy coding! 🚀**
