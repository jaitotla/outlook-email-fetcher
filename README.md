# OpenMailBot

AI-powered email assistant for Gmail and Thunderbird. Summarize, draft, search, and organize emails with multi-provider LLM support.

## Installation

### macOS / Linux

```bash
curl -fsSL https://raw.githubusercontent.com/ankitgoel2004/openmailbot/main/run.sh | sh
```

or manually:

```bash
git clone https://github.com/ankitgoel2004/openmailbot.git
cd openmailbot
chmod +x run.sh
./run.sh
```

### Windows

```powershell
git clone https://github.com/ankitgoel2004/openmailbot.git
cd openmailbot
python -m venv backend/venv
backend\venv\Scripts\activate
pip install --upgrade pip setuptools wheel
cd backend
pip install -r requirements.txt
python main.py
```

### Requirements

- Python 3.8+
- Git
- 500MB free disk space
- Internet connection for LLM providers (optional for local Ollama)

# Activate virtual environment

# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate

# Install Python packages
pip install -r requirements.txt


```


## 🌐 4. Google Gmail Add-on Setup

### Step 4.1: Create Google Cloud Project

1. **Go to Google Cloud Console**
   - Visit: https://console.cloud.google.com/
   - Click **"Select a Project"** → **"New Project"**
   - Name: `OpenMailBot` → Create

2. **Enable Gmail API**
   - In left sidebar, click **"APIs & Services"** → **"Enable APIs and Services"**
   - Search: `Gmail API`
   - Click **"Gmail API"** → **"Enable"**

3. **Create OAuth 2.0 Credentials**
   - Go to **"Credentials"** in left sidebar
   - Click **"Create Credentials"** → **"OAuth 2.0 Client ID"**
   - Choose **"Web application"**
   - Add Authorized Redirect URI: `http://localhost:3000/auth/callback`
   - Click **"Create"**
   - **Save** `Client ID` and `Client Secret` (you'll need these)

### Step 4.2: Create Gmail Add-on Script

1. **Go to Google Apps Script**
   - Visit: https://script.google.com/
   - Click **"New Project"**
   - Name it: `OpenMailBot Gmail Add-on`

2. **Copy Script Code**
   - Go to your cloned repository: `openmailbot/addon/Code.gs`
   - Copy the entire content
   - Paste into Google Apps Script editor
   - Click **"Save"** (Ctrl+S)

3. **Deploy as Add-on**
   - Click **"Deploy"** → **"New Deployment"**
   - Type: Select **"Add-on"**
   - Description: `OpenMailBot - AI Email Assistant`
   - Click **"Deploy"**

### Step 4.3: Install Gmail Add-on

1. **Open Gmail**
   - Go to https://gmail.google.com/
   - Click the **gear icon** ⚙️ (top right)
   - Select **"See all settings"**

2. **Install Add-on**
   - Go to **"Add-ons"** tab
   - Search: `OpenMailBot`
   - Click **"Install"**
   - Grant permissions when prompted

3. **Configure Settings**
   - Open Gmail
   - Click the **sidebar** icon (left menu)
   - Find **"OpenMailBot"** extension
   - Click **"Settings"**
   - Enter your API credentials (see Section 7 for API keys)

### Step 4.4: Verify Installation

```
✅ OpenMailBot icon appears in Gmail sidebar
✅ Click icon to open settings panel
✅ Settings shows mode selector (Manotr/Local/External)
✅ Can select LLM provider and model
```

---

## 🦣 5. Thunderbird Add-on Setup

### Step 5.1: Install Thunderbird

1. **Download Thunderbird**
   - Visit: https://www.thunderbird.net/
   - Click **"Free Download"**
   - Install following on-screen instructions
   - Launch Thunderbird

2. **Add Email Account**
   - Click **"Menu"** ☰ (top right) → **"Settings"** → **"Mail"** → **"Accounts"**
   - Or click **"Create"** button during first launch
   - Enter email address and password
   - Click **"Continue"** and **"Done"**

### Step 5.2: Load OpenMailBot Extension

#### Method A: Development Mode (For Development)

1. **Type about:debugging**
   - In Thunderbird address bar, type: `about:debugging`
   - Press Enter

2. **Load Temporary Add-on**
   - Click **"This Thunderbird"** (left sidebar)
   - Click **"Load Temporary Add-on..."**
   - Navigate to: `openmailbot/addon/thunderbird-addon/manifest.json`
   - Select it and click **"Open"**

3. **Verify Loading**
   - Check sidebar for **"OpenMailBot"** icon
   - Icon should appear in left panel below Mail/Address Book

#### Method B: Production Install (For End Users)

1. **Build Extension Package**
   ```bash
   cd addon/thunderbird-addon
   zip -r openmailbot.xpi *
   ```

2. **Install from File**
   - In Thunderbird, click **"Menu"** ☰ → **"Add-ons and Themes"**
   - Click **"gear icon"** → **"Install Add-on from File"**
   - Select `openmailbot.xpi`
   - Click **"Add"** and grant permissions

### Step 5.3: Configure Extension Settings

1. **Open Settings**
   - Right-click **"OpenMailBot"** icon in Thunderbird sidebar
   - Click **"Options"** or **"Settings"**

2. **Select Mode**
   - **Manotr Mode** (Cloud): Uses pre-configured OpenMailBot cloud service
   - **Local Mode**: Points to your local agent running on `http://localhost:5051`
   - **External Mode**: Points to custom agent URL

3. **Configure LLM Provider**
   - Select from: OpenAI, Anthropic, Groq, Ollama
   - Enter API keys or base URL
   - Click **"Validate"** to test connection

4. **Save Settings**
   - Click **"Save & Verify"**
   - Wait for success message

### Step 5.4: Start Using OpenMailBot in Thunderbird

1. **Select an Email**
   - In Thunderbird, click any email thread
   - The email preview appears in bottom panel

2. **Open OpenMailBot Sidebar**
   - Click **"OpenMailBot"** icon in left sidebar
   - Settings panel appears

3. **Use Features**
   - **Chat with Email**: Ask questions about email in textarea
   - **Summarize**: Click "Summarize" button
   - **Draft Reply**: Click "Draft Reply" button
   - **Analyze**: Click "Analyze" for sentiment and keywords

### Step 5.5: Verify Installation

```
✅ OpenMailBot icon visible in Thunderbird left sidebar
✅ Can open Settings without errors
✅ Can see mode selection (Manotr/Local/External)
✅ Can select LLM provider
✅ Success message appears when clicking "Validate"
```

---

## 🏠 6. Local Development & Running Locally

### Step 6.1: Directory Structure

```
openmailbot/
├── addon/                    # Gmail Add-on & Thunderbird Extension
│   ├── Code.gs              # Gmail Apps Script
│   └── thunderbird-addon/   # Thunderbird WebExtension
├── agent/                    # Python FastAPI Agent
│   ├── main.py              # Main server
│   ├── requirements.txt      # Python dependencies
│   └── services/            # AI services (RAG, LLM, etc.)
├── backend/                  # Node.js Express Backend
│   ├── main.js              # Server entry point
│   ├── package.json         # NPM dependencies
│   └── routes/              # API routes
├── frontend/                 # Next.js Frontend Dashboard
│   ├── package.json
│   └── src/                 # React components
├── data_pipeline/           # Email ingestion
├── vector/                  # Vector database
├── graph/                   # Graph database (Neo4j)
└── db/                      # Database schemas
```





## 🔑 7. API Key Configuration

### Step 7.1: Get API from openmailbot.com

1. **Visit Website**
   - Go to: https://openmailbot.com/
   - Click **"Get Started"** or **"Dashboard"**

2. **Sign Up or Login**
   - If first time: Click **"Sign Up"** → Enter email and create password
   - If existing: Click **"Sign In"** → Enter credentials

3. **Go to API Settings**
   - In dashboard: Click **"Settings"** (left sidebar)
   - Click **"API Keys"** or **"Integrations"**
   - Click **"Create API Key"**

4. **Copy API Key**
   - New key appears on screen
   - Click **"Copy"** to clipboard
   - **⚠️ Save it somewhere safe** (you can't view it again)

5. **Create Separate Keys for Each Service**
   - Gmail Add-on: Create key named `gmail-addon`
   - Thunderbird: Create key named `thunderbird-addon`
   - Your App: Create key named `my-app-key`



## 🦙 8. Ollama Setup & Usage

### What is Ollama?

**Ollama** is a tool to run large language models (like Llama, Mixtral) **locally on your computer** for **free**, with **no internet required** after download.

**Advantages:**
- ✅ Free (no API costs)
- ✅ Runs offline
- ✅ Fast responses
- ✅ Privacy (your data never leaves your computer)
- ✅ No API keys needed

**Disadvantages:**
- ⚠️ Requires GPU (NVIDIA recommended) or CPU with 8GB+ RAM
- ⚠️ Slower than cloud LLMs
- ⚠️ Models take time to download (1-20GB)

### Step 8.1: Install Ollama

#### Windows

1. Download from: https://ollama.ai/
2. Click **"Download for Windows"**
3. Run installer (`.exe` file)
4. Follow installation prompts
5. Restart computer

#### macOS

```bash
# Download and install
brew install ollama

# Or download DMG from https://ollama.ai/
```

#### Linux

```bash
# Install
curl https://ollama.ai/install.sh | sh

# Or install via package manager:
# Ubuntu: sudo apt install ollama
# Fedora: sudo dnf install ollama
```

### Step 8.2: Start Ollama Service

```bash
# Start Ollama
ollama serve

# Should show: "Listening on http://127.0.0.1:11434"
# Leave this terminal running
```

### Step 8.3: Download Models

**Open a new terminal while Ollama is running:**

#### For Chat/LLM (Pick ONE)

```bash
# Option 1: Lightweight (fast, low RAM)
ollama pull llama2          # 3.8GB

# Option 2: Recommended (balanced)
ollama pull llama2:13b      # 7.4GB

# Option 3: Advanced (slow but smart)
ollama pull mistral         # 4.1GB

# Option 4: Very powerful (requires 24GB+ RAM)
ollama pull llama2:70b      # 39GB
```

#### For Embeddings (Semantic Search)

```bash
# Best option (fast & accurate)
ollama pull nomic-embed-text    # 274MB

# Alternative
ollama pull sentence-transformers/all-minilm-l6-v2  # 66MB
```

### Step 8.4: Verify Models Downloaded

```bash
# List all downloaded models
ollama list

# Expected output:
# NAME                    ID          SIZE    MODIFIED
# llama2                  8dab227bde06  3.8 GB  2 minutes ago
# nomic-embed-text        0570d732f81a  274 MB  1 minute ago
```

### Step 8.5: Configure OpenMailBot for Ollama

#### For Local Development (Thunderbird)

1. **Open Thunderbird Settings**
   - Right-click **OpenMailBot** → **"Options"**

2. **Select Mode**
   - Choose **"Local"**
   - Agent URL: `http://localhost:5051`
   - Click **"Connect"**

3. **Select Ollama as LLM**
   - Provider: **"Ollama"**
   - Model: **"llama2"** (or your chosen model)
   - Local URL: **"http://localhost:11434"**
   - Click **"Fetch Models"** to verify
   - Click **"Test"** to validate

4. **Select Ollama for Embedding**
   - Embedding Provider: **"Ollama"**
   - Model: **"nomic-embed-text"**
   - Click **"Fetch Models"**
   - Click **"Test"**

5. **Save Settings**
   - Click **"Save & Verify"**
   - Success message should appear

#### For Gmail Add-on (Cloud Mode)

```bash
# If using openmailbot.com cloud:
# You can't directly use local Ollama through cloud
# Use Local/External mode instead

# For local agent setup:
1. Change mode to "Local" or "External"
2. Point to http://localhost:5051
3. Configure LLM provider as Ollama (see above)
```

### Step 8.6: Test Ollama Setup

```bash
# Test if Ollama is responding
curl http://localhost:11434/api/tags

# Expected: List of downloaded models in JSON format

# Test with a simple prompt
curl -X POST http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama2",
    "prompt": "Hello, how are you?",
    "stream": false
  }'
```

### Step 8.7: Performance Tips

```
Model Size vs Speed & Quality:

Small Models (2-7GB):
  - llama2, mistral, neural-chat
  - Speed: ⚡ Fast (1-2 sec)
  - Quality: ⭐⭐⭐ Good
  - RAM: 4GB

Medium Models (10-13GB):
  - llama2:13b, neural-chat:7b
  - Speed: ⚡⚡ Medium (3-5 sec)
  - Quality: ⭐⭐⭐⭐ Excellent
  - RAM: 8GB+

Large Models (30GB+):
  - llama2:70b, mixtral:large
  - Speed: ⚡⚡⚡⚡ Slow (10+ sec)
  - Quality: ⭐⭐⭐⭐⭐ Amazing
  - RAM: 16GB+ GPU recommended

Recommendation for Testing:
→ Start with "llama2" or "mistral" (balanced)
→ Upgrade to "llama2:13b" if you have 8GB+ RAM
→ Use GPU if available (NVIDIA: CUDA, AMD: HIP)
```

---

## 🐛 9. Troubleshooting

### Issue: Agent Won't Start

```
Error: "Address already in use" or "Port 5051 in use"

Solution:
# Find process using port 5051
# Windows (PowerShell):
netstat -ano | findstr :5051
taskkill /PID <PID> /F

# macOS/Linux:
lsof -i :5051
kill -9 <PID>
```


### Issue: Gmail Add-on Not Appearing

```
Error: Add-on icon doesn't show in Gmail sidebar

Solution:
1. Hard refresh Gmail: Ctrl+Shift+R (Windows) or Cmd+Shift+R (macOS)
2. Clear browser cache:
   - Chrome: Settings → Privacy → Clear Browsing Data
3. Re-deploy script in Google Apps Script:
   - Deploy → New Deployment → Add-on
4. Check permissions: Gmail settings → Manage your Google Account → Security
```

### Issue: Thunderbird Extension Won't Load

```
Error: "Error loading extension" when adding to Thunderbird

Solution:
1. Check manifest.json syntax:
   - Use JSON validator: https://jsonlint.com/
   
2. Check browser compatibility:
   - Thunderbird 102+ required for WebExtensions
   - Update Thunderbird: Help → About → Check for Updates

3. Reinstall extension:
   - Remove current extension
   - Delete manifest.json.zip from profile folder
   - Reload from file

4. Check file permissions:
   - manifest.json should be readable
   - No special characters in path
```

### Issue: API Key Invalid or Expired

```
Error: "Invalid API key" or "Unauthorized"

Solution:
1. Verify key is copied completely (no spaces)
2. Check key hasn't been revoked in dashboard
3. Create new key and update settings
4. Ensure key has correct permissions for service
5. Check key expiration date (if applicable)
```

### Issue: Ollama Not Connecting

```
Error: "Failed to connect to Ollama" or "Connection refused"

Solution:
1. Check Ollama is running:
   # Terminal should show: Listening on http://127.0.0.1:11434
   
2. If not running, start it:
   ollama serve
   
3. Check correct URL:
   # Local: http://localhost:11434 ✓
   # NOT: http://127.0.0.1:11434 (different on network)
   
4. Test connection:
   curl http://localhost:11434/api/tags
   
5. Check firewall:
   # Windows: Add Ollama to firewall exceptions
   # macOS: System Preferences → Security → Firewall
   
6. Verify model is downloaded:
   ollama list
```
### Issue: GPU Not Being Used (Ollama Running Slowly)

```
Error: Ollama using CPU only, very slow responses

Solution:

For NVIDIA GPUs:
1. Install NVIDIA CUDA Toolkit
   # https://developer.nvidia.com/cuda-downloads
   
2. Install cuDNN
   # https://developer.nvidia.com/cudnn
   
3. Restart Ollama:
   ollama serve
   
4. Verify in Ollama logs:
   # Should show: "GPU acceleration enabled"

For AMD GPUs:
1. Install ROCm
   # https://rocmdocs.amd.com/en/docs-5.7.1/deploy/linux/index.html
   
2. Set environment variable:
   export HSA_OVERRIDE_GFX_VERSION=your_gfx_version
   
3. Restart Ollama

For Mac:
1. Ollama automatically uses Metal (GPU)
2. No additional setup needed
3. Check Activity Monitor for GPU usage
```

## 📞 Support & Resources

### Documentation
- Main Docs: https://openmailbot.com/docs
- API Reference: https://openmailbot.com/api
- GitHub Issues: https://github.com/ankitgoel2004/openmailbot/issues

### Contact
- Email: support@openmailbot.com
- GitHub Discussions: https://github.com/ankitgoel2004/openmailbot/discussions

---

## 📝 Next Steps After Installation

1. ✅ **Verify all services running** (Backend, Agent, Frontend)
2. ✅ **Create API keys** (get from openmailbot.com)
3. ✅ **Install Gmail Add-on or Thunderbird Extension**
4. ✅ **Configure LLM provider** (OpenAI, Anthropic, Groq, or Ollama)
5. ✅ **Test with a sample email**
6. ✅ **Explore features** (Summarize, Draft, Chat, Analyze)

---

**Happy email automating! 🚀**

*Last Updated: May 2026*  
*For latest updates, visit: https://github.com/ankitgoel2004/openmailbot*
