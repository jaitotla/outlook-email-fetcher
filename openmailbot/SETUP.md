# 🚀 OpenMailBot - Quick Start Guide

Get OpenMailBot up and running in minutes!

## 📋 Prerequisites

Before you begin, ensure you have:

- **Node.js** 18+ ([Download](https://nodejs.org/))
- **Python** 3.9+ ([Download](https://www.python.org/))
- **MongoDB** ([Local](https://www.mongodb.com/try/download/community) or [Atlas](https://www.mongodb.com/cloud/atlas))
- **Neo4j** ([Download](https://neo4j.com/download/) or [Cloud](https://neo4j.com/cloud/))
- **Git** ([Download](https://git-scm.com/))

## 🎯 Quick Start with Docker (Recommended)

### 1. Clone the Repository

```bash
git clone https://github.com/ankitgoel2004/openmailbot.git
cd openmailbot/openmailbot
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
nano .env  # or use your favorite editor
```

**Required variables:**
- `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` (from [Google Cloud Console](https://console.cloud.google.com/))
- `JWT_SECRET` (generate: `openssl rand -base64 32`)
- `NEXTAUTH_SECRET` (generate: `openssl rand -base64 32`)
- Database passwords

### 3. Start All Services

```bash
docker-compose up -d
```

This starts:
- ✅ MongoDB (port 27017)
- ✅ Neo4j (ports 7474, 7687)
- ✅ Backend API (port 5000)
- ✅ Python Agent (port 8000)
- ✅ Frontend (port 3000)

### 4. Access the Application

- **Web App**: http://localhost:3000
- **Backend API**: http://localhost:5000/health
- **Python Agent**: http://localhost:8000/health
- **Neo4j Browser**: http://localhost:7474

---

## 🔧 Manual Setup (Without Docker)

### Step 1: Setup MongoDB

**Option A: Local MongoDB**
```bash
# macOS
brew install mongodb-community@7.0
brew services start mongodb-community@7.0

# Ubuntu/Debian
sudo apt-get install mongodb-org
sudo systemctl start mongod
```

**Option B: MongoDB Atlas** (Cloud)
1. Create free cluster at https://www.mongodb.com/cloud/atlas
2. Get connection string
3. Update `.env` with connection string

### Step 2: Setup Neo4j

**Option A: Local Neo4j**
```bash
# Download from https://neo4j.com/download/
# Or use Docker:
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your-password \
  neo4j:5.15
```

**Option B: Neo4j Aura** (Cloud)
1. Create free instance at https://neo4j.com/cloud/aura/
2. Get connection URI
3. Update `.env` with credentials

### Step 3: Setup Backend

```bash
cd backend
cp .env.example .env
# Edit .env with your credentials
npm install
npm start
```

Backend runs on http://localhost:5000

### Step 4: Setup Python Agent

```bash
cd ../agent
cp .env.example .env
# Edit .env with your credentials
pip install -r requirements.txt
python main.py
```

Agent runs on http://localhost:8000

### Step 5: Setup Frontend

```bash
cd ../frontend
cp .env.example .env
# Edit .env with your credentials
npm install
npm run dev
```

Frontend runs on http://localhost:3000

---

## 🔑 OAuth Setup

### Google OAuth (Required)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable **Gmail API** and **Google+ API**
4. Create **OAuth 2.0 Client ID**:
   - Application type: Web application
   - Authorized redirect URIs:
     - `http://localhost:5000/auth/google/callback`
     - `http://localhost:3000/api/auth/callback/google`
5. Copy **Client ID** and **Client Secret** to `.env`

### Microsoft OAuth (Optional for Outlook)

1. Go to [Azure Portal](https://portal.azure.com/)
2. Register new application
3. Add **Microsoft Graph** permissions:
   - `Mail.Read`
   - `User.Read`
4. Add redirect URIs:
   - `http://localhost:5000/auth/microsoft/callback`
   - `http://localhost:3000/api/auth/callback/microsoft`
5. Copy **Application ID** and **Secret** to `.env`

---

## 🤖 AI Provider Setup

### OpenAI (Recommended)

1. Get API key from https://platform.openai.com/
2. Add to `.env`:
   ```
   OPENAI_API_KEY=sk-your-key-here
   LLM_PROVIDER=openai
   EMBEDDING_PROVIDER=openai
   ```

### Anthropic Claude (Alternative)

1. Get API key from https://console.anthropic.com/
2. Add to `.env`:
   ```
   ANTHROPIC_API_KEY=sk-ant-your-key-here
   LLM_PROVIDER=anthropic
   ```

### Ollama (Local/Self-hosted)

1. Install Ollama: https://ollama.ai/
2. Pull a model:
   ```bash
   ollama pull llama2
   ```
3. Update `.env`:
   ```
   LLM_PROVIDER=ollama
   OLLAMA_BASE_URL=http://localhost:11434
   ```

---

## 💾 Vector Database Setup

### Option 1: FAISS (Local - No setup required)

```env
VECTOR_DB_TYPE=faiss
```

Perfect for self-hosting and privacy. No external dependencies.

### Option 2: Pinecone (Cloud)

1. Create account at https://www.pinecone.io/
2. Create an index:
   - Dimensions: `1536` (for OpenAI embeddings)
   - Metric: `cosine`
3. Add to `.env`:
   ```
   VECTOR_DB_TYPE=pinecone
   PINECONE_API_KEY=your-key-here
   PINECONE_ENVIRONMENT=your-env
   ```

---

## 📱 Gmail Add-on Setup

1. Go to https://script.google.com
2. Create new project
3. Copy contents from `addon/Code.gs`
4. Copy `addon/appsscript.json`
5. Update `BACKEND_API_URL` in Code.gs
6. Deploy as Gmail add-on
7. Test in Gmail

**Detailed guide**: See [addon/README.md](addon/README.md)

---

## ✅ Verify Installation

### Check Services

```bash
# Backend
curl http://localhost:5000/health

# Agent
curl http://localhost:8000/health

# Frontend (in browser)
# http://localhost:3000
```

### Test Database Connections

```bash
# MongoDB
mongosh "mongodb://admin:changeme@localhost:27017"

# Neo4j
# Open http://localhost:7474 in browser
```

---

## 📊 First Steps After Installation

1. **Sign Up**: Go to http://localhost:3000/auth/signup
2. **Connect Email**: Sign in with Google
3. **Configure AI**: Visit Settings to choose LLM provider
4. **Sync Emails**: Emails will be imported automatically
5. **Try Chat**: Ask "Summarize my recent emails"

---

## 🔄 Common Commands

```bash
# Start all services (Docker)
docker-compose up -d

# Stop all services
docker-compose down

# View logs
docker-compose logs -f

# Restart a service
docker-compose restart backend

# Backend only
cd backend && npm run dev

# Agent only
cd agent && python main.py

# Frontend only
cd frontend && npm run dev
```

---

## 🐛 Troubleshooting

### MongoDB Connection Failed
- Check MongoDB is running: `mongosh`
- Verify connection string in `.env`
- Check firewall settings

### Neo4j Connection Failed
- Check Neo4j is running: http://localhost:7474
- Verify credentials in `.env`
- Ensure ports 7474 and 7687 are not in use

### OAuth Errors
- Verify redirect URIs match exactly
- Check API credentials are correct
- Ensure APIs are enabled in Google Cloud Console

### Agent Import Errors
```bash
cd agent
pip install --upgrade -r requirements.txt
```

### Frontend Build Errors
```bash
cd frontend
rm -rf node_modules .next
npm install
npm run dev
```

---

## 📚 Next Steps

- **Full Documentation**: [README.md](README.md)
- **API Reference**: [docs/API.md](docs/API.md)
- **Backend Guide**: [backend/README.md](backend/README.md)
- **Agent Guide**: [agent/README.md](agent/README.md)
- **Development Status**: [DEVELOPMENT_STATUS.md](../DEVELOPMENT_STATUS.md)

---

## 🆘 Getting Help

- **GitHub Issues**: https://github.com/ankitgoel2004/openmailbot/issues
- **Discussions**: https://github.com/ankitgoel2004/openmailbot/discussions
- **Email**: support@openmailbot.dev (coming soon)

---

## 🎉 Success!

You're all set! OpenMailBot is now running.

**Pro Tips:**
- Use Docker for easiest setup
- Start with FAISS for vector DB (no external dependencies)
- OpenAI provides best results but costs money
- Try Ollama for completely free local AI

Happy email managing! 🚀
