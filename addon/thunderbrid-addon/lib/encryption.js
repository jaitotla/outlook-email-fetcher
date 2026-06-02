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
 * Get and cache the public key from backend
 * @param {string} backendUrl - Backend base URL
 * @return {string} Base64-encoded public key
 */
async function _getEncryptionPublicKey(backendUrl) {
  try {
    // Try to get from storage cache first
    const cached = await _safeStorageGet("encryption_public_key");
    if (cached) {
      console.log("[Encryption] ✅ Using cached public key");
      return cached;
    }

    // Fetch fresh from backend
    console.log("[Encryption] 📤 Fetching public key from backend...");
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

    // Cache the public key
    await _safeStorageSet({ encryption_public_key: data.public_key }, "cache public key");
    
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
 * Send encrypted settings to backend encrypted endpoint
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
    const publicKeyB64 = await _getEncryptionPublicKey(backendUrl);
    if (!publicKeyB64) {
      console.warn("[Encryption] ⚠️  Failed to get public key, falling back to plaintext");
      return _syncSettingsToBackend(settings, userEmail);
    }
    
    // Encrypt settings
    const encryptedPayload = await _encryptSettings(publicKeyB64, settings);
    
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
    
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    
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
 * Clear cached public key (use when rotating keys)
 */
async function _clearPublicKeyCache() {
  try {
    const storage = await browser.storage.local.get("encryption_public_key");
    if (storage.encryption_public_key) {
      await browser.storage.local.remove("encryption_public_key");
      console.log("[Encryption] ✅ Cleared cached public key");
    }
  } catch (e) {
    console.error("[Encryption] ⚠️  Error clearing cache:", e.message);
  }
}
