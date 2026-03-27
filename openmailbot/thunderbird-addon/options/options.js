/**
 * Options/Settings script for Email Thread Assistant
 * Handles loading and saving user preferences
 */

// Default backend URL
const DEFAULT_BACKEND_URL = "http://43.204.98.38:5050";

/**
 * Get the configured backend URL
 */
async function getBackendUrl() {
  try {
    const r = await browser.storage.local.get("user_settings");
    return (r.user_settings && r.user_settings.backend_url) || DEFAULT_BACKEND_URL;
  } catch (e) { return DEFAULT_BACKEND_URL; }
}

// Default settings
const DEFAULT_SETTINGS = {
  backend_url: "http://43.204.98.38:5050",
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

// Load the bundled addon_config.json (addon-side config, like .env / app secrets)
async function getAddonConfig() {
  try {
    const url  = browser.runtime.getURL("addon_config.json");
    const resp = await fetch(url);
    if (resp.ok) return await resp.json();
  } catch (e) { console.warn("addon_config.json not loaded:", e.message); }
  return {};
}

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
    const result = await browser.storage.local.get(["user_settings", "domain_filters", "process_last_n_months"]);
    const settings = result.user_settings || DEFAULT_SETTINGS;

    // Populate user_settings fields
    Object.keys(settings).forEach(key => {
      const element = document.getElementById(key);
      if (element) element.value = settings[key] || "";
    });

    // Populate domain_filters — merge storage + addon_config.json defaults
    const filtersEl = document.getElementById("domain_filters");
    if (filtersEl) {
      const stored   = result.domain_filters || [];
      const cfg      = await getAddonConfig();
      const cfgDoms  = (cfg.domain_filters && cfg.domain_filters.blocked_domains)  || [];
      const cfgAddrs = (cfg.domain_filters && cfg.domain_filters.blocked_addresses) || [];
      const merged   = [...new Set([...stored, ...cfgDoms, ...cfgAddrs])];
      filtersEl.value = merged.join("\n");
    }

    // Populate process_months
    const monthsEl = document.getElementById("process_months");
    if (monthsEl) monthsEl.value = result.process_last_n_months || "3";

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
    
    // Parse + save domain_filters separately
    const filtersRaw = settings.domain_filters || "";
    delete settings.domain_filters;
    const filters = filtersRaw.split(/\n|,/).map(f => f.trim().toLowerCase()).filter(Boolean);
    await browser.storage.local.set({ domain_filters: filters });

    // Parse + save process_months separately
    const monthsVal = settings.process_months || "3";
    delete settings.process_months;
    await browser.storage.local.set({ process_last_n_months: monthsVal });

    // Save user_settings
    await browser.storage.local.set({ user_settings: settings });
    
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
    await browser.storage.local.remove(["user_settings", "domain_filters", "process_last_n_months"]);
    
    // Reload form with defaults
    Object.keys(DEFAULT_SETTINGS).forEach(key => {
      const element = document.getElementById(key);
      if (element) element.value = DEFAULT_SETTINGS[key] || "";
    });
    const filtersEl = document.getElementById("domain_filters");
    if (filtersEl) filtersEl.value = "";
    const monthsEl = document.getElementById("process_months");
    if (monthsEl) monthsEl.value = "3";
    
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