# 🤖 OpenMailBot

**Open-source AI Email Assistant for Gmail, Outlook & Thunderbird**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Node.js](https://img.shields.io/badge/Node.js-18+-green.svg)](https://nodejs.org/)
[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org/)
[![Next.js](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)
[![Thunderbird](https://img.shields.io/badge/Thunderbird-102+-blue.svg)](https://www.thunderbird.net/)

Transform your email experience with AI-powered summaries, intelligent search, and smart reply generation. OpenMailBot integrates seamlessly with Gmail, Outlook, and Thunderbird, offering a web portal, Gmail add-on, and Thunderbird extension.

## ✨ Features

- **🎯 Smart Summaries** - Get instant AI-powered summaries of long email threads
- **💬 AI Chat** - Ask questions about your emails in natural language
- **✍️ Smart Replies** - Generate context-aware responses with customizable tone
- **🔍 Semantic Search** - Find emails by meaning, not just keywords
- **📊 Analytics** - Track response times, email volume, and sentiment trends
- **🔐 Privacy First** - Self-host with local AI models (Ollama, FAISS)
- **🌐 Multi-Provider** - Choose between OpenAI, Anthropic, or local LLMs
- **👥 Multi-Tenant** - Perfect for teams and organizations

## 🚀 Quick Start

### With Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/ankitgoel2004/openmailbot.git
cd openmailbot/openmailbot

# Run setup script
./setup.sh

# Configure environment
cp .env.example .env
nano .env  # Add your credentials

# Start all services
docker-compose up -d

# Access the application
open http://localhost:3000
```

### Without Docker

```bash
# Clone and setup
git clone https://github.com/ankitgoel2004/openmailbot.git
cd openmailbot/openmailbot
./setup.sh

# Start MongoDB & Neo4j
# Then start each service:

# Backend (Terminal 1)
cd backend && npm start

# Python Agent (Terminal 2)
cd agent && source venv/bin/activate && python main.py

# Frontend (Terminal 3)
cd frontend && npm run dev
```

**📖 Detailed Setup**: See [SETUP.md](SETUP.md)

## 🏗️ Architecture

```
┌─────────────────┐
│  Gmail Add-on   │◄────┐
│ (Apps Script)   │     │
└─────────────────┘     │
                        │
┌─────────────────┐     │    ┌──────────────────┐
│  Web Portal     │◄────┼───►│  Backend API     │
│  (Next.js)      │     │    │  (Node.js)       │
└─────────────────┘     │    └────────┬─────────┘
                        │             │
                        │             ▼
                        │    ┌──────────────────┐
                        └───►│  Python Agent    │
                             │  (FastAPI)       │
                             └────────┬─────────┘
                                      │
                  ┌───────────────────┼───────────────────┐
                  ▼                   ▼                   ▼
           ┌──────────┐       ┌──────────┐      ┌──────────┐
           │ MongoDB  │       │ Vector DB│      │ Graph DB │
           │          │       │ Pinecone │      │  Neo4j   │
           │          │       │ / FAISS  │      │          │
           └──────────┘       └──────────┘      └──────────┘
```

## 📦 Technology Stack

### Backend
- **Node.js 18+** with Express.js
- **MongoDB** for data storage
- **Passport.js** for OAuth authentication
- **JWT** for session management

### Python Agent
- **FastAPI** for async API server
- **OpenAI / Anthropic / Ollama** for LLM
- **Pinecone / FAISS** for vector search
- **Neo4j** for relationship mapping

### Frontend
- **Next.js 14** with App Router
- **TypeScript** for type safety
- **Tailwind CSS** for styling
- **NextAuth.js** for authentication

### Gmail Add-on
- **Google Apps Script**
- **CardService** for UI

### Thunderbird Add-on
- **WebExtension** API
- **Modern UI** with popup interface

## 📁 Project Structure

```
openmailbot/
├── backend/           # Node.js REST API
│   ├── controllers/   # Route controllers
│   ├── models/        # MongoDB models
│   ├── routes/        # API routes
│   └── config/        # OAuth & configs
├── agent/             # Python AI agent
│   ├── services/      # Core AI services
│   │   ├── embeddings.py
│   │   ├── llm.py
│   │   ├── rag.py
│   │   └── ingestion.py
│   ├── vector/        # Vector DB clients
│   ├── graph/         # Graph DB client
│   └── database/      # MongoDB client
├── frontend/          # Next.js web app
│   └── src/
│       ├── app/       # App router pages
│       └── components/# React components
├── addon/             # Gmail add-on
│   ├── Code.gs        # Main add-on code
│   └── appsscript.json
├── thunderbird-addon/ # Thunderbird extension
│   ├── manifest.json  # Extension manifest
│   ├── background.js  # Background script
│   ├── popup/         # UI components
│   └── options/       # Settings page
├── docker/            # Docker configs
└── docker-compose.yml # Multi-service setup
```

## 🔧 Configuration

OpenMailBot is highly configurable. Choose your preferred providers:

### LLM Providers
- **OpenAI** (GPT-4, GPT-3.5) - Best quality, costs money
- **Anthropic** (Claude 3) - Great quality, costs money
- **Ollama** (Llama 2, Mistral) - Free, runs locally

### Vector Databases
- **Pinecone** - Cloud-based, scalable
- **FAISS** - Local, privacy-focused, free

### Embedding Models
- **OpenAI** (text-embedding-ada-002) - 1536 dimensions
- **Sentence Transformers** - Local, free

## 📖 Documentation

- **[Setup Guide](SETUP.md)** - Detailed installation instructions
- **[API Documentation](docs/API.md)** - REST API reference
- **[Backend Guide](backend/README.md)** - Backend architecture
- **[Agent Guide](agent/README.md)** - Python agent details
- **[Development Status](../DEVELOPMENT_STATUS.md)** - Project roadmap

## 🤝 Contributing

We welcome contributions! Here's how:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📧 Support

- **GitHub Issues**: [Report bugs](https://github.com/ankitgoel2004/openmailbot/issues)
- **Discussions**: [Ask questions](https://github.com/ankitgoel2004/openmailbot/discussions)

---

**Made with ❤️ by the OpenMailBot Team**
