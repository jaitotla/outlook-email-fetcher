# OpenMailBot for Zoho Mail

AI-powered email assistant extension for Zoho Mail. Get smart summaries, AI-generated replies, semantic search, and more—all directly in your inbox.

## ✨ Features

### 📝 Email Summarization
- Instant summaries of long email threads
- Key points extraction
- Action items identification

### ✍️ AI-Generated Replies
- Context-aware response generation
- Multiple tone options (professional, friendly, concise, detailed)
- **Direct insertion into Zoho Mail compose window**
- Reply and Reply All support

### 🔗 Semantic Search
- Find related emails using AI-powered similarity
- Cross-reference conversations
- Discover relevant context automatically

### 😊 Sentiment Analysis
- Understand email tone and sentiment
- Prioritize urgent or negative emails
- Track emotional context

### 💬 Interactive Chat
- Ask questions about emails
- Extract specific information
- Get AI-powered answers

## 🚀 Installation

### From Zoho Marketplace
1. Visit [Zoho Marketplace](https://marketplace.zoho.com)
2. Search for "OpenMailBot"
3. Click "Install"
4. Configure your API key in settings

### Manual Installation (Development)
1. Download this repository
2. Open Zoho Mail
3. Go to Settings → Extensions → Developer Mode
4. Click "Load Unpacked Extension"
5. Select the `zoho-extension` folder

## ⚙️ Configuration

### 1. Get API Key
- Visit [OpenMailBot Dashboard](https://app.openmailbot.com)
- Sign up or log in
- Go to Settings → API Keys
- Generate a new API key

### 2. Configure Extension
1. Click the OpenMailBot icon in Zoho Mail
2. Click "Configure Settings"
3. Enter your API key
4. Choose your preferred LLM provider and tone
5. Save settings

## 📖 Usage

### Summarize Email
1. Select an email
2. Click "📝 Summarize Thread"
3. View AI-generated summary

### Generate Reply
1. Select an email
2. Click "✍️ Generate Reply"
3. Review AI-generated response
4. Click **"Insert into Reply"** or **"Insert into Reply All"**
5. The compose window opens with the reply pre-filled
6. Edit if needed and send

### Find Related Emails
1. Select an email
2. Click "🔗 Find Related"
3. Browse semantically similar conversations

### Ask Questions
1. Select an email
2. Type your question in the chat box
3. Get instant AI-powered answers

## 🔧 Advanced Features

### Direct Compose Integration
OpenMailBot uses the Zoho Mail Composer API to insert AI-generated replies directly into the compose window:

```javascript
await ZMAIL.composer.open({
  type: 'reply',  // or 'replyAll'
  messageId: messageId,
  subject: 'Re: ' + emailData.subject,
  body: aiGeneratedReply,
  format: 'html'
});
```

This provides a seamless experience where you can:
- Review and edit the AI-generated reply
- Add or remove recipients
- Attach files
- Schedule sending
- Use all native Zoho Mail compose features

### LLM Provider Options
- **OpenAI**: GPT-4 for highest quality
- **Anthropic**: Claude for detailed analysis
- **Ollama**: Local models for privacy

### Reply Tone Customization
- **Professional**: Formal business communication
- **Friendly**: Warm and approachable
- **Concise**: Brief and to-the-point
- **Detailed**: Comprehensive responses

## 🔒 Privacy & Security

- API calls are encrypted (HTTPS)
- Email content processed securely
- No data stored on servers (when using local LLM)
- Settings stored locally in Zoho Mail

## 🐛 Troubleshooting

### "API Key Invalid" Error
- Verify API key is correct
- Check if key is still active
- Regenerate key if needed

### "Failed to Connect" Error
- Check internet connection
- Verify backend URL is correct
- Check firewall settings

### Reply Not Inserting
- Ensure compose permissions are granted
- Check Zoho Mail version compatibility
- Try reloading the extension

## 📝 Development

### Project Structure
```
zoho-extension/
├── manifest.json          # Extension manifest
├── src/
│   ├── index.js          # Main extension code
│   └── styles.css        # UI styles
├── settings/
│   ├── settings.html     # Settings page
│   └── settings.js       # Settings logic
└── assets/               # Icons and images
```

### Build & Test
```bash
# No build step required - pure JavaScript

# Test in Zoho Mail
1. Enable Developer Mode
2. Load unpacked extension
3. Test features in inbox

# Debug
- Use browser DevTools
- Check console for errors
- Monitor network requests
```

### API Integration
The extension communicates with the OpenMailBot backend:

```javascript
// Summarize
POST /api/summarize
{
  "messageId": "string",
  "emailData": { ... }
}

// Generate Reply
POST /api/generate-reply
{
  "messageId": "string",
  "emailData": { ... },
  "tone": "professional"
}

// Related Threads
POST /api/related-threads
{
  "messageId": "string",
  "subject": "string",
  "from": "email@example.com"
}
```

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

MIT License - see [LICENSE](../LICENSE) for details

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/ankitgoel2004/openmailbot/issues)
- **Email**: support@openmailbot.com
- **Docs**: [Documentation](https://docs.openmailbot.com)

## 🎯 Roadmap

- [ ] Calendar integration
- [ ] Task creation from emails
- [ ] Multi-language support
- [ ] Custom AI prompts
- [ ] Offline mode
- [ ] Mobile app

---

Built with ❤️ by the OpenMailBot Team
