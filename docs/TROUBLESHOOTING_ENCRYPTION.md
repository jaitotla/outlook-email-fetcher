# OpenMailBot Troubleshooting Guide

## Encrypted Settings Sync Failing (HTTP 400)

### Error Message
```
❌ Decryption failed for user@example.com: An error occurred trying to decrypt the message
Status: 400 Bad Request
```

### Symptoms
- POST `/api/settings/encrypted` returns HTTP 400
- Settings save works with plaintext endpoint `/api/settings` (deprecated)
- Error appears when using Gmail Add-on or other clients that support encrypted sync

### Root Causes & Solutions

#### 1. **Multi-Instance Deployment - Key Mismatch** (Most Common)

**What's happening:**
- You're running multiple backend instances (load balancer setup)
- Each instance generated its own encryption keypair
- Client encrypted data with Instance A's public key
- Request routed to Instance B (different keypair)
- Instance B can't decrypt

**Solution:**
```bash
# 1. Generate a shared key (do this once)
python3 -c "
from nacl.public import PrivateKey
import base64
pk = PrivateKey.generate()
print(base64.b64encode(bytes(pk)).decode())
"

# 2. Set on ALL backend instances
export ENCRYPTION_PRIVATE_KEY="<the-key-from-step-1>"

# 3. Restart all instances
# They will now share the same keypair
```

For Docker/Kubernetes, see [ENCRYPTION_DEPLOYMENT.md](./ENCRYPTION_DEPLOYMENT.md)

#### 2. **Client Cached Stale Public Key**

**What's happening:**
- Backend restarted or keypair changed
- Client still has old cached public key
- Encryption fails because keys don't match

**Solution (Client Side):**

**Thunderbird:**
1. Open Add-on Options
2. Scroll to "Advanced" section
3. Click "Clear Encryption Cache"
4. Close and reopen popup
5. Retry settings sync

**Gmail Add-on:**
1. Open script editor: Tools → Script editor
2. Delete properties: `PropertiesService.getUserProperties().deleteProperty("encryption_public_key")`
3. Refresh the add-on
4. Retry settings sync

**Firefox/Chrome (Web Interface):**
1. Open browser console: F12
2. Go to Storage tab
3. Click on Local Storage
4. Find and delete key: `encryption_public_key`
5. Refresh page and retry

#### 3. **Network Corruption or Data Transfer Issue**

**What's happening:**
- Payload was corrupted during transmission
- Invalid base64 encoding
- Incomplete upload

**Solution:**
1. Check network connectivity
2. Try again from a stable connection
3. Use HTTPS instead of HTTP (prevents corruption)

#### 4. **Add-on Using Wrong Backend URL**

**What's happening:**
- Add-on configured to talk to backend A
- Backend A's keypair isn't synced with backend B
- Getting key from one instance, sending to another

**Solution:**
```bash
# Verify add-on configuration
# Thunderbird: Add-on Options → Backend URL
# Gmail: Gmail Sheet configuration → Agent URL
# Should match: https://your-backend-domain.com

# Verify backend is accessible
curl https://your-backend-domain.com/api/public-key
# Should return public key JSON
```

### Diagnostic Checklist

- [ ] **Is backend responding?** 
  ```bash
  curl https://your-backend-domain.com/health
  # Should return 200 OK
  ```

- [ ] **Is public key endpoint working?**
  ```bash
  curl https://your-backend-domain.com/api/public-key
  # Should return JSON with "public_key" field
  ```

- [ ] **For multi-instance setup: Are all instances using same key?**
  ```bash
  # Query each instance
  curl https://instance1.com/api/public-key | jq .public_key
  curl https://instance2.com/api/public-key | jq .public_key
  # Should output identical values
  ```

- [ ] **Is client cache causing issues?**
  - Clear `encryption_public_key` from browser storage
  - Retry encryption

### Advanced Debugging

**1. Check server logs for detailed error:**
```bash
# Look for lines with pattern: "🔍 DIAGNOSTIC HINTS"
# Example from logs:
# ⚠️  SealedBox.decrypt() failed: ...
# This typically indicates a KEY MISMATCH
# Hint: Ensure add-on public key matches backend private key
```

**2. Enable debug logging:**
```python
# Add to agent config or main.py
import logging
logging.basicConfig(level=logging.DEBUG)
# Re-run backend and watch for encryption service logs
```

**3. Verify key match:**
```python
from agent.services.encryption_service import get_encryption_service
service = get_encryption_service()
print("Public key:", service.get_public_key_b64())
# Compare with what add-on sees in /api/public-key
```

## When All Else Fails

### Fallback to Plaintext Endpoint
The plaintext endpoint still works:

```javascript
// JavaScript fallback
const response = await fetch(`${backendUrl}/api/settings`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    user_id: userEmail,
    settings: settingsObject
  })
});
```

**Note:** Plaintext endpoint is deprecated but functional. It encrypts data at-rest in database.

### Report Issue
If you can't resolve it, include:
1. Server logs with "🔍 DIAGNOSTIC HINTS" section
2. Public key from `/api/public-key` (safe to share)
3. Add-on configuration (backend URL, agent URL)
4. Whether single-instance or multi-instance setup
5. Any custom deployment (Docker, K8s, etc.)

---

## Other Common Issues

### Settings Not Saving at All
**Check:**
1. Backend is running and accessible
2. User email is correct in add-on settings
3. API key authentication is working: `curl -H "Authorization: Bearer <token>" https://backend/health`

### Settings Saving but Not Applying
**Check:**
1. Agent service is reading from backend (not using cached local settings)
2. Check logs: "Loaded settings for user:" should appear when pipeline runs
3. Restart agent service to clear cached settings

### Add-on Won't Connect to Backend
**Check:**
1. Backend URL is correct and publicly accessible
2. No firewall blocking the connection
3. HTTPS certificate is valid (not self-signed without proper setup)
4. CORS is configured properly (try `curl -H "Origin: <origin>" https://backend/api/public-key`)

---

**Still need help?** 
- See [ENCRYPTION_DEPLOYMENT.md](./ENCRYPTION_DEPLOYMENT.md) for deployment-specific guidance
- Check [docs/SLACK_APP_SETUP.md](./SLACK_APP_SETUP.md) for alternative integration
- Review [README.md](../README.md) for general setup
