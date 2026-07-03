/**
 * Encryption Module for Thunderbird Add-on
 * Uses libsodium.js for client-side encryption
 * 
 * Add to: addon/thunderbrid-addon/background.js
 * Or create as: addon/thunderbrid-addon/lib/encryption.js
 */

/**
 * Load libsodium.js library
 * Uses a CDN-based approach compatible with Thunderbird WebExtensions
 */
async function _loadSodiumLibrary() {
  return new Promise((resolve, reject) => {
    // Check if already loaded
    if (window.sodium && window.sodium.crypto_box_seal) {
      console.log("[Encryption] ✅ Sodium library already loaded");
      resolve(window.sodium);
      return;
    }

    // Load from CDN
    const script = document.createElement("script");
    script.src = "https://cdn.jsdelivr.net/npm/libsodium-wrappers@0.7.11/dist/sodium.min.js";
    
    script.onload = () => {
      // sodium_config runs in the global scope
      if (window.sodium) {
        window.sodium.onload = () => {
          console.log("[Encryption] ✅ Libsodium loaded from CDN");
          resolve(window.sodium);
        };
      } else {
        reject(new Error("Sodium library failed to load from CDN"));
      }
    };
    
    script.onerror = () => {
      console.error("[Encryption] ❌ Failed to load libsodium from CDN");
      reject(new Error("Failed to load libsodium from CDN"));
    };
    
    // Append to document head if available, otherwise use body
    const target = document.head || document.body;
    if (target) {
      target.appendChild(script);
    } else {
      reject(new Error("No document target to load script"));
    }
  });
}

/**
 * Get and cache the public key from backend with version checking
 * @param {string} backendUrl - Backend base URL
 * @param {boolean} forceRefresh - Force fetch fresh key (bypass cache)
 * @return {string} Base64-encoded public key
 */
async function _getEncryptionPublicKey(backendUrl, forceRefresh = false) {
  try {
    // Try to get from storage cache first (unless forced to refresh)
    if (!forceRefresh) {
      const cached = await _safeStorageGet("encryption_public_key");
      const cachedVersion = await _safeStorageGet("encryption_key_version");
      
      if (cached) {
        console.log("[Encryption] ✅ Using cached public key (v" + cachedVersion + ")");
        return cached;
      }
    }

    // Fetch fresh from backend
    if (forceRefresh) {
      console.log("[Encryption] 🔄 Force-refreshing public key from backend...");
    } else {
      console.log("[Encryption] 📤 Fetching public key from backend...");
    }
    
    const url = backendUrl.replace(/\/$/, "") + "/api/public-key";
    
    const response = await fetch(url, {
      method: "GET",
      headers: { "Accept": "application/json" }
    });

    if (!response.ok) {
      throw new Error(`Backend returned ${response.status}`);
    }

    const data = await response.json();
    if (!data.public_key) {
      throw new Error("No public_key in response");
    }

    // Cache both key and version
    await _safeStorageSet({
      encryption_public_key: data.public_key,
      encryption_key_version: data.key_version || 1
    }, "cache public key with version");
    
    console.log("[Encryption] ✅ Fetched and cached public key");
    console.log(`   Algorithm: ${data.algorithm}`);
    console.log(`   Version: ${data.key_version}`);
    
    return data.public_key;
  } catch (e) {
    console.error("[Encryption] ❌ Error fetching public key:", e.message);
    return null;
  }
}

/**
 * Encrypt settings using libsodium box_seal
 * @param {string} publicKeyB64 - Base64-encoded public key
 * @param {Object} settings - Settings object to encrypt
 * @return {string} Base64-encoded encrypted payload
 */
async function _encryptSettings(publicKeyB64, settings) {
  try {
    const sodium = await _loadSodiumLibrary();
    
    // Convert settings to JSON
    const plaintext = JSON.stringify(settings);
    console.log(`[Encryption] 📝 Encrypting ${plaintext.length} bytes...`);
    
    // Decode public key from base64
    const publicKeyBytes = sodium.from_base64(publicKeyB64);
    const plaintextBytes = sodium.from_string(plaintext);
    
    // Encrypt using box_seal (anonymous encryption - no nonce needed)
    const encryptedBytes = sodium.crypto_box_seal(plaintextBytes, publicKeyBytes);
    
    // Encode to base64 for transmission
    const encryptedB64 = sodium.to_base64(encryptedBytes);
    console.log(`[Encryption] 🔒 Encrypted: ${encryptedB64.length} bytes (base64)`);
    
    return encryptedB64;
  } catch (e) {
    console.error("[Encryption] ❌ Encryption failed:", e.message);
    console.error("[Encryption] ⚠️  Fallback: Will send plaintext over HTTPS");
    
    // Fallback: return base64-encoded plaintext (still transported over HTTPS)
    const encoder = new TextEncoder();
    const bytes = encoder.encode(JSON.stringify(settings));
    const fallbackB64 = _bytesToBase64(bytes);
    return fallbackB64;
  }
}

/**
 * Convert Uint8Array to base64 string
 * @param {Uint8Array} bytes
 * @return {string} Base64 string
 */
function _bytesToBase64(bytes) {
  let binary = '';
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

/**
 * Send encrypted settings to backend encrypted endpoint with auto-retry on key mismatch
 * @param {Object} settings - Settings object
 * @param {string} userEmail - User email ID
 * @param {string} backendUrl - Backend base URL
 * @return {Object} Server response
 */
async function _syncSettingsToBackendEncrypted(settings, userEmail, backendUrl) {
  if (!userEmail) {
    throw new Error("User email required to sync settings");
  }

  try {
    console.log("[Encryption] 🔐 Starting encrypted settings sync...");
    
    // Get public key
    let publicKeyB64 = await _getEncryptionPublicKey(backendUrl);
    if (!publicKeyB64) {
      console.warn("[Encryption] ⚠️  Failed to get public key, falling back to plaintext");
      return _syncSettingsToBackend(settings, userEmail);
    }
    
    // Encrypt settings
    let encryptedPayload = await _encryptSettings(publicKeyB64, settings);
    
    // Send encrypted payload
    const base = backendUrl.replace(/\/$/, "").replace(/\/api$/, "");
    const endpoint = `${base}/api/settings/encrypted`;
    
    console.log(`[Encryption] 📤 Sending encrypted payload to ${endpoint}`);
    
    const payload = {
      user_id: userEmail,
      encrypted_payload: encryptedPayload,
      key_version: 1,
      timestamp: new Date().toISOString()
    };
    
    let response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    
    // Auto-retry with fresh key if we get a 400 (likely decryption failure)
    if (response.status === 400) {
      console.warn("[Encryption] ⚠️  Decryption failed (400) - Likely key mismatch");
      console.warn("[Encryption] 🔄 Refreshing public key and retrying...");
      
      // Force refresh the public key
      publicKeyB64 = await _getEncryptionPublicKey(backendUrl, true);
      if (!publicKeyB64) {
        throw new Error("Failed to refresh public key after 400 error");
      }
      
      // Re-encrypt with fresh key
      encryptedPayload = await _encryptSettings(publicKeyB64, settings);
      
      // Retry
      payload.encrypted_payload = encryptedPayload;
      response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
    }
    
    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`Backend ${response.status}: ${errText}`);
    }
    
    const result = await response.json();
    console.log(`[Encryption] ✅ Encrypted sync complete!`);
    console.log(`   Transport: ${result.transport}`);
    console.log(`   Storage: ${result.storage}`);
    
    return result;
  } catch (e) {
    console.error("[Encryption] ❌ Encrypted sync failed:", e.message);
    console.warn("[Encryption] ⚠️  Attempting fallback to plaintext...");
    
    // Fallback: send plaintext (will be encrypted at rest)
    try {
      return _syncSettingsToBackend(settings, userEmail);
    } catch (fallbackErr) {
      console.error("[Encryption] ❌ Fallback also failed:", fallbackErr.message);
      throw fallbackErr;
    }
  }
}

/**
 * Clear cached public key and force refresh on next encryption
 * Call this when you suspect the backend has rotated keys
 */
async function _clearPublicKeyCache() {
  try {
    await browser.storage.local.remove(["encryption_public_key", "encryption_key_version"]);
    console.log("[Encryption] ✅ Cleared cached public key and version");
    console.log("[Encryption] 📝 Next encryption will fetch fresh key from backend");
  } catch (e) {
    console.error("[Encryption] ⚠️  Error clearing cache:", e.message);
  }
}

/**
 * Manual force-refresh of the public key from backend
 * Returns the new key version on success
 */
async function _refreshEncryptionKeyManual(backendUrl) {
  try {
    console.log("[Encryption] 🔄 Manual force-refresh of public key...");
    await _clearPublicKeyCache();
    
    const newKey = await _getEncryptionPublicKey(backendUrl, true);
    if (!newKey) {
      throw new Error("Failed to fetch fresh public key");
    }
    
    const version = await _safeStorageGet("encryption_key_version");
    console.log("[Encryption] ✅ Public key refreshed successfully!");
    console.log(`[Encryption] 📌 New version: ${version}`);
    
    return { success: true, key_version: version };
  } catch (e) {
    console.error("[Encryption] ❌ Manual refresh failed:", e.message);
    return { success: false, error: e.message };
  }
}
