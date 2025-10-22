# 📨 OpenMailBot — Product Requirement Document (PRD)

**Project Name:** OpenMailBot  
**Website:** [https://openmailbot.com](https://openmailbot.com)  
**Type:** Open Source SaaS Platform + Gmail Add-on  
**Version:** 1.0  
**Author:** Product & Engineering Team  
**Last Updated:** October 2025

---

## 🧭 1. Overview

**OpenMailBot** is an open-source **AI email agent** integrated directly into Gmail as an Add-on and supported by a scalable, multi-tenant backend platform.  
It enables users (individuals and companies) to **query**, **summarize**, **analyze**, and **respond** to emails intelligently through natural language interaction.

OpenMailBot connects to users’ Gmail accounts, stores relevant data securely in a vector database, and enables deep retrieval-augmented generation (RAG) over email history to assist with context-aware email drafting and analytics.

---

## 🚀 2. Vision & Goals

**Vision:**  
Empower individuals and organizations to manage and communicate through email more intelligently using open-source AI tooling.

**Goals:**
- Build a transparent, privacy-first, open-source AI assistant for Gmail.
- Support both **Standalone** and **Enterprise** clients.
- Provide **context-aware summaries, analytics, and smart replies**.
- Enable flexible architecture — user chooses:
  - Vector DB (Pinecone or Local)
  - LLM (OpenAI, Gemini, or Local LLM via Ollama)
  - Deployment: self-hosted or company-hosted.

---

## 🧱 3. Core Components

| Component | Description | Technology |
|------------|--------------|-------------|
| **Gmail Add-on (Frontend)** | Conversational AI interface inside Gmail. | Google Apps Script (CardService) |
| **Backend (Agent + API)** | Handles ingestion, embeddings, RAG queries, analytics, and settings. | Python (FastAPI) + Node.js (Express) |
| **Database (Core)** | Stores users, orgs, and metadata. | NoSQL (MongoDB preferred) |
| **Vector Store** | Stores email embeddings and semantic relationships. | Pinecone or Local (FAISS / Milvus) |
| **Graph Store** | Tracks relationships between threads, topics, and participants. | Neo4j or NetworkX |
| **Frontend Platform** | Web interface for onboarding, configuration, and analytics. | Next.js + Tailwind CSS |
| **Authentication** | Google OAuth 2.0 + Workspace Admin consent for enterprise rollout. | Google Identity APIs |

---

## 👥 4. Client Types & Data Segmentation

### 4.1 Standalone Users
- Individual Gmail users.
- Sign up via **Google OAuth** on openmailbot.com.
- Each user’s data and vector namespace are **fully isolated** (`tenant_id = user_id`).
- Can configure:
  - Vector DB (Pinecone / Local)
  - LLM (OpenAI / Gemini / Ollama)
  - Email tone preferences
- Access their personal dashboard for analytics, summaries, and settings.

### 4.2 Enterprise Clients
- Represent a company or organization.
- Domain-wide rollout via Google Workspace Admin consent.
- **Admin Dashboard** allows:
  - Managing employees and permissions
  - Configuring org-wide defaults (LLM, DB, tone)
  - Viewing analytics by user, group, or department
- **Departments/Groups:**
  - e.g., Sales, Support, Engineering
  - Track team KPIs like avg. response time, email volume, sentiment trends.
- Each employee’s data is **individually isolated** (email content not shared between users).
- Admins see aggregated analytics, not raw emails.

---

## 🔐 5. Authentication & Permissions

| Flow | Description |
|------|-------------|
| **Standalone Login** | Google OAuth Sign-In; user consents to Gmail access. |
| **Enterprise Admin Login** | Google Workspace Admin OAuth; domain-wide deployment permissions. |
| **Employee Login** | Google Workspace SSO; limited to personal data. |

OAuth Scopes:
- `https://www.googleapis.com/auth/gmail.readonly`
- `https://www.googleapis.com/auth/gmail.modify`
- `https://www.googleapis.com/auth/userinfo.profile`
- `https://www.googleapis.com/auth/userinfo.email`

---

## 🧩 6. Gmail Add-on Features

**Purpose:**  
Provide a conversational interface inside Gmail to interact with OpenMailBot using natural language.

### 6.1 Core Capabilities
- Summarize email threads  
- Generate context-aware replies  
- Fetch related threads  
- Provide weekly or project summaries  
- Offer analytics like pending replies or engagement trends  
- Allow open-ended questions such as:
  - “What’s the latest on Project Titan?”
  - “Draft a polite update to leadership.”
  - “Summarize client communications this week.”

### 6.2 Setup Flow (Conversational)
- Step-by-step conversational onboarding within Gmail.
- Choose:
  - Vector DB (Pinecone / Local)
  - LLM (OpenAI / Gemini / Ollama)
- Configure tone preferences (Professional, Semi-Professional, Casual, Personal).

### 6.3 Tone and Hierarchy
When generating replies, the system adapts based on:
- **Tone:** professional, semi-professional, casual, personal.
- **Direction:** upward (boss), sideways (peers), downward (team).

---

## 🧮 7. Email Processing Logic

### 7.1 Email Ingestion
1. Gmail API fetches new or updated emails.
2. Extracts metadata:
   - Sender, recipients, subject, thread ID, date, message ID.
3. Stores:
   - Basic email metadata in NoSQL DB.
   - Email content embeddings in Vector DB.
   - Thread relationships in Graph DB.

### 7.2 Context Linking
- Related emails are connected via:
  - Thread ID
  - Reply references
  - Detected shared topics or entities
- Graph built for quick traversal of related communication threads.

### 7.3 RAG Pipeline
1. Query received (user question or summary request).
2. Retrieve relevant email embeddings from Vector DB.
3. Combine with context graph.
4. Feed into selected LLM (OpenAI / Gemini / Ollama).
5. Return structured answer or draft.

---

## 🧠 8. Data Model (Simplified)

### 8.1 NoSQL (MongoDB)
```json
{
  "user": {
    "id": "uuid",
    "tenant_id": "uuid",
    "first_name": "John",
    "last_name": "Doe",
    "dob": "1990-05-12",
    "country": "USA",
    "city": "San Francisco",
    "email": "john@company.com",
    "role": "admin|manager|employee|solo",
    "settings": {
      "llm_provider": "openai",
      "vector_db": "pinecone",
      "tone": "professional"
    }
  },
  "tenant": {
    "id": "uuid",
    "name": "Acme Corp",
    "type": "enterprise",
    "domain": "acme.com",
    "settings": {
      "llm_provider": "gemini",
      "vector_db": "pinecone"
    }
  },
  "group": {
    "id": "uuid",
    "tenant_id": "uuid",
    "name": "Sales",
    "manager_id": "uuid"
  },
  "email_metadata": {
    "id": "uuid",
    "tenant_id": "uuid",
    "user_id": "uuid",
    "subject": "string",
    "thread_id": "string",
    "from": "string",
    "to": ["string"],
    "timestamp": "datetime",
    "labels": ["Project Titan", "Client A"],
    "embedding_id": "string",
    "summary": "string"
  }
}
```

9. Database Architecture
Type	Purpose	Example
NoSQL (MongoDB)	User, tenant, group, metadata, settings	Core DB
Vector DB (Pinecone / FAISS)	Email embeddings	Context retrieval
Graph DB (Neo4j / NetworkX)	Thread and topic relationships	Context graph
Cache (Redis)	Session tokens, temporary query data	Performance optimization
💬 10. User Interface Components
10.1 Web Platform (openmailbot.com)

Built with Next.js + Tailwind.

Key Modules:

Home Page: Explains features, links to GitHub repo (open source).

Signup/Login: Google OAuth & Workspace Admin login.

User Dashboard (Standalone):

Recent summaries

Personal analytics

Settings (tone, LLM, vector DB)

Admin Dashboard (Enterprise):

Add/remove users

Create groups/departments

View team analytics

Configure organization settings

Group Dashboard:

Department-level analytics

Average response times

Sentiment / tone trends

📊 11. Analytics & Insights
Metric	Description	Scope
Avg Response Time	Time to respond to emails	Personal / Group / Company
Email Volume	Emails sent/received per user/group	Personal / Group
Sentiment Trend	Overall tone (positive/neutral/negative)	Group / Company
Top Contacts	Frequent senders or recipients	Personal
Pending Replies	Emails awaiting response	Personal
Tone Distribution	Percentage of professional vs. casual tone	Company

Visualization:
Dashboards use Recharts / Chart.js with role-based access:

Employees: see personal stats

Managers: see group stats

Admins: see organization overview

⚙️ 12. Setup & Configuration Flow

Website Sign-up

Choose Standalone or Enterprise

Sign in with Google

Connect Gmail

Authorize Gmail API access

Select Vector DB

Pinecone (enter key & region) or Local

Select LLM

OpenAI / Gemini / Ollama (local)

Configure Preferences

Tone, hierarchy defaults

Install Add-on

Redirect to Gmail Marketplace installation

🧩 13. Multi-Tenant Architecture

Each tenant (user/org) has its own namespace in:

Vector DB

NoSQL collections (filtered by tenant_id)

Data isolation enforced at all levels:

Standalone: per-user

Enterprise: per-organization, with per-employee isolation

🧰 14. Tech Stack Summary
Layer	Technology
Frontend	Next.js, Tailwind CSS
Add-on	Google Apps Script
Backend APIs	Node.js (Express)
AI Processing	Python (FastAPI)
Database	MongoDB (NoSQL)
Vector DB	Pinecone / FAISS / Milvus
Graph DB	Neo4j / NetworkX
Auth	Google OAuth 2.0 + Workspace Admin
Hosting	Docker, Kubernetes, or self-hosted
Analytics	Chart.js / Recharts
🧠 15. Future Enhancements

Integration with Google One for personal account expansion.

Support for Outlook Add-on in later versions.

Plugin marketplace for third-party analytics.

Automated “Weekly Digest” email reports.

Multi-language support for summarization and generation.

⚖️ 16. Security & Compliance

OAuth-based authentication (no password storage).

Scopes limited to Gmail read/modify where required.

All user data encrypted at rest and in transit.

Employees’ emails remain private — only their embeddings and summaries are processed.

Compliance with GDPR and Google Workspace data-handling policies.

🧩 17. Open Source Policy

Code hosted on GitHub (openmailbot/openmailbot).

MIT License.

Modular architecture — self-hosting supported.

Contributions and extensions encouraged via PRs.

✅ 18. Deliverables

 Gmail Add-on (Apps Script)

 Node.js Backend (Auth, API, Analytics)

 Python Agent (Embeddings, RAG, LLM interface)

 Next.js Web Portal (User/Admin dashboards)

 MongoDB schema and setup

 Pinecone integration module

 Docker + Deployment scripts

 Full API documentation

 GitHub repo with setup guide

🏁 19. Success Metrics
KPI	Target
Time to onboard new user	< 2 minutes
Query latency (summary or reply)	< 4 seconds
System uptime	99.9%
User retention (monthly)	> 80%
Open source stars (first year)	1,000+
🧩 20. Summary

OpenMailBot is a privacy-first, intelligent email assistant that integrates directly with Gmail.
It combines the convenience of conversational AI with powerful email analytics and flexible open-source architecture for both individual and enterprise users.

The platform will live at openmailbot.com and serve as both a product and a framework for building smarter, transparent AI-driven communication tools.
