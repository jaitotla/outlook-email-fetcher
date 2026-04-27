# Quick Testing Guide - Provider Model Fetching

## Prerequisites
1. Start the agent: `cd agent && python main.py`
2. Open Thunderbird addon settings page

## Test Scenarios

### 1. OpenAI LLM Provider ✅

**Steps:**
1. Navigate to settings page
2. Select **LLM Provider: OpenAI**
3. Enter your OpenAI API key
4. Click **"🔄 Fetch Available Models"**

**Expected Result:**
- Status: "✅ X model(s) loaded"
- Dropdown shows: gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo, o1, etc.
- **Should NOT show:** text-embedding-*, whisper-*, tts-*, dall-e-*

**To Verify:**
- Invalid key shows: "❌ Invalid OpenAI API key."
- Network issues show: "❌ Timed out" or connection error

---

### 2. Anthropic LLM Provider ✅

**Steps:**
1. Select **LLM Provider: Anthropic**
2. Enter your Anthropic API key
3. Click **"🔄 Fetch Available Models"**

**Expected Result:**
- Status: "✅ X model(s) loaded"
- Dropdown shows: claude-3-5-sonnet-20241022, claude-3-5-haiku-20241022, etc.

---

### 3. Groq LLM Provider ✅

**Steps:**
1. Select **LLM Provider: Groq**
2. Enter your Groq API key
3. Click **"🔄 Fetch Available Models"**

**Expected Result:**
- Status: "✅ X model(s) loaded"
- Dropdown shows: llama-3.3-70b-versatile, mixtral-8x7b-32768, gemma2-9b-it, etc.

---

### 4. Ollama - Case 1: Local 🏠

**Prerequisites:**
- Ollama installed locally
- Running: `ollama serve`
- At least one model pulled: `ollama pull llama3.2`

**Steps:**
1. Select **LLM Provider: Ollama**
2. Leave URL as default: `http://localhost:11434` (or enter manually)
3. Leave API key blank
4. Click **"🔄 Fetch Ollama Models"**

**Expected Result:**
- Status: "✅ X model(s) loaded"
- Message: "**Local Ollama** is reachable. Found X model(s)."
- Dropdown shows: llama3.2, mistral, etc. (your locally installed models)

**Error Cases:**
- Ollama not running: "❌ Cannot connect to Ollama at http://localhost:11434. **Is Ollama running?**"
- No models: "⚠️ **Local Ollama** is reachable but no models are installed. Run 'ollama pull <model>' first."

---

### 5. Ollama - Case 2: Remote Public URL 🌐

**Prerequisites:**
- Ollama running on remote server
- Exposed via PageKite, ngrok, or reverse proxy
- Example: `https://ollama-abc123.pagekite.me`

**Steps:**
1. Select **LLM Provider: Ollama**
2. Enter your public URL: `https://ollama-abc123.pagekite.me`
3. Leave API key blank (if no auth required)
4. Click **"🔄 Fetch Ollama Models"**

**Expected Result:**
- Status: "✅ X model(s) loaded"
- Message: "**Remote Ollama** is reachable. Found X model(s)."
- Dropdown shows available models from your remote server

**Error Cases:**
- Connection failure: "❌ Cannot connect to Ollama at {url}. **Check the URL and ensure it's publicly accessible.**"
- Wrong URL: Connection timeout or 404 error

---

### 6. Ollama - Case 3: Secured Remote 🔒

**Prerequisites:**
- Ollama running on remote server with authentication
- API key/Bearer token configured

**Steps:**
1. Select **LLM Provider: Ollama**
2. Enter your public URL: `https://secure-ollama.example.com`
3. Enter API key in **"Ollama API Key (optional)"** field
4. Click **"🔄 Fetch Ollama Models"**

**Expected Result:**
- Status: "✅ X model(s) loaded"
- Message: "**Remote Ollama (secured)** is reachable. Found X model(s)."
- Dropdown shows available models

**Error Cases:**
- Wrong/missing API key: "❌ Ollama requires authentication — check your API key."

---

### 7. OpenAI Embedding Provider ✅

**Steps:**
1. Select **Embedding Provider: OpenAI**
2. Enter your OpenAI API key
3. Click **"🔄 Fetch Available Models"**

**Expected Result:**
- Status: "✅ X model(s) loaded"
- Dropdown shows **ONLY**: text-embedding-3-small, text-embedding-3-large, text-embedding-ada-002
- **Should NOT show:** gpt-*, o1-*, etc.

---

### 8. Ollama Embedding Provider ✅

**Prerequisites:**
- Ollama with embedding models: `ollama pull nomic-embed-text`

**Steps:**
1. Select **Embedding Provider: Ollama**
2. Enter Ollama URL (local or remote)
3. Click **"🔄 Fetch Ollama Models"**

**Expected Result:**
- Status: "✅ X model(s) loaded"
- Dropdown **prioritizes** embedding models: nomic-embed-text, mxbai-embed-large, bge-large, etc.
- If only LLM models available, shows all models

---

### 9. Save & Verify All Providers 💾

**Steps:**
1. Configure LLM provider (e.g., OpenAI)
2. Configure Embedding provider (e.g., OpenAI or Ollama)
3. Configure Vector DB (e.g., Manotr or Pinecone)
4. Fill in User Profile (Name, Position)
5. Click **"💾 Save & Verify"**

**Expected Result:**
- Button changes to "🔍 Verifying providers…"
- All providers validated simultaneously:
  - LLM test status: "✅ OpenAI API key is valid. Found X models."
  - Embedding test status: "✅ OpenAI API key is valid. Found X models."
  - Vector DB test status: "✅ Manotr (built-in) — no validation needed"
- Final message: "✅ Settings saved and all providers verified!"

**Error Case:**
- One provider fails: "⚠️ Settings saved, but some providers failed validation — check the highlighted sections."

---

### 10. Test Connection Buttons 🔍

**Steps:**
1. After configuring a provider (without clicking Fetch Models)
2. Click **"🔍 Test LLM Connection"** or **"🔍 Test Embedding Connection"**

**Expected Result:**
- Same validation as Fetch Models
- **ALSO auto-populates model dropdown** if validation succeeds
- Shows clear status: success or error

---

## Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| "❌ Cannot connect to Ollama" | Agent not running | Start agent: `python main.py` |
| "❌ Invalid API key" | Wrong key or expired | Check API key from provider dashboard |
| "⚠️ No models found" | Ollama: No models pulled | Run `ollama pull llama3.2` |
| Models not showing | Fetch button not clicked | Click "🔄 Fetch Available Models" |
| Dropdown shows wrong models | Filter not applied | Check provider type (LLM vs Embedding) |
| Settings not saving | Agent endpoint wrong | Verify agent URL in Page 1 |

---

## Validation API Endpoints (for reference)

```bash
# Test OpenAI
curl -H "Authorization: Bearer YOUR_API_KEY" \
  https://api.openai.com/v1/models

# Test Anthropic
curl -H "x-api-key: YOUR_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  https://api.anthropic.com/v1/models

# Test Groq
curl -H "Authorization: Bearer YOUR_API_KEY" \
  https://api.groq.com/openai/v1/models

# Test Ollama (local)
curl http://localhost:11434/api/tags

# Test Ollama (remote with auth)
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://your-ollama-url.com/api/tags
```

---

## Permutation Test Matrix

| LLM Provider | Embedding Provider | Vector DB | Expected Result |
|--------------|-------------------|-----------|-----------------|
| OpenAI | OpenAI | Manotr | ✅ All validate |
| Anthropic | OpenAI | Pinecone | ✅ All validate |
| Groq | Ollama (local) | Manotr | ✅ All validate |
| Ollama (local) | Ollama (local) | Qdrant | ✅ All validate |
| Ollama (remote) | OpenAI | Manotr | ✅ All validate |
| OpenAI | Ollama (secured) | Pinecone | ✅ All validate |

**Test at least 3-4 combinations to ensure settings work correctly.**

---

## Success Criteria ✅

- [ ] All cloud providers (OpenAI, Anthropic, Groq) fetch models correctly
- [ ] Ollama works in all 3 cases (local, remote, secured)
- [ ] Embedding models filtered correctly for each provider
- [ ] Invalid API keys show clear error messages
- [ ] Connection failures show helpful guidance
- [ ] Save & Verify validates all providers simultaneously
- [ ] Settings persist after browser restart
- [ ] Background process picks up saved settings
