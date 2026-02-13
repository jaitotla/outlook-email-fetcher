/**
 * Options/Settings script for Email Thread Assistant
 * Handles loading and saving user preferences
 */

// Default backend URL
const DEFAULT_BACKEND_URL = "http://43.204.98.38:8000";

/**
 * Get the configured backend URL
 */
async function getBackendUrl() {
  try {
    const result = await browser.storage.local.get("backend_url");
    return result.backend_url || DEFAULT_BACKEND_URL;
  } catch (error) {
    console.error("Error getting backend URL:", error);
    return DEFAULT_BACKEND_URL;
  }
}

// Default settings
const DEFAULT_SETTINGS = {
  backend_url: "http://43.204.98.38:8000",
  mode: "inbuilt",
  llm_provider: "inbuilt",
  llm_api_key: "",
  llm_model: "gpt-4o-mini",
  llm_base_url: "",
  embedding_provider: "inbuilt",
  embedding_api_key: "",
  embedding_model: "text-embedding-3-small",
  vector_provider: "inbuilt",
  vector_url: "",
  vector_api_key: "",
  user_name: "",
  user_position: "",
  user_tone: "professional",
  system_prompt: ""
};

// Initialize options page
document.addEventListener("DOMContentLoaded", async () => {
  await loadSettings();
  setupEventListeners();
});

/**
 * Setup event listeners
 */
function setupEventListeners() {
  document.getElementById("settings-form").addEventListener("submit", handleSave);
  document.getElementById("reset-btn").addEventListener("click", handleReset);
}

/**
 * Load settings from storage
 */
async function loadSettings() {
  try {
    const result = await browser.storage.local.get("user_settings");
    const settings = result.user_settings || DEFAULT_SETTINGS;
    
    // Populate form fields
    Object.keys(settings).forEach(key => {
      const element = document.getElementById(key);
      if (element) {
        element.value = settings[key] || "";
      }
    });
    
    console.log("Settings loaded successfully");
  } catch (error) {
    console.error("Error loading settings:", error);
    showStatus("Error loading settings: " + error.message, "error");
  }
}

/**
 * Save settings
 */
async function handleSave(event) {
  event.preventDefault();
  
  try {
    const form = document.getElementById("settings-form");
    const formData = new FormData(form);
    
    const settings = {};
    for (const [key, value] of formData.entries()) {
      settings[key] = value;
    }
    
    // Save to local storage
    await browser.storage.local.set({ user_settings: settings });
    
    // Also save backend_url separately for quick access
    if (settings.backend_url) {
      await browser.storage.local.set({ backend_url: settings.backend_url });
    }
    
    // Sync to backend (best effort)
    try {
      await syncSettingsToBackend(settings);
      showStatus("✅ Settings saved successfully and synced to server!", "success");
    } catch (syncErr) {
      console.log("Settings sync to backend failed:", syncErr.message);
      showStatus("✅ Settings saved locally (server sync failed)", "success");
    }
    
  } catch (error) {
    console.error("Error saving settings:", error);
    showStatus("❌ Error saving settings: " + error.message, "error");
  }
}

/**
 * Reset settings to defaults
 */
async function handleReset() {
  if (!confirm("Are you sure you want to reset all settings to defaults?")) {
    return;
  }
  
  try {
    await browser.storage.local.remove("user_settings");
    
    // Reload form with defaults
    Object.keys(DEFAULT_SETTINGS).forEach(key => {
      const element = document.getElementById(key);
      if (element) {
        element.value = DEFAULT_SETTINGS[key] || "";
      }
    });
    
    showStatus("🔄 Settings reset to defaults!", "success");
  } catch (error) {
    console.error("Error resetting settings:", error);
    showStatus("❌ Error resetting settings: " + error.message, "error");
  }
}

/**
 * Sync settings to backend server
 */
async function syncSettingsToBackend(settings) {
  const userId = await getUserId();
  const backendUrl = await getBackendUrl();
  const endpoint = `${backendUrl}/api/settings`;
  
  const payload = {
    user_id: userId,
    settings: settings
  };
  
  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
  
  if (!response.ok) {
    throw new Error(`Backend returned error: ${response.status} - ${await response.text()}`);
  }
  
  return await response.json();
}

/**
 * Get user ID (email address)
 */
async function getUserId() {
  try {
    const accounts = await browser.accounts.list();
    if (accounts.length > 0 && accounts[0].identities.length > 0) {
      return accounts[0].identities[0].email;
    }
    return "unknown@user.com";
  } catch (error) {
    console.error("Error getting user ID:", error);
    return "unknown@user.com";
  }
}

/**
 * Show status message
 */
function showStatus(message, type) {
  const statusEl = document.getElementById("status-message");
  statusEl.textContent = message;
  statusEl.className = `status-message ${type}`;
  statusEl.classList.remove("hidden");
  
  // Auto-hide after 5 seconds
  setTimeout(() => {
    statusEl.classList.add("hidden");
  }, 5000);
}