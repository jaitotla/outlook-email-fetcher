# Testing the OpenMailBot Settings Implementation

This guide helps you verify that all settings features work correctly.

## Quick Verification Checklist

Use this checklist to verify the implementation:

- [ ] **Mode Selection**
  - [ ] Manotr mode shows read-only agent URL
  - [ ] Local/External modes require agent URL input
  - [ ] Connect button appears for non-Manotr modes

- [ ] **Agent Connection**
  - [ ] Connect button validates agent URL
  - [ ] Success message shows when connected
  - [ ] Next button only enables after successful connection

- [ ] **Provider Configuration**
  - [ ] OpenAI provider shows OpenAI models
  - [ ] Anthropic provider shows Claude models
  - [ ] Groq provider shows Groq models
  - [ ] Ollama provider shows Ollama models

- [ ] **Ollama Support**
  - [ ] Local URL field accepts localhost:11434
  - [ ] Remote URL field accepts custom URLs
  - [ ] Optional API key field appears
  - [ ] Fetch Models button retrieves installed models
  - [ ] Works for both LLM and embedding

- [ ] **API Validation**
  - [ ] Test buttons validate providers
  - [ ] Models auto-populate after validation
  - [ ] Save validates all configured providers
  - [ ] Error messages show for invalid credentials

- [ ] **Vector Database**
  - [ ] Pinecone validation works
  - [ ] Qdrant validation works
  - [ ] Manotr mode requires no configuration

## 🧪 Automated Testing

### Method 1: Python Test Script

A comprehensive test script is provided to validate all endpoints:

```bash
# 1. Make sure agent is running
cd agent
python main.py

# 2. In another terminal, run the test script
cd ..
python test_settings_validation.py
```

**Before running:**
- Edit `test_settings_validation.py` and add your API keys
- Start Ollama if you want to test it: `ollama serve`
- Install required models: `ollama pull llama3.2 nomic-embed-text`

The script will test:
- ✅ Agent handshake endpoint
- ✅ Health check endpoint
- ✅ All provider validations
- ✅ Model fetching for each provider

### Method 2: Manual API Testing

#### Test Handshake
```bash
curl http://localhost:5051/handshake
```
**Expected:** `{"handshake": true, "status": "ok", ...}`

#### Test OpenAI Validation
```bash
curl -X POST http://localhost:5051/api/validate-provider \
  -H "Content-Type: application/json" \
  -d '{
    "provider_type": "llm",
    "provider": "openai",
    "api_key": "sk-YOUR_KEY_HERE"
  }'
```
**Expected:** `{"valid": true, "models": ["gpt-4o", ...], ...}`

#### Test Ollama Validation
```bash
# Make sure Ollama is running first
ollama serve

# Test validation
curl -X POST http://localhost:5051/api/validate-provider \
  -H "Content-Type: application/json" \
  -d '{
    "provider_type": "llm",
    "provider": "ollama",
    "base_url": "http://localhost:11434"
  }'
```
**Expected:** `{"valid": true, "models": ["llama3.2", ...], ...}`

#### Test Anthropic Validation
```bash
curl -X POST http://localhost:5051/api/validate-provider \
  -H "Content-Type: application/json" \
  -d '{
    "provider_type": "llm",
    "provider": "anthropic",
    "api_key": "sk-ant-YOUR_KEY_HERE"
  }'
```
**Expected:** `{"valid": true, "models": ["claude-3-5-sonnet-20241022", ...], ...}`

## 🖥️ Manual UI Testing

### Test 1: Manotr Mode (Zero Config)

**Steps:**
1. Open Thunderbird
2. Go to Tools → Add-ons → OpenMailBot → Settings
3. Select "Manotr" from Mode dropdown
4. **Verify:** Agent URL shows "http://omb.manotr.com" (grayed out)
5. **Verify:** "Next" button is enabled immediately
6. Click "Next"
7. **Verify:** All providers default to "Manotr"
8. Click "Save & Verify"
9. **Verify:** Success message appears

### Test 2: Local Mode with Ollama

**Prerequisites:**
```bash
# Start Ollama
ollama serve

# Pull a model
ollama pull llama3.2
ollama pull nomic-embed-text
```

**Steps:**
1. Open settings
2. Select "Local" mode
3. Enter agent URL: `http://localhost:5051`
4. Click "Connect"
5. **Verify:** Success message appears
6. Click "Next"
7. Change LLM Provider to "Ollama"
8. **Verify:** Ollama URL field appears (default: localhost:11434)
9. Click "Fetch Ollama Models"
10. **Verify:** Models populate dropdown (llama3.2, mistral, etc.)
11. Select a model
12. Click "Test LLM Connection"
13. **Verify:** Success message appears
14. Change Embedding Provider to "Ollama"
15. Click "Fetch Ollama Models" (embedding section)
16. **Verify:** Embedding models populate (nomic-embed-text, etc.)
17. Click "Test Embedding Connection"
18. **Verify:** Success message appears
19. Click "Save & Verify"
20. **Verify:** All validations pass

### Test 3: External API Mode

**Prerequisites:**
- OpenAI API key
- (Optional) Anthropic API key

**Steps:**
1. Open settings
2. Select "External API" mode
3. Enter agent URL
4. Click "Connect" and verify
5. Click "Next"
6. Select "OpenAI" for LLM Provider
7. Enter OpenAI API key
8. Click "Test LLM Connection"
9. **Verify:** Models auto-populate (gpt-4o, gpt-4o-mini, etc.)
10. **Verify:** Success message appears
11. Select a model from dropdown
12. Repeat for Embedding provider
13. Click "Save & Verify"
14. **Verify:** All validations pass

### Test 4: Remote Ollama with Authentication

**Prerequisites:**
- Remote Ollama server with authentication
- Bearer token for the server

**Steps:**
1. Open settings → "External API" mode
2. Configure agent URL and connect
3. Select "Ollama" for LLM Provider
4. Enter remote Ollama URL: `https://ollama.myserver.com`
5. Enter Bearer token in "Ollama API Key" field
6. Click "Fetch Ollama Models"
7. **Verify:** Models fetch successfully
8. Click "Test LLM Connection"
9. **Verify:** Validation succeeds
10. Repeat for embedding provider
11. Save and verify

### Test 5: Mixed Providers

**Steps:**
1. Configure different providers for each service:
   - LLM: OpenAI (gpt-4o)
   - Embedding: Ollama (nomic-embed-text)
   - Vector: Manotr (built-in)
2. Validate each provider
3. **Verify:** All work together
4. Save and verify

### Test 6: Validation Failures

**Test invalid API keys:**
1. Enter invalid OpenAI key: `sk-invalid123`
2. Click "Test LLM Connection"
3. **Verify:** Error message appears: "Invalid OpenAI API key"
4. **Verify:** Status shows red ❌

**Test unreachable Ollama:**
1. Enter wrong Ollama URL: `http://localhost:99999`
2. Click "Test LLM Connection"
3. **Verify:** Error message: "Cannot connect to Ollama"

**Test missing configuration:**
1. Select "OpenAI" provider
2. Leave API key blank
3. Click "Test LLM Connection"
4. **Verify:** Error message appears

## 📊 Expected Results

### Successful Validation
- ✅ Green checkmark appears
- ✅ Success message displayed
- ✅ Models populate (if applicable)
- ✅ Save button works

### Failed Validation
- ❌ Red X appears
- ❌ Error message explains the issue
- ❌ Settings still save (best effort)
- ⚠️ Warning shown on save

## 🐛 Troubleshooting

### Agent Won't Start
```bash
# Check if port is in use
netstat -an | grep 5051

# Check logs
cd agent
python main.py
# Look for errors in output
```

### Ollama Not Detected
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama
ollama serve

# Verify models installed
ollama list
```

### Models Not Fetching
```bash
# Test API directly
curl http://localhost:5051/api/validate-provider \
  -H "Content-Type: application/json" \
  -d '{"provider_type":"llm","provider":"ollama","base_url":"http://localhost:11434"}'

# Check response for errors
```

### Connect Button Fails
```bash
# Test handshake endpoint
curl http://localhost:5051/handshake

# If fails, check agent logs
# If succeeds, check browser console for errors
```

## ✅ Verification Complete

If all tests pass:
- ✅ Mode-based agent URL configuration works
- ✅ Handshake validation works
- ✅ Provider-specific models display correctly
- ✅ API key validation works for all providers
- ✅ Ollama self-hosted URL support works
- ✅ Models auto-populate after validation
- ✅ All provider permutations supported

**System is PRODUCTION READY!** 🎉

## 📚 Additional Resources

- **Full Verification Report:** `IMPLEMENTATION_VERIFICATION_REPORT.md`
- **Changes Summary:** `CHANGES_SUMMARY.md`
- **Test Script:** `test_settings_validation.py`
- **API Documentation:** `docs/API.md`

## 🤝 Need Help?

If you encounter issues:
1. Check the logs: `agent/main.py` output
2. Check browser console: F12 → Console tab
3. Verify prerequisites: Python packages, Ollama, API keys
4. Review configuration files: `agent/config.json`
5. Check network connectivity: firewall, ports, URLs
