# Security Configuration Guide - OpenMailBot

## Overview
This document outlines security measures to prevent API keys, credentials, and sensitive data from being accidentally committed to the repository.

## `.gitignore` Configuration

### Root Level
**File**: `/.gitignore`

Protects the entire project from committing:
- Environment variables (`.env*` files)
- Config files with credentials (`config.json`)
- Database files (`.db`, `.sqlite3`)
- IDE and editor configurations
- OS-specific files
- Build artifacts and node_modules

### Backend/Agent
**File**: `/openmailbot/.gitignore`

Additional protections for backend services:
- `agent/config.json` - Local LLM provider configs
- `data/*/sql_data/` - Encrypted user settings databases
- `store_attachments/` - Email attachments
- `log_emails/` - Raw email logs  
- `vector_db/` - Vector databases
- `chroma.sqlite3` - ChromaDB embeddings

### Frontend
**File**: `/openmailbot/openmailbot/frontend/.gitignore`

Frontend-specific protections:
- `.env*.local` - Local environment overrides
- `node_modules/` - Dependencies
- `.next/` - Build artifacts
- `.env` - Never commit actual env vars

## Protected Sensitive Data

### API Keys & Credentials
```
✅ PROTECTED by .gitignore:
- OpenAI API keys
- Anthropic API keys
- Groq API keys
- Ollama credentials
- Embedding provider API keys
- Gmail OAuth tokens
- IMAP passwords
- Database connection strings
```

### Configuration Files
```
✅ PROTECTED:
- config.json - Provider settings
- .env files - All environment variables
- credentials.json - Service credentials
- secrets.json - Application secrets
```

### User Data Directories
```
✅ PROTECTED:
- data/{user_id}/sql_data/ - Encrypted settings
- data/{user_id}/store_attachments/ - Email files
- data/{user_id}/log_emails/ - Raw email logs
- data/{user_id}/vector_db/ - Embeddings
```

## Best Practices

### 1. Use `.env.example` for Documentation
Create template files showing required variables without actual values:

```bash
# .env.example
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=claude-3-...
OLLAMA_URL=http://localhost:11434
MONGODB_URI=mongodb://...
```

### 2. Local Configuration
For development, create `.env.local`:
```bash
# .env.local (NOT committed to git)
OPENAI_API_KEY=sk-your-actual-key-here
```

### 3. Environment Variables
Always use environment variables for secrets:
```python
# ✅ CORRECT
api_key = os.environ.get("OPENAI_API_KEY")

# ❌ WRONG
api_key = "sk-hardcoded-key-exposed"
```

### 4. Config Files
Keep `config.json` in `.gitignore`, use environment-based config:
```python
# agent/config.py
config = {
    "llm_provider": os.environ.get("LLM_PROVIDER", "openai"),
    "llm_api_key": os.environ.get("LLM_API_KEY"),
    "embedding_provider": os.environ.get("EMBEDDING_PROVIDER", "openai"),
}
```

### 5. Database Encryption
User settings are encrypted with Fernet:
```python
# ✅ All keys/passwords encrypted in SQLite
settings_manager = SettingsManager(user_id="user@example.com")
settings_manager.save_settings({
    "llm_api_key": "sk-xxx",  # Encrypted before storage
    "imap_app_password": "xxxx xxxx xxxx xxxx",  # Encrypted
}, user_id, "general")
```

## Cleanup - If Secrets Were Already Committed

### 1. Remove from Git History
```bash
# Remove specific file from all commits
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch config.json' \
  --prune-empty --tag-name-filter cat -- --all

# Or remove all files matching .gitignore patterns
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch .env config.json' \
  --prune-empty --tag-name-filter cat -- --all
```

### 2. Force Push to Remote
```bash
# ⚠️  This rewrites history - coordinate with team
git push --force --all
git push --force --tags
```

### 3. Rotate Compromised Credentials
If API keys were committed:
- Rotate all exposed API keys immediately
- Revoke OAuth tokens
- Update database passwords
- Review access logs for unauthorized usage

## Pre-Commit Hooks

To prevent accidental commits of sensitive files, create `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Prevent committing .env files and config.json

FILES_PATTERN="(\.env|config\.json|\.key|\.pem|secrets\.json)"
if git diff-index --cached HEAD --name-only | egrep "$FILES_PATTERN"; then
    echo "❌ ERROR: Attempting to commit sensitive files:"
    git diff-index --cached HEAD --name-only | egrep "$FILES_PATTERN"
    echo ""
    echo "Sensitive files should not be committed. Use .env.example instead."
    exit 1
fi
```

Make it executable:
```bash
chmod +x .git/hooks/pre-commit
```

## File Structure - What Gets Committed

```
✅ COMMITTED (safe):
├── .gitignore
├── .env.example
├── package.json
├── requirements.txt
├── src/
├── agent/
└── docs/

❌ NOT COMMITTED (protected):
├── .env
├── .env.local
├── config.json
├── data/
├── logs/
├── node_modules/
└── __pycache__/
```

## Monitoring

### Git Status Check
```bash
# Verify no sensitive files are staged
git status

# Expected: Only source code files should be staged
```

### GitHub Secret Scanning
Enable in repository settings:
- Settings → Security & analysis → Secret scanning
- Automatically detects committed API keys
- GitHub will notify if patterns are detected

## Troubleshooting

### Accidentally Committed a Secret?
1. Immediately rotate the exposed credential
2. Use `git filter-branch` to remove from history
3. Force push to clean the repository
4. Create a new commit with `.gitignore` updates

### Files Still Showing as Modified?
```bash
# Remove from git tracking (keep local file)
git rm --cached filename

# Or update .gitignore and:
git rm -r --cached .
git add .
git commit -m "Remove ignored files from tracking"
```

## Related Files

- [Agent Configuration](../openmailbot/agent/config.py)
- [Settings Manager](../openmailbot/agent/services/settings_manager.py)
- [Environment Variables](./DEVELOPMENT_STATUS.md#environment-setup)

---

**Last Updated**: 2026-05-19  
**Status**: ✅ All .gitignore files updated with comprehensive patterns
