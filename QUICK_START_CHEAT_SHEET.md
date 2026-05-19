# 🚀 OpenMailBot - Quick Start Cheat Sheet

*Print this page for quick reference!*

---

## ⚡ 5-Minute Quick Start

```bash
# 1. Clone & enter directory
git clone https://github.com/ankitgoel2004/openmailbot.git
cd openmailbot

# 2. Start MongoDB (Docker)
docker run -d --name mongodb -p 27017:27017 \
  -e MONGO_INITDB_ROOT_USERNAME=root \
  -e MONGO_INITDB_ROOT_PASSWORD=password \
  mongo:latest

# 3. Start Backend
cd backend && npm install && npm start
# Terminal 1: Backend running on :3000

# 4. Start Agent
cd ../agent && python -m venv venv
# Windows: venv\Scripts\activate
# Mac/Linux: source venv/bin/activate
pip install -r requirements.txt && python main.py
# Terminal 2: Agent running on :5051

# 5. Start Frontend
cd ../frontend && npm install && npm run dev
# Terminal 3: Frontend on http://localhost:3000

# ✅ All services running!
```

---

## 📦 Installation One-Liners

### Windows (PowerShell as Admin)
```powershell
choco install nodejs python git docker-desktop -y
```

### macOS
```bash
brew install node python@3.11 git docker
```

### Linux (Ubuntu)
```bash
sudo apt install -y nodejs npm python3 python3-pip git docker.io
```

---

## 🔐 API Keys Quick Links

| Provider | Link | Copy Key From |
|----------|------|----------------|
| **OpenAI** | https://platform.openai.com/api-keys | "Create new secret key" |
| **Anthropic** | https://console.anthropic.com/ | "API Keys" section |
| **Groq** | https://console.groq.com/ | "API Keys" section |
| **openmailbot.com** | https://openmailbot.com/ | Dashboard → Settings → API Keys |
| **Google Cloud** | https://console.cloud.google.com/ | OAuth 2.0 Credentials |

---

## 🦙 Ollama Quick Setup

```bash
# 1. Download & Install
# Visit: https://ollama.ai/

# 2. Start Ollama
ollama serve

# 3. In another terminal, download models
ollama pull llama2                    # LLM Chat (3.8GB)
ollama pull nomic-embed-text          # Embeddings (274MB)

# 4. Verify
ollama list

# 5. Configure in OpenMailBot
# Mode: Local
# Agent URL: http://localhost:5051
# LLM Provider: Ollama
# LLM Model: llama2
# Base URL: http://localhost:11434
```

---

## 📧 Gmail Add-on Setup (5 Steps)

1. **Create Google Cloud Project**
   - Go to https://console.cloud.google.com/
   - Click "New Project" → Name: "OpenMailBot" → Create

2. **Enable Gmail API**
   - APIs & Services → Enable APIs → Search "Gmail API" → Enable

3. **Create OAuth Credentials**
   - Credentials → Create Credentials → OAuth 2.0 Client ID
   - Type: Web application
   - Redirect URI: `http://localhost:3000/auth/callback`

4. **Deploy Gmail Add-on**
   - Go to https://script.google.com/
   - Copy code from: `openmailbot/addon/Code.gs`
   - Deploy → New Deployment → Type: Add-on

5. **Install in Gmail**
   - https://gmail.google.com/ → ⚙️ → Settings → Add-ons
   - Search "OpenMailBot" → Install → Grant permissions

---

## 🦣 Thunderbird Extension Setup (5 Steps)

1. **Install Thunderbird**
   - Download from https://www.thunderbird.net/
   - Add your email account

2. **Load Extension**
   - Type `about:debugging` in address bar
   - "This Thunderbird" → "Load Temporary Add-on"
   - Select: `openmailbot/addon/thunderbird-addon/manifest.json`

3. **Open Settings**
   - Right-click OpenMailBot icon → Options

4. **Choose Mode**
   - **Manotr**: Cloud service (easiest)
   - **Local**: `http://localhost:5051`
   - **External**: Custom URL

5. **Configure LLM**
   - Select provider (OpenAI, Anthropic, Ollama, etc.)
   - Enter API key or Ollama URL
   - Click "Validate" → "Save"

---

## 🏠 Local Development Commands

```bash
# Start all services in separate terminals

# Terminal 1: Backend
cd backend && npm start

# Terminal 2: Agent
cd agent && source venv/bin/activate && python main.py

# Terminal 3: Frontend
cd frontend && npm run dev

# Terminal 4: MongoDB (if not using Docker)
# macOS: brew services start mongodb-community
# Linux: sudo systemctl start mongod
# Windows: net start MongoDB

# Terminal 5: Ollama (optional)
ollama serve
```

---

## 🔍 Service Health Check

```bash
# Test all endpoints

curl http://localhost:3000/health     # Backend
curl http://localhost:5051/health     # Agent
curl http://localhost:11434/api/tags  # Ollama (if running)

# If all return data ✅ Setup is working!
```

---

## 📝 Environment Variables Template

```bash
# .env file in root directory

# Backend
BACKEND_URL=http://localhost:3000
BACKEND_PORT=3000

# Agent
AGENT_URL=http://localhost:5051
AGENT_PORT=5051

# Database
MONGODB_URI=mongodb://root:password@localhost:27017/openmailbot

# Google OAuth
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret

# LLM Provider (choose one)
LLM_PROVIDER=openai          # or: anthropic, groq, ollama
LLM_API_KEY=sk-your-key
LLM_MODEL=gpt-4o-mini

# Ollama (if using local LLM)
OLLAMA_BASE_URL=http://localhost:11434

# Vector Database
VECTOR_DB=pinecone           # or: local, qdrant
PINECONE_API_KEY=pk-your-key
```

---

## 🚨 Common Issues & Fixes

| Issue | Fix |
|-------|-----|
| Port already in use | `lsof -i :5051` (Mac/Linux) or `netstat -ano \| findstr :5051` (Windows) |
| MongoDB won't connect | `docker run -d --name mongodb -p 27017:27017 mongo:latest` |
| Agent won't start | Check Python version: `python --version` (need 3.9+) |
| Gmail Add-on not showing | Hard refresh: Ctrl+Shift+R or Cmd+Shift+R |
| Ollama connection error | `curl http://localhost:11434/api/tags` to verify running |
| API key invalid | Copy entire key (check for trailing spaces!) |

---

## 🎯 Ollama Model Selection

```
For Testing:        llama2 (3.8GB, fast)
For Production:     llama2:13b (7.4GB, balanced)
For High Quality:   mistral (4.1GB, excellent)
For Embeddings:     nomic-embed-text (274MB, required)

Download: ollama pull <model-name>
List all: ollama list
```

---

## 🔗 Important URLs

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:3000/api |
| Agent API | http://localhost:5051/api |
| MongoDB Atlas | https://www.mongodb.com/cloud/atlas |
| Neo4j Cloud | https://neo4j.com/cloud/aura/ |
| Pinecone | https://www.pinecone.io/ |
| Ollama | https://ollama.ai/ |
| OpenMailBot | https://openmailbot.com/ |
| GitHub | https://github.com/ankitgoel2004/openmailbot |

---

## 🆘 Get Help

- 📖 Full Guide: [COMPLETE_SETUP_GUIDE.md](COMPLETE_SETUP_GUIDE.md)
- 💬 GitHub Issues: https://github.com/ankitgoel2004/openmailbot/issues
- 📧 Email: support@openmailbot.com
- 🤝 Discord: https://discord.gg/openmailbot

---

**Pro Tip:** Save this file locally for quick reference! 📌
