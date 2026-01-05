# OpenMailBot - Thunderbird Add-on

AI-powered email assistant for Mozilla Thunderbird. Get smart summaries, AI-generated replies, semantic search, and sentiment analysis directly in Thunderbird.

## ✨ Features

- **📝 Email Summaries** - Instantly summarize long email threads
- **✍️ Smart Replies** - Generate context-aware responses with customizable tone
- **🔍 Find Related** - Discover related emails using semantic search
- **😊 Sentiment Analysis** - Analyze the emotional tone of emails
- **🎨 Clean UI** - Beautiful popup interface integrated into Thunderbird
- **⚙️ Configurable** - Choose your AI provider (OpenAI, Anthropic, Ollama)
- **🔐 Privacy-Focused** - Self-host option with local AI models

## 📋 Prerequisites

Before installing the add-on, you need:

1. **Mozilla Thunderbird** 102.0 or later
2. **OpenMailBot Backend & Agent** running:
   - Backend API (default: http://localhost:5000)
   - Python Agent (default: http://localhost:8000)

## 🚀 Installation

### Method 1: Install from File (Development)

1. **Package the add-on:**
   ```bash
   cd thunderbird-addon
   zip -r openmailbot.xpi manifest.json background.js popup/ options/ icons/
   ```

2. **Install in Thunderbird:**
   - Open Thunderbird
   - Go to `Tools` → `Add-ons and Themes` (or press `Ctrl+Shift+A`)
   - Click the gear icon ⚙️
   - Select `Install Add-on From File...`
   - Choose the `openmailbot.xpi` file
   - Click `Install Now`

### Method 2: Load Temporarily (Testing)

1. Open Thunderbird
2. Go to `Tools` → `Developer Tools` → `Debug Add-ons`
3. Click `Load Temporary Add-on...`
4. Navigate to the `thunderbird-addon` folder
5. Select the `manifest.json` file

## ⚙️ Configuration

### First-Time Setup

1. After installation, click the OpenMailBot icon in the toolbar
2. Click **⚙️ Settings** at the bottom
3. Configure the following:

   **Connection Settings:**
   - Backend API URL: `http://localhost:5000`
   - Python Agent URL: `http://localhost:8000`
   - User ID: Your email address (optional)

   **AI Configuration:**
   - LLM Provider: Choose between OpenAI, Anthropic, or Ollama
   - Model: Select the AI model to use
   - Default Reply Tone: Professional, Semi-Professional, Casual, or Personal

   **Vector Database:**
   - Vector DB Provider: FAISS (local) or Pinecone (cloud)
   - Embedding Provider: OpenAI or Local

4. Click **Test Connection** to verify the setup
5. Click **Save Settings**

### Backend Setup

Make sure your OpenMailBot backend and agent are running:

```bash
# Start Backend
cd backend
npm start

# Start Agent (in another terminal)
cd agent
source venv/bin/activate
python main.py
```

Or use Docker:

```bash
cd openmailbot
docker-compose up -d
```

## 🎯 Usage

### Summarize Email

1. Open any email in Thunderbird
2. Click the OpenMailBot icon in the toolbar
3. Click **📝 Summarize Email**
4. View the AI-generated summary

### Generate Smart Reply

1. Open the email you want to reply to
2. Click the OpenMailBot icon
3. Click **✍️ Generate Reply**
4. Optionally add context for the reply
5. Choose the tone (Professional, Casual, etc.)
6. Click **Generate**
7. Copy the generated reply and paste into Thunderbird's compose window

### Find Related Emails

1. Open an email
2. Click the OpenMailBot icon
3. Click **🔍 Find Related**
4. View similar emails based on semantic similarity

### Analyze Sentiment

1. Open an email
2. Click the OpenMailBot icon
3. Click **😊 Analyze Sentiment**
4. See the emotional tone (Positive, Negative, Neutral)

## 🔧 Customization

### Change AI Provider

1. Open Settings (⚙️ button in popup)
2. Change **LLM Provider** to:
   - **OpenAI** - Best quality, requires API key
   - **Anthropic** - Claude models, requires API key
   - **Ollama** - Free local models
3. Select the appropriate **Model**
4. Save settings

### Adjust Reply Tone

The default tone can be set in Settings, but you can also change it per-reply:
- **Professional** - Formal business communication
- **Semi-Professional** - Friendly but professional
- **Casual** - Relaxed and conversational
- **Personal** - Warm and personal

### Use Local AI (Privacy Mode)

For complete privacy, use local models:

1. Install Ollama: https://ollama.ai/
2. Pull a model: `ollama pull llama2`
3. In Settings, set:
   - LLM Provider: Ollama
   - Vector DB: FAISS
   - Embedding Provider: Local
4. Your emails never leave your computer!

## 📁 File Structure

```
thunderbird-addon/
├── manifest.json          # Add-on manifest
├── background.js          # Background script
├── popup/
│   ├── popup.html        # Main popup UI
│   ├── popup.css         # Popup styles
│   └── popup.js          # Popup logic
├── options/
│   ├── options.html      # Settings page
│   ├── options.css       # Settings styles
│   └── options.js        # Settings logic
├── icons/                # Add-on icons
│   ├── icon-16.png
│   ├── icon-32.png
│   ├── icon-48.png
│   └── icon-128.png
└── README.md            # This file
```

## 🔑 Permissions Explained

The add-on requests the following permissions:

- **messagesRead** - Read email content for summarization and analysis
- **accountsRead** - Access email account information
- **storage** - Save your settings locally
- **tabs** - Interact with Thunderbird tabs

**Privacy Note:** Your emails are only sent to the backend/agent you configure. By default, this is localhost (your own computer).

## 🐛 Troubleshooting

### "Failed to connect to OpenMailBot agent"

**Solution:**
1. Make sure the backend and agent are running
2. Check the URLs in Settings match your setup
3. Click "Test Connection" to verify
4. Check firewall isn't blocking connections

### "No message displayed"

**Solution:**
1. Make sure you have an email open
2. The popup only works when viewing an email
3. Try selecting a different email

### Generate Reply not working

**Solution:**
1. Check your AI provider settings
2. If using OpenAI/Anthropic, verify API key is set in agent
3. If using Ollama, make sure the model is downloaded

### Related Emails shows nothing

**Solution:**
1. You need to have emails indexed first
2. Use the backend API to ingest emails
3. Wait for embeddings to be generated

## 📚 API Endpoints Used

The add-on communicates with these agent endpoints:

- `POST /api/summarize` - Generate email summary
- `POST /api/generate-reply` - Generate smart reply
- `POST /api/related-threads` - Find related emails
- `POST /api/analyze-sentiment` - Analyze sentiment
- `GET /health` - Check agent status

## 🔄 Updates

To update the add-on:

1. Get the latest version
2. Rebuild the XPI file
3. In Thunderbird, go to Add-ons
4. Click the gear icon → Install Add-on From File
5. Select the new XPI file

## 🤝 Contributing

Found a bug or want to add a feature?

1. Open an issue: https://github.com/ankitgoel2004/openmailbot/issues
2. Submit a pull request
3. Join the discussion

## 📄 License

MIT License - See LICENSE file for details

## 🆘 Support

- **Documentation**: [Main README](../README.md)
- **Setup Guide**: [SETUP.md](../SETUP.md)
- **Issues**: https://github.com/ankitgoel2004/openmailbot/issues
- **Discussions**: https://github.com/ankitgoel2004/openmailbot/discussions

## 🎉 Credits

Built with ❤️ by the OpenMailBot Team

Powered by:
- Mozilla Thunderbird WebExtension APIs
- OpenAI / Anthropic / Ollama
- FastAPI
- Your creativity!

---

**Enjoy your AI email assistant in Thunderbird! 🚀**
