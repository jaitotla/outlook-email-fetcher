# Encryption Key Management & Deployment Guide

## Overview
OpenMailBot uses libsodium (NaCl) Ed25519 keypairs for client-side encryption of settings. This document explains how to properly deploy and manage encryption keys, especially for multi-instance backends.

## Single-Instance Deployment (Local Development / Simple Setup)

### Automatic Keypair Generation
- On first startup, the encryption service automatically generates a new Ed25519 keypair
- Private key is stored in: `agent/data/system/keys.db` (SQLite)
- Public key is exposed via `/api/public-key` endpoint
- Keypair persists across restarts (stored in database)

### Deployment Steps
```bash
# 1. Start backend/agent normally
python agent/main.py

# 2. Keypair will be auto-generated and logged:
# 🔐 NEW ENCRYPTION KEYPAIR GENERATED
# ✅ Encryption keypair auto-saved!
#    📁 Saved to: agent/data/system/keys.db
#    🔐 Private Key: <base64-string>
#    📤 Public Key (share with add-ons / bake into code):
#       <base64-string>

# 3. Add-ons automatically fetch public key via /api/public-key
# 4. No manual configuration needed
```

## Multi-Instance Deployment (Load Balancer / Docker Swarm)

### The Problem
Each backend instance generates its own keypair on startup:
- Instance A: Keypair A
- Instance B: Keypair B
- Instance C: Keypair C

When a client encrypts settings with Instance A's public key but request routes to Instance B:
- Instance B tries to decrypt with its own private key
- Decryption fails: "An error occurred trying to decrypt the message"
- Error is returned with helpful diagnostic hints

### Solution: Shared Encryption Key

#### Step 1: Generate Keypair (Once, Off-Instance)

**Option A: Using Python**
```bash
python3 -c "
from nacl.public import PrivateKey
from nacl.utils import random
import base64
pk = PrivateKey.generate()
print('ENCRYPTION_PRIVATE_KEY=' + base64.b64encode(bytes(pk)).decode())
"
```

**Option B: Using OpenSSL + Python**
```bash
openssl rand 32 | base64
# Then use that to generate NaCl key
```

#### Step 2: Configure All Instances

**Docker Environment Variables**
```dockerfile
ENV ENCRYPTION_PRIVATE_KEY="<base64-encoded-32-byte-key>"
```

**Docker Compose**
```yaml
services:
  backend:
    environment:
      - ENCRYPTION_PRIVATE_KEY=<key>
    
  backend-2:
    environment:
      - ENCRYPTION_PRIVATE_KEY=<key>
      
  backend-3:
    environment:
      - ENCRYPTION_PRIVATE_KEY=<key>
```

**Kubernetes Secrets**
```bash
# Create secret
kubectl create secret generic encryption-key \
  --from-literal=ENCRYPTION_PRIVATE_KEY='<key>'

# Reference in deployment
env:
  - name: ENCRYPTION_PRIVATE_KEY
    valueFrom:
      secretKeyRef:
        name: encryption-key
        key: ENCRYPTION_PRIVATE_KEY
```

**Environment Variables (Bare Metal)**
```bash
export ENCRYPTION_PRIVATE_KEY="<base64-encoded-key>"
python agent/main.py
```

#### Step 3: Verify Configuration
All instances should now:
1. Load the same private key from environment variable
2. Derive the same public key
3. Expose same `/api/public-key` to clients
4. Decrypt payloads from any instance successfully

```bash
# Test endpoint on different instances
curl http://instance-1:5051/api/public-key
curl http://instance-2:5051/api/public-key
# Both should return the same "public_key" value
```

## Key Lifecycle Management

### Rotating Keys (When Needed)
Reasons to rotate:
- Security breach / key compromise
- Intentional security refresh (yearly)
- Migration to new infrastructure

**Rotation Process:**
1. Generate new keypair (see Step 1 above)
2. Update environment variables on all instances
3. Restart all instances (they will load new key from SQLite or environment)
4. Old cached public keys on clients will become invalid
5. Clients will auto-retry with fresh `/api/public-key` fetch
6. New encrypted payloads will use new key

### Key Backup & Recovery
```bash
# Backup key from database
sqlite3 agent/data/system/keys.db "SELECT private_key FROM encryption_keys ORDER BY created_at DESC LIMIT 1;"

# Restore by setting environment variable before startup
export ENCRYPTION_PRIVATE_KEY="<recovered-key>"
```

## Troubleshooting

### Error: "Decryption failed (likely key mismatch)"

**Symptoms:**
- POST `/api/settings/encrypted` returns HTTP 400
- Error: "An error occurred trying to decrypt the message"
- Works fine with plaintext `/api/settings` endpoint

**Causes & Solutions:**

1. **Different backend instances have different keys**
   - ✅ Set `ENCRYPTION_PRIVATE_KEY` environment variable on ALL instances
   - ✅ Verify all instances return same public key from `/api/public-key`

2. **Client cached old public key**
   - ✅ Clear browser cache: `browser.storage.local.remove('encryption_public_key')`
   - ✅ Client will auto-retry with fresh key fetch
   - ✅ Retry encryption

3. **Load balancer routing to different instances**
   - ✅ Use sticky sessions if load balancer supports it
   - ✅ Or implement shared key management (see above)

4. **Backend restarted and regenerated key**
   - ✅ Use environment variable to pin key (persists across restarts)
   - ✅ Or clear client cache and retry

### Diagnostic Information

The service includes instance identification in `/api/public-key` response:
```json
{
  "public_key": "...",
  "algorithm": "libsodium/box_seal",
  "key_version": 1,
  "instance_id": "server-hostname:5051"
}
```

Use `instance_id` to verify which backend instance client is connecting to.

## Implementation Details

### Private Key Loading Order
```python
1. Environment variable: ENCRYPTION_PRIVATE_KEY (production override)
   └─ Set for multi-instance deployments
   
2. SQLite database: agent/data/system/keys.db
   └─ Persists across restarts
   
3. Generate new keypair (only if neither above exists)
   └─ Single-instance development mode
```

### Storage
- **In SQLite**: Encrypted keys stored with metadata (version, creation timestamp)
- **In Memory**: Only during runtime (not swapped to disk)
- **No .env Files**: Uses environment variables or database for persistence

### Client-Side Behavior
- Fetches public key via `/api/public-key`
- Caches in `browser.storage.local`
- Auto-retries with fresh key on HTTP 400 error
- Fallback to plaintext transmission if encryption fails

## Security Considerations

1. **Environment Variable Exposure**
   - ✅ Avoid logging `ENCRYPTION_PRIVATE_KEY`
   - ✅ Restrict container/pod logs access
   - ✅ Use secrets management systems (Kubernetes, Vault, etc.)

2. **Database File Permissions**
   - ✅ Restrict access: `chmod 600 agent/data/system/keys.db`
   - ✅ Only backend service process should read it

3. **Transport Security**
   - ✅ Always use HTTPS in production
   - ✅ Encryption is redundant with HTTPS but provides defense-in-depth

4. **Key Rotation**
   - ✅ Establish annual key rotation policy
   - ✅ Document rotation procedures
   - ✅ Test rotation in non-production first

## References

- [libsodium Documentation](https://doc.libsodium.org/)
- [PyNaCl Documentation](https://pynacl.readthedocs.io/)
- [Ed25519 Signature Scheme](https://en.wikipedia.org/wiki/EdDSA)
- [NaCl Box (Public Key Encryption)](https://nacl.cr.yp.to/box.html)
