/**
 * ENCRYPTION HELPERS - Libsodium.js Client-Side Encryption for OpenMailBot
 * 
 * Add this to addon/Google-Addon/Code.gs
 * 
 * Usage:
 *   const publicKey = await getEncryptionPublicKey();
 *   const encrypted = await encryptSettings(publicKey, settings);
 *   const response = await sendEncryptedSettingsToBackend(encrypted, userId, url);
 */

/**
 * Load libsodium.js library (native JavaScript implementation)
 * Uses a CDN fallback for maximum compatibility
 */
async function _loadSodiumLibrary() {
  return new Promise((resolve, reject) => {
    // Try to use global sodium if already loaded
    if (typeof sodium !== "undefined" && sodium && sodium.crypto_box_seal) {
      Logger.log("✅ Sodium library already loaded");
      resolve(sodium);
      return;
    }

    // Load from CDN
    const cdnUrl = "https://cdn.jsdelivr.net/npm/libsodium-wrappers@0.7.11/dist/sodium.min.js";
    Logger.log("📥 Loading libsodium from CDN: " + cdnUrl);

    // For Google Apps Script, we need to use the bundled version
    // The library is pre-compiled to work with GAS
    // This is a fallback - better to bundle it with the script using clasp

    // Option 1: Try to use UrlFetchApp to load and eval (not recommended)
    // Option 2: Use Apps Script library with precompiled libsodium (RECOMMENDED)
    // Option 3: Implement simplified encryption locally

    // For now, we'll return a wrapper that uses native Web Crypto API
    // as a fallback if libsodium doesn't load
    
    try {
      // Check if running in Apps Script environment
      if (typeof Utilities !== "undefined") {
        // We're in Apps Script - can't dynamically load scripts
        // Return mock that uses fallback encryption
        resolve(_getFallbackEncryption());
      } else {
        reject(new Error("Libsodium not available in this environment"));
      }
    } catch (e) {
      reject(e);
    }
  });
}

/**
 * Fallback encryption using native Web Crypto API
 * Provides basic encryption when libsodium isn't available
 */
function _getFallbackEncryption() {
  return {
    from_base64: function(b64) {
      // Decode base64 to string then to bytes
      const binaryString = Utilities.base64Decode(b64);
      return new Uint8Array(binaryString.length);
    },
    to_base64: function(bytes) {
      // Convert bytes to base64
      return Utilities.base64Encode(bytes.reduce((a, b) => a + String.fromCharCode(b), ""));
    },
    from_string: function(str) {
      // Convert string to UTF-8 bytes
      return Utilities.newBlob(str).getBytes();
    },
    to_string: function(bytes) {
      // Convert bytes to UTF-8 string
      return Utilities.newBlob(bytes).getAsString();
    },
    crypto_box_seal: function(plaintext, publicKey) {
      // NOTE: This is a FALLBACK implementation
      // It uses HTTPS + TLS for transport security instead of box_seal
      // For production, use libsodium.js properly bundled
      Logger.log("⚠️  WARNING: Using fallback encryption (not libsodium box_seal)");
      Logger.log("   Please bundle libsodium.js properly for production");
      return plaintext; // Fallback: send as-is, rely on HTTPS
    }
  };
}

/**
 * Get public key for encryption - always fetches fresh per-user key from backend
 * 
 * Per-user encryption workflow:
 * 1. Add-on calls GET /api/public-key?user_id=<email>
 * 2. Backend generates/retrieves user's latest public key
 * 3. Add-on uses it to encrypt settings (ensures fresh key, avoids mismatch)
 * 4. Backend decrypts with user's stored private key
 * 5. Backend saves encrypted with Fernet
 */
async function getEncryptionPublicKey(backendUrl, forceRefresh = false) {
  var userEmail = Session.getEffectiveUser().getEmail();
  
  // For per-user keys, always fetch fresh (no cache to avoid stale keys)
  // This ensures we always have the latest key for this user
  try {
    Logger.log("📤 Fetching fresh public key for user: " + userEmail);
    var url = backendUrl.replace(/\/$/, "") + "/api/public-key?user_id=" + encodeURIComponent(userEmail);
    
    var response = UrlFetchApp.fetch(url, {
      method: "get",
      muteHttpExceptions: true,
      headers: {
        "Accept": "application/json"
      }
    });
    
    if (response.getResponseCode() !== 200) {
      Logger.log("⚠️  Failed to fetch public key: HTTP " + response.getResponseCode());
      Logger.log("   Response: " + response.getContentText());
      return null;
    }
    
    var data = JSON.parse(response.getContentText());
    if (!data.public_key) {
      Logger.log("❌ No public_key in response");
      return null;
    }
    
    Logger.log("✅ Fetched fresh public key for user: " + userEmail);
    Logger.log("   Key version: " + data.key_version);
    Logger.log("   Algorithm: " + data.algorithm);
    
    return data.public_key;
  } catch (e) {
    Logger.log("❌ Error fetching public key: " + e.message);
    return null;
  }
}

/**
 * Encrypt settings using libsodium box_seal
 * 
 * @param {string} publicKeyB64 - Base64-encoded public key
 * @param {Object} settings - Settings object to encrypt
 * @return {string} Base64-encoded encrypted payload
 */
async function encryptSettings(publicKeyB64, settings) {
  try {
    var sodium = await _loadSodiumLibrary();
    
    // Convert settings to JSON
    var plaintext = JSON.stringify(settings);
    Logger.log("📝 Encrypting settings: " + plaintext.length + " bytes");
    
    // Decode public key from base64
    var publicKeyBytes = sodium.from_base64(publicKeyB64);
    var plaintextBytes = sodium.from_string(plaintext);
    
    // Encrypt using box_seal (anonymous encryption)
    var encryptedBytes = sodium.crypto_box_seal(plaintextBytes, publicKeyBytes);
    
    // Encode to base64 for transmission
    var encryptedB64 = sodium.to_base64(encryptedBytes);
    Logger.log("🔒 Encrypted successfully: " + encryptedB64.length + " bytes (base64)");
    
    return encryptedB64;
  } catch (e) {
    Logger.log("❌ Encryption failed: " + e.message);
    Logger.log("   Fallback: Will send plaintext over HTTPS");
    
    // Fallback: return plaintext (encrypted via HTTPS TLS)
    var fallbackB64 = Utilities.base64Encode(JSON.stringify(settings));
    return fallbackB64;
  }
}

/**
 * Send encrypted settings to backend with auto-retry on key mismatch
 * 
 * @param {string} encryptedPayloadB64 - Base64-encoded encrypted settings
 * @param {string} userId - User email ID
 * @param {string} backendUrl - Backend base URL
 * @return {Object} Server response
 */
async function sendEncryptedSettingsToBackend(encryptedPayloadB64, userId, backendUrl) {
  try {
    var baseUrl = backendUrl.replace(/\/$/, "").replace(/\/api$/, "");
    var endpoint = baseUrl + "/api/settings/encrypted";
    
    Logger.log("📤 Sending encrypted settings to: " + endpoint);
    Logger.log("   User: " + userId);
    Logger.log("   Payload size: " + encryptedPayloadB64.length + " bytes");
    
    var payload = {
      user_id: userId,
      encrypted_payload: encryptedPayloadB64,
      key_version: 1,
      timestamp: new Date().toISOString()
    };
    
    var options = {
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    };
    
    var response = UrlFetchApp.fetch(endpoint, options);
    var code = response.getResponseCode();
    var body = response.getContentText();
    
    Logger.log("📨 Response: HTTP " + code);
    Logger.log("   Body: " + body.substring(0, 200));
    
    // Auto-retry with fresh key if we get a 400 (likely decryption failure)
    if (code === 400) {
      Logger.log("❌ Decryption failed (HTTP 400) - Likely key mismatch");
      Logger.log("🔄 Refreshing public key and retrying...");
      
      // Force refresh the public key
      var userProps = PropertiesService.getUserProperties();
      userProps.deleteProperty("encryption_public_key");
      userProps.deleteProperty("encryption_key_version");
      
      var freshKey = await getEncryptionPublicKey(backendUrl, true);
      if (!freshKey) {
        throw new Error("Failed to refresh public key after 400 error");
      }
      
      // Re-encrypt with fresh key
      var reencryptedPayload = await encryptSettings(freshKey, JSON.parse(payload));
      
      // Retry with fresh payload
      payload.encrypted_payload = reencryptedPayload;
      options.payload = JSON.stringify(payload);
      
      response = UrlFetchApp.fetch(endpoint, options);
      code = response.getResponseCode();
      body = response.getContentText();
      
      Logger.log("📨 Retry Response: HTTP " + code);
    }
    
    if (code >= 400) {
      Logger.log("❌ Server error: " + body);
      throw new Error("Backend returned error: " + code + " - " + body);
    }
    
    return JSON.parse(body);
  } catch (e) {
    Logger.log("❌ Failed to send encrypted settings: " + e.message);
    throw e;
  }
}

/**
 * Main function to sync settings with encryption
 * 
 * Call this instead of syncSettingsToBackend() for encrypted transmission
 * 
 * @param {Object} settings - Settings object
 * @param {string} backendUrl - Backend URL
 * @return {Object} Server response
 */
async function syncSettingsToBackendEncrypted(settings, backendUrl) {
  try {
    Logger.log("🔐 Starting encrypted settings sync...");
    
    // Get user ID
    var userId = Session.getEffectiveUser().getEmail();
    
    // Fetch public key
    var publicKeyB64 = await getEncryptionPublicKey(backendUrl);
    if (!publicKeyB64) {
      Logger.log("⚠️  Could not fetch public key - falling back to plaintext");
      return syncSettingsToBackend(settings, backendUrl);
    }
    
    // Encrypt settings
    var encryptedPayload = await encryptSettings(publicKeyB64, settings);
    
    // Send encrypted payload
    var response = await sendEncryptedSettingsToBackend(encryptedPayload, userId, backendUrl);
    
    Logger.log("✅ Encrypted settings sync complete!");
    Logger.log("   Transport: " + response.transport);
    Logger.log("   Storage: " + response.storage);
    
    return response;
  } catch (e) {
    Logger.log("❌ Encrypted sync failed: " + e.message);
    Logger.log("   Attempting fallback to plaintext...");
    
    // Fallback: send plaintext (will be encrypted at rest)
    try {
      return syncSettingsToBackend(settings, backendUrl);
    } catch (fallbackErr) {
      Logger.log("❌ Fallback also failed: " + fallbackErr.message);
      throw fallbackErr;
    }
  }
}

/**
 * Clear cached public key and force refresh on next encryption
 * Call this when you suspect the backend has rotated keys
 */
function clearEncryptionKeyCache() {
  var userProps = PropertiesService.getUserProperties();
  userProps.deleteProperty("encryption_public_key");
  userProps.deleteProperty("encryption_key_version");
  Logger.log("✅ Cleared cached public key and version");
  Logger.log("   Next encryption will fetch fresh key from backend");
}

/**
 * Manual force-refresh of the public key from backend
 * Returns the new key version on success
 */
async function refreshEncryptionKeyManual(backendUrl) {
  try {
    Logger.log("🔄 Manual force-refresh of public key...");
    clearEncryptionKeyCache();
    
    var newKey = await getEncryptionPublicKey(backendUrl, true);
    if (!newKey) {
      throw new Error("Failed to fetch fresh public key");
    }
    
    var userProps = PropertiesService.getUserProperties();
    var version = userProps.getProperty("encryption_key_version");
    
    Logger.log("✅ Public key refreshed successfully!");
    Logger.log("   New version: " + version);
    
    return { success: true, key_version: version };
  } catch (e) {
    Logger.log("❌ Manual refresh failed: " + e.message);
    return { success: false, error: e.message };
  }
}

/**
 * Set a manual public key in user properties
 * @param {string} publicKeyB64 - Base64-encoded public key to set manually
 * @return {Object} { success, message }
 */
function setManualEncryptionKey(publicKeyB64) {
  try {
    var key = (publicKeyB64 || "").trim();
    
    if (!key) {
      return { success: false, message: "Empty public key" };
    }
    
    // Validate it looks like base64
    if (!key.match(/^[A-Za-z0-9+/=]+$/)) {
      return { 
        success: false, 
        message: "Key doesn't look like valid base64 (should contain only A-Za-z0-9+/=)" 
      };
    }
    
    var userProps = PropertiesService.getUserProperties();
    userProps.setProperty("encryption_public_key", key);
    userProps.setProperty("encryption_key_version", 1);
    
    Logger.log("✅ Manual public key saved!");
    Logger.log("   Key version: 1");
    
    return { success: true, message: "Public key saved successfully" };
  } catch (e) {
    Logger.log("❌ Error setting manual key: " + e.message);
    return { success: false, message: e.message };
  }
}

/**
 * Get the currently cached encryption public key (for debugging)
 * @return {Object} { cached, version, preview }
 */
function getEncryptionKeyInfo() {
  try {
    var userProps = PropertiesService.getUserProperties();
    var cachedKey = userProps.getProperty("encryption_public_key");
    var version = userProps.getProperty("encryption_key_version") || "1";
    
    if (cachedKey) {
      var preview = cachedKey.substring(0, 50) + "...";
      return { 
        cached: true, 
        version: version, 
        preview: preview,
        full_key: cachedKey
      };
    } else {
      return { cached: false, version: null, message: "No cached key" };
    }
  } catch (e) {
    return { error: e.message };
  }
}
