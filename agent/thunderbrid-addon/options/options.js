/**
 * Options/Settings script for Email Thread Assistant
 * Handles loading and saving user preferences
 */

const MANOTR_AGENT_URL = "http://omb.manotr.com";
const DEFAULT_BACKEND_URL = MANOTR_AGENT_URL;

/**
 * Get the configured backend URL
 */
async function getBackendUrl() {
  try {
    const r = await browser.storage.local.get("user_settings");
    return (r.user_settings && (r.user_settings.agent_url || r.user_settings.backend_url)) || DEFAULT_BACKEND_URL;
  } catch (e) { return DEFAULT_BACKEND_URL; }
}

// Default settings
const DEFAULT_SETTINGS = {
  agent_url: MANOTR_AGENT_URL,
  mode: "",
  llm_provider: "manotr",
  llm_api_key: "",
  llm_model: "gpt-4o-mini",
  llm_base_url: "",
  embedding_provider: "manotr",
  embedding_api_key: "",
  embedding_model: "text-embedding-3-small",
  vector_provider: "manotr",
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
  await detectAndDisplayEmail();
  await loadSettings();
  setupEventListeners();
});

// ─── Email display ───────────────────────────────────────────────────────────

async function detectAndDisplayEmail() {
  const el = document.getElementById("detected-email");
  if (!el) return;
  try {
    const accounts = await browser.accounts.list();
    const email = (accounts.length > 0 && accounts[0].identities.length > 0)
      ? accounts[0].identities[0].email
      : null;
    el.textContent = email || "Could not detect — check Thunderbird account settings";
    el.classList.toggle("readonly-field-ok", !!email);
  } catch (e) {
    el.textContent = "Could not detect account";
  }
}

// ─── Mode-aware field visibility ─────────────────────────────────────────────

/**
 * Handle mode selection:
 *   manotr  → auto-set agent URL to omb.manotr.com, hide URL input
 *   local / external → show required agent URL input
 *   (empty) → hide agent URL and rest-of-settings
 */
function updateModeFields() {
  const mode = document.getElementById("mode").value;
  const manotrUrlInfo  = document.getElementById("manotr-url-info");
  const restSettings   = document.getElementById("rest-of-settings");
  const agentUrlInput  = document.getElementById("agent_url");
  const agentUrlHint   = document.getElementById("agent-url-hint");

  if (mode === "manotr") {
    agentUrlInput.value = MANOTR_AGENT_URL;
    agentUrlInput.readOnly = false;        // still allow override
    agentUrlInput.style.background = "#f0f7ff";
    agentUrlInput.style.color = "#1a73e8";
    if (agentUrlHint) agentUrlHint.innerHTML = "<em>Auto-set for Manotr — edit only if you self-host.</em>";
    manotrUrlInfo.classList.remove("hidden");
    restSettings.classList.remove("hidden");
  } else if (mode) {
    // local or external — clear Manotr URL if still set
    if (agentUrlInput.value === MANOTR_AGENT_URL) agentUrlInput.value = "";
    agentUrlInput.readOnly = false;
    agentUrlInput.style.background = "";
    agentUrlInput.style.color = "";
    agentUrlInput.setAttribute("required", "");
    if (agentUrlHint) agentUrlHint.innerHTML = "<em>Enter the URL where your agent server is running.</em>";
    manotrUrlInfo.classList.add("hidden");
    restSettings.classList.remove("hidden");
  } else {
    // No mode chosen yet
    agentUrlInput.value = "";
    agentUrlInput.readOnly = true;
    agentUrlInput.style.background = "#f5f5f5";
    agentUrlInput.style.color = "#aaa";
    agentUrlInput.removeAttribute("required");
    if (agentUrlHint) agentUrlHint.innerHTML = "<em>Choose a mode above first.</em>";
    manotrUrlInfo.classList.add("hidden");
    restSettings.classList.add("hidden");
  }
}


/**
 * Show/hide LLM sub-fields based on the selected provider.
 *   manotr  → nothing extra needed (all hidden)
 *   openai/anthropic/groq → api_key + model
 *   ollama  → model + base_url
 */
function updateLLMFields() {
  const provider = document.getElementById("llm_provider").value;
  const apiKeyGroup  = document.getElementById("llm-api-key-group");
  const modelGroup   = document.getElementById("llm-model-group");
  const baseUrlGroup = document.getElementById("llm-base-url-group");

  const needsApiKey  = ["openai", "anthropic", "groq"].includes(provider);
  const needsModel   = ["openai", "anthropic", "groq", "ollama"].includes(provider);
  const needsBaseUrl = provider === "ollama";

  apiKeyGroup.classList.toggle("hidden",  !needsApiKey);
  modelGroup.classList.toggle("hidden",   !needsModel);
  baseUrlGroup.classList.toggle("hidden", !needsBaseUrl);
}

/**
 * Show/hide Embedding sub-fields based on the selected provider.
 *   manotr → nothing
 *   openai → api_key + model
 *   ollama → model only
 */
function updateEmbeddingFields() {
  const provider = document.getElementById("embedding_provider").value;
  const apiKeyGroup = document.getElementById("embedding-api-key-group");
  const modelGroup  = document.getElementById("embedding-model-group");

  const needsApiKey = provider === "openai";
  const needsModel  = ["openai", "ollama"].includes(provider);

  apiKeyGroup.classList.toggle("hidden", !needsApiKey);
  modelGroup.classList.toggle("hidden",  !needsModel);
}

/**
 * Show/hide Vector sub-fields based on the selected provider.
 *   manotr → nothing
 *   pinecone/qdrant → url + api_key
 */
function updateVectorFields() {
  const provider = document.getElementById("vector_provider").value;
  const urlGroup    = document.getElementById("vector-url-group");
  const apiKeyGroup = document.getElementById("vector-api-key-group");

  const needsConfig = provider !== "manotr";
  urlGroup.classList.toggle("hidden",    !needsConfig);
  apiKeyGroup.classList.toggle("hidden", !needsConfig);
}

// ─────────────────────────────────────────────────────────────────────────────

/**
 * Setup event listeners
 */
function setupEventListeners() {
  document.getElementById("settings-form").addEventListener("submit", handleSave);
  document.getElementById("reset-btn").addEventListener("click", handleReset);

  // Mode drives agent URL visibility + rest-of-settings reveal
  document.getElementById("mode").addEventListener("change", updateModeFields);

  // Re-evaluate visibility whenever a provider dropdown changes
  document.getElementById("llm_provider").addEventListener("change", updateLLMFields);
  document.getElementById("embedding_provider").addEventListener("change", updateEmbeddingFields);
  document.getElementById("vector_provider").addEventListener("change", updateVectorFields);
}

/**
 * Load settings from storage
 */
async function loadSettings() {
  try {
    const result = await browser.storage.local.get(["user_settings", "domain_filters", "process_last_n_months"]);
    const rawSettings = result.user_settings || DEFAULT_SETTINGS;
    
    // Map legacy field names
    const settings = Object.assign({}, rawSettings);
    if (settings.backend_url && !settings.agent_url) {
      settings.agent_url = settings.backend_url;
    }
    // Map legacy "inbuilt" to "manotr"
    for (const key of ["mode", "llm_provider", "embedding_provider", "vector_provider"]) {
      if (settings[key] === "inbuilt") settings[key] = "manotr";
    }

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

    // Apply mode-aware visibility first (drives agent URL + rest-of-settings)
    updateModeFields();

    // Apply provider-aware field visibility after values are loaded
    updateLLMFields();
    updateEmbeddingFields();
    updateVectorFields();
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

    // Re-apply visibility for default selections
    updateModeFields();
    updateLLMFields();
    updateEmbeddingFields();
    updateVectorFields();

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