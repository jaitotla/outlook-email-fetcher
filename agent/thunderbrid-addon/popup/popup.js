/**
 * OpenMailBot — popup.js
 * Full feature parity with gmail_summariser.gs
 */

"use strict";

// ── CONSTANTS ──────────────────────────────────────────
const MANOTR_AGENT_URL = "http://omb.manotr.com";

// ── STATE ──────────────────────────────────────────────
let currentMessageId = null;
let currentAccountId = null;       // Track current account for bulk processing
let currentAccountEmail = null;    // Track current account email for all API calls
let currentSummary    = "";
let chatHistory       = [];
let localFilters      = [];        // working copy edited before save
let backendSettingsLoaded = false;
let backendSettings = null;

// Multi-account onboarding state
let allAccounts = [];              // All Thunderbird mail accounts
let onboardingIndex = 0;           // Current account index in onboarding flow
let onboardingAccountEmails = {};  // Map: accountId → email

const ALL_VIEWS = [
  "onboarding-view", "no-email-view", "main-menu", "loading", "summary-view", "draft-view",
  "chat-view", "error-view", "settings-view", "advanced-view", "bulk-status-view", "history-view"
];

// ── MODE-BASED VISIBILITY LOGIC ──────────────────────────────
/**
 * Update field visibility based on mode selection.
 * - manotr: hide API keys, URLs for LLM/Embedding/VectorDB, auto-select "manotr" providers
 * - local: show base URLs (for Ollama), hide external API keys
 * - external: show everything (API keys, providers, models)
 *
 * @param {string} prefix - "ob" for onboarding, "s" for settings
 */
function updateModeVisibility(prefix) {
  const mode = getVal(`${prefix}-mode`);

  // ── Agent URL: always visible, behaviour driven by mode ──
  const agentInput = document.getElementById(`${prefix}-agent-url`);
  const agentHint  = document.getElementById(`${prefix}-agent-url-hint`);
  
  console.log(`[updateModeVisibility] prefix=${prefix}, mode=${mode}, agentInput=`, agentInput);
  
  if (mode === "manotr") {
    if (agentInput) {
      agentInput.value = MANOTR_AGENT_URL;
      agentInput.readOnly = false;
      agentInput.removeAttribute("readonly");
      agentInput.style.background = "#f0f7ff";
      agentInput.style.color = "#1a73e8";
      agentInput.placeholder = MANOTR_AGENT_URL;
    }
    if (agentHint) agentHint.textContent = "Auto-set for Manotr — edit only if you self-host.";
    _showEl(`${prefix}-manotr-url-info`);
  } else if (mode) {
    if (agentInput) {
      if (agentInput.value === MANOTR_AGENT_URL) agentInput.value = "";
      agentInput.readOnly = false;
      agentInput.removeAttribute("readonly");  // Explicitly remove the readonly attribute
      agentInput.style.background = "#ffffff";  // Set to white
      agentInput.style.color = "#000000";       // Set to black
      agentInput.placeholder = "http://your-server:5050";
      console.log(`[updateModeVisibility] Agent input should now be editable. readonly=${agentInput.readOnly}`);
    }
    if (agentHint) agentHint.textContent = "Enter the URL where your agent server is running.";
    _hideEl(`${prefix}-manotr-url-info`);
  } else {
    if (agentInput) {
      agentInput.value = "";
      agentInput.readOnly = true;
      agentInput.setAttribute("readonly", "readonly");
      agentInput.style.background = "#f5f5f5";
      agentInput.style.color = "#aaa";
      agentInput.placeholder = "Choose a mode first…";
    }
    if (agentHint) agentHint.textContent = "Choose a mode above to set the agent URL.";
    _hideEl(`${prefix}-manotr-url-info`);
  }

  // ── Mode hints ──
  const hintEl = document.getElementById(`${prefix}-mode-hint`);
  if (hintEl) {
    if (mode === "manotr")        hintEl.textContent = "Manotr mode uses the built-in AI — no configuration needed.";
    else if (mode === "local")    hintEl.textContent = "Local mode uses locally hosted services (e.g. Ollama).";
    else if (mode === "external") hintEl.textContent = "External API mode — provide your own API keys and select providers.";
    else                          hintEl.textContent = "Select a mode to continue.";
  }

  if (mode === "manotr") {
    // Auto-select manotr for all providers
    setVal(`${prefix}-llm-provider`, "manotr");
    setVal(`${prefix}-emb-provider`, "manotr");
    setVal(`${prefix}-vec-provider`, "manotr");
    // Hide all API key/URL/model fields
    _hideEl(`${prefix}-llm-api-key-section`);
    _hideEl(`${prefix}-llm-model-section`);
    _hideEl(`${prefix}-llm-base-url-section`);
    _hideEl(`${prefix}-emb-api-key-section`);
    _hideEl(`${prefix}-emb-model-section`);
    _hideEl(`${prefix}-vec-url-section`);
    _hideEl(`${prefix}-vec-api-key-section`);
  } else if (mode === "local") {
    // Default to ollama for LLM and embedding
    setVal(`${prefix}-llm-provider`, "ollama");
    setVal(`${prefix}-emb-provider`, "ollama");
    setVal(`${prefix}-vec-provider`, "manotr");
    // Show base URL, hide API keys (local doesn't need them)
    _hideEl(`${prefix}-llm-api-key-section`);
    _showEl(`${prefix}-llm-base-url-section`);
    _hideEl(`${prefix}-emb-api-key-section`);
    _hideEl(`${prefix}-vec-url-section`);
    _hideEl(`${prefix}-vec-api-key-section`);
  } else {
    // external: show everything
    _showEl(`${prefix}-llm-api-key-section`);
    _showEl(`${prefix}-llm-base-url-section`);
    _showEl(`${prefix}-emb-api-key-section`);
    _showEl(`${prefix}-vec-url-section`);
    _showEl(`${prefix}-vec-api-key-section`);
  }

  // Also update per-provider visibility
  updateProviderVisibility(prefix);
}

/**
 * Fine-tune visibility based on individual provider selection
 */
function updateProviderVisibility(prefix) {
  const llmProvider = getVal(`${prefix}-llm-provider`);
  const embProvider = getVal(`${prefix}-emb-provider`);
  const vecProvider = getVal(`${prefix}-vec-provider`);
  const mode = getVal(`${prefix}-mode`);
  
  // LLM: hide API key for manotr/ollama; hide model for manotr
  if (mode !== "manotr") {
    if (llmProvider === "manotr") {
      _hideEl(`${prefix}-llm-api-key-section`);
      _hideEl(`${prefix}-llm-model-section`);
      _hideEl(`${prefix}-llm-base-url-section`);
    } else if (llmProvider === "ollama") {
      _hideEl(`${prefix}-llm-api-key-section`);
      _showEl(`${prefix}-llm-model-section`);
      _showEl(`${prefix}-llm-base-url-section`);
    } else {
      _showEl(`${prefix}-llm-api-key-section`);
      _showEl(`${prefix}-llm-model-section`);
      if (mode === "external") _showEl(`${prefix}-llm-base-url-section`);
    }
  }
  
  // Embedding: hide API key and model for manotr
  if (mode !== "manotr") {
    if (embProvider === "manotr") {
      _hideEl(`${prefix}-emb-api-key-section`);
      _hideEl(`${prefix}-emb-model-section`);
    } else if (embProvider === "ollama") {
      _hideEl(`${prefix}-emb-api-key-section`);
      _showEl(`${prefix}-emb-model-section`);
    } else {
      _showEl(`${prefix}-emb-api-key-section`);
      _showEl(`${prefix}-emb-model-section`);
    }
  }
  
  // VectorDB: hide URL/key for manotr
  if (mode !== "manotr") {
    if (vecProvider === "manotr") {
      _hideEl(`${prefix}-vec-url-section`);
      _hideEl(`${prefix}-vec-api-key-section`);
    } else {
      _showEl(`${prefix}-vec-url-section`);
      _showEl(`${prefix}-vec-api-key-section`);
    }
  }
}

function _hideEl(id) { const el = document.getElementById(id); if (el) el.style.display = "none"; }
function _showEl(id) { const el = document.getElementById(id); if (el) el.style.display = ""; }

// ── INIT ───────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  try {
    const tabs = await browser.tabs.query({ active: true, currentWindow: true });
    const msg  = await browser.messageDisplay.getDisplayedMessage(tabs[0].id);
    if (msg) {
      currentMessageId = msg.id;
      if (msg.folder && msg.folder.accountId) {
        currentAccountId = msg.folder.accountId;
        try {
          const accountResp = await send("getAccountEmail", { accountId: currentAccountId });
          if (accountResp && accountResp.email) {
            currentAccountEmail = accountResp.email;
            console.log(`[Popup] Current account: ${currentAccountId} (${currentAccountEmail})`);
          }
        } catch (e) {
          console.warn(`[Popup] Could not get email for account ${currentAccountId}:`, e.message);
        }
      }
    } else {
      bindEvents();
      showView("no-email-view");
      return;
    }
    bindEvents();

    // Check if user has completed onboarding; if not, show setup wizard
    try {
      const obResp = await send("checkOnboarding");
      if (!obResp.complete) {
        await initOnboarding();
        return;
      }
    } catch (e) {
      console.warn("Onboarding check failed:", e.message);
    }
    showMainMenu();
  } catch (e) {
    showError("Failed to initialise: " + e.message);
  }
});

// ── MULTI-ACCOUNT ONBOARDING ─────────────────────────────
async function initOnboarding() {
  try {
    const accountsResp = await send("getAccountsList");
    allAccounts = (accountsResp.accounts || []).filter(a => a.id);
    
    if (allAccounts.length === 0) {
      showError("No email accounts found in Thunderbird.");
      return;
    }
    
    // Resolve emails for all accounts
    for (const acc of allAccounts) {
      try {
        const emailResp = await send("getAccountEmail", { accountId: acc.id });
        if (emailResp && emailResp.email) {
          onboardingAccountEmails[acc.id] = emailResp.email;
          acc.email = emailResp.email;
        }
      } catch (e) {
        console.warn(`Could not get email for ${acc.id}:`, e.message);
      }
    }
    
    onboardingIndex = 0;
    renderOnboardingPage();
    showView("onboarding-view");
    
    // Force initial state update and add debugging
    setTimeout(() => {
      const modeSelect = document.getElementById("ob-mode");
      const agentInput = document.getElementById("ob-agent-url");
      console.log("[initOnboarding] After 100ms - Mode:", modeSelect ? modeSelect.value : "N/A");
      if (agentInput) {
        console.log("[initOnboarding] Agent input readonly:", agentInput.readOnly);
        console.log("[initOnboarding] Agent input readonly attr:", agentInput.getAttribute("readonly"));
        console.log("[initOnboarding] Agent input value:", agentInput.value);
      }
    }, 100);
  } catch (e) {
    showError("Failed to load accounts: " + e.message);
  }
}

function renderOnboardingPage() {
  const acc = allAccounts[onboardingIndex];
  if (!acc) return;
  
  const email = onboardingAccountEmails[acc.id] || acc.name || acc.id;
  
  // Update progress dots
  const progressEl = document.getElementById("ob-progress");
  if (progressEl) {
    progressEl.innerHTML = allAccounts.map((a, i) => {
      const done = i < onboardingIndex;
      const active = i === onboardingIndex;
      const color = done ? "#4caf50" : active ? "#4A86E8" : "#ccc";
      const label = onboardingAccountEmails[a.id] || a.name || `Account ${i+1}`;
      return `<div style="flex:1;text-align:center;" title="${label}">
        <div style="width:12px;height:12px;border-radius:50%;background:${color};margin:0 auto;"></div>
        <div style="font-size:10px;color:${active?'#333':'#999'};margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${i+1}/${allAccounts.length}</div>
      </div>`;
    }).join("");
  }
  
  // Update account header
  const labelEl = document.getElementById("ob-current-account-label");
  const emailEl = document.getElementById("ob-current-account-email");
  if (labelEl) labelEl.textContent = acc.name || acc.id;
  if (emailEl) emailEl.textContent = email;
  
  // Update button text
  const saveBtn = document.getElementById("ob-save-btn");
  const skipBtn = document.getElementById("ob-skip-btn");
  const isLast = onboardingIndex >= allAccounts.length - 1;
  if (saveBtn) saveBtn.textContent = isLast ? "🚀 Finish Setup" : "💾 Save & Next Account";
  if (skipBtn) {
    skipBtn.classList.toggle("hidden", allAccounts.length <= 1);
    skipBtn.textContent = isLast ? "⏭️ Skip & Finish" : "⏭️ Skip This Account";
  }
  
  // Reset form to defaults for this account
  setVal("ob-agent-url", "");
  setVal("ob-mode", "");
  setVal("ob-llm-provider", "manotr");
  setVal("ob-llm-api-key", "");
  setVal("ob-llm-model", "gpt-4o-mini");
  setVal("ob-llm-base-url", "");
  setVal("ob-emb-provider", "manotr");
  setVal("ob-emb-api-key", "");
  setVal("ob-emb-model", "text-embedding-3-small");
  setVal("ob-vec-provider", "manotr");
  setVal("ob-vec-url", "");
  setVal("ob-vec-api-key", "");
  setVal("ob-user-name", "");
  setVal("ob-user-position", "");
  setVal("ob-user-tone", "professional");
  setVal("ob-system-prompt", "");
  
  // Reset UI state
  hideStatus("ob-backend-status");
  hideStatus("ob-status");
  document.getElementById("ob-backend-settings-actions").classList.add("hidden");
  document.getElementById("ob-fetched-settings-preview").classList.add("hidden");
  backendSettingsLoaded = false;
  backendSettings = null;
  
  // Ensure agent URL field starts as readonly since mode is empty
  const agentInput = document.getElementById("ob-agent-url");
  if (agentInput) {
    agentInput.readOnly = true;
    agentInput.setAttribute("readonly", "readonly");
  }
  
  // Apply mode visibility (this will handle all field states)
  updateModeVisibility("ob");
}

// ── EVENT BINDING ──────────────────────────────────────
function bindEvents() {
  // No-email view
  on("no-email-settings-btn", "click", handleOpenSettings);

  // Main menu
  on("summarize-btn",      "click", handleSummarize);
  on("chat-btn",           "click", handleShowChat);
  on("draft-btn",          "click", handleDraftWithAttachments);
  on("generate-draft-btn", "click", handleGenerateDraft);
  on("index-history-btn",  "click", handleOpenHistory);
  on("settings-btn",       "click", handleOpenSettings);
  on("advanced-btn",       "click", handleOpenAdvanced);

  // Summary view
  on("draft-response-btn",   "click", handleDraftResponse);
  on("back-from-summary-btn","click", showMainMenu);

  // Draft view
  on("back-from-draft-btn",  "click", showMainMenu);

  // Chat view
  on("send-chat-btn",        "click", handleSendChat);
  on("clear-chat-btn",       "click", () => { chatHistory = []; renderChat(); });
  on("back-from-chat-btn",   "click", showMainMenu);
  on("chat-input", "keydown", e => { if (e.key === "Enter" && e.ctrlKey) handleSendChat(); });

  // Error view
  on("back-from-error-btn",  "click", showMainMenu);

  // Onboarding view - Multi-account page-by-page
  on("ob-fetch-backend-btn",  "click", handleFetchBackendSettings);
  on("ob-use-backend-btn",    "click", handleUseBackendSettings);
  on("ob-ignore-backend-btn", "click", handleIgnoreBackendSettings);
  on("ob-save-btn",           "click", handleOnboardingSave);
  on("ob-skip-btn",           "click", handleOnboardingSkip);
  on("ob-mode",               "change", () => {
    console.log("[Popup] Mode changed to:", getVal("ob-mode"));
    updateModeVisibility("ob");
  });
  on("ob-mode",               "input", () => {
    console.log("[Popup] Mode input to:", getVal("ob-mode"));
    updateModeVisibility("ob");
  });
  on("ob-llm-provider",       "change", () => updateProviderVisibility("ob"));
  on("ob-emb-provider",       "change", () => updateProviderVisibility("ob"));
  on("ob-vec-provider",       "change", () => updateProviderVisibility("ob"));

  // Settings view
  on("save-settings-btn",    "click", handleSaveSettings);
  on("sync-settings-btn",    "click", handleSyncSettings);
  on("reset-settings-btn",   "click", handleResetSettings);
  on("back-from-settings-btn","click", showMainMenu);
  on("s-mode",                "change", () => updateModeVisibility("s"));
  on("s-llm-provider",        "change", () => updateProviderVisibility("s"));
  on("s-emb-provider",        "change", () => updateProviderVisibility("s"));
  on("s-vec-provider",        "change", () => updateProviderVisibility("s"));
  on("s-account-select",      "change", handleSettingsAccountChange);
  on("s-fetch-backend-btn",   "click", handleSettingsFetchFromServer);

  // Advanced view
  on("adv-monitor-toggle", "change", handleMonitorToggle);
  on("adv-add-filter-btn",   "click", handleAddFilter);
  on("adv-save-filters-btn", "click", handleSaveFilters);
  on("adv-test-filters-btn", "click", handleTestFilters);
  on("run-bulk-btn",         "click", handleRunBulk);
  on("bulk-confirm-yes-btn", "click", handleRunBulkConfirmed);
  on("bulk-confirm-no-btn",  "click", hideBulkConfirm);
  on("bulk-status-btn",      "click", handleOpenBulkStatus);
  on("back-from-advanced-btn","click", showMainMenu);

  // Bulk status view
  on("bs-refresh-btn",       "click", handleRefreshBulkStatus);
  on("bs-cancel-btn",        "click", handleCancelBulk);
  on("bs-cancel-ok-btn",     "click", handleCancelBulkOk);
  on("back-from-bulk-btn",   "click", handleOpenHistory);

  // History view
  on("back-from-history-btn", "click", showMainMenu);
  on("history-account-select", "change", () => {
    const accountId = getVal("history-account-select");
    console.log(`[OpenMailBot] Account selected: ${accountId}`);
  });
}

function on(id, event, fn) {
  const el = document.getElementById(id);
  if (el) el.addEventListener(event, fn);
}

// Helper function to populate account selector
function _populateAccountSelector(accounts, currentId) {
  const select = document.getElementById("history-account-select");
  if (!select) return;
  
  select.innerHTML = "";
  if (!accounts || accounts.length === 0) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No accounts found";
    select.appendChild(option);
    return;
  }
  
  for (const acc of accounts) {
    const option = document.createElement("option");
    option.value = acc.id;
    option.textContent = `${acc.name || acc.id}${acc.email ? ` (${acc.email})` : ""}`;
    if (acc.id === currentId) option.selected = true;
    select.appendChild(option);
  }
}

/**
 * Render a settings preview (key-value pairs) in a target element
 */
function _renderSettingsPreview(containerId, settings) {
  const container = document.getElementById(containerId);
  if (!container) return;
  
  const fieldLabels = {
    agent_url: "Agent URL", backend_url: "Agent URL",
    mode: "Mode", llm_provider: "LLM Provider", llm_model: "LLM Model",
    llm_base_url: "LLM Base URL", embedding_provider: "Embedding Provider",
    embedding_model: "Embedding Model", vector_provider: "Vector DB Provider",
    vector_url: "Vector DB URL", user_name: "Name", user_position: "Position",
    user_tone: "Tone", system_prompt: "Custom Instructions"
  };
  
  // Don't show API keys in preview
  const skipKeys = ["llm_api_key", "embedding_api_key", "vector_api_key"];
  
  let html = '<table style="width:100%;border-collapse:collapse;">';
  for (const [key, val] of Object.entries(settings)) {
    if (skipKeys.includes(key) || !val) continue;
    const label = fieldLabels[key] || key;
    const displayVal = typeof val === "string" && val.length > 40 ? val.substring(0, 40) + "…" : val;
    html += `<tr><td style="padding:2px 6px;font-weight:600;color:#333;white-space:nowrap;">${escHtml(label)}</td><td style="padding:2px 6px;color:#555;">${escHtml(String(displayVal))}</td></tr>`;
  }
  html += "</table>";
  container.innerHTML = html;
}

/**
 * Fetch and display settings from server for onboarding
 */
async function handleFetchBackendSettings() {
  const acc = allAccounts[onboardingIndex];
  if (!acc) return;
  
  const userEmail = onboardingAccountEmails[acc.id];
  if (!userEmail) {
    setStatus("ob-backend-status", "❌ Could not resolve account email", true);
    return;
  }
  
  try {
    setStatus("ob-backend-status", "🔍 Checking server...", false);
    const fetchResp = await send("fetchSettingsFromBackend", { userEmail });
    if (fetchResp.success && fetchResp.settings) {
      backendSettings = fetchResp.settings;
      backendSettingsLoaded = true;
      setStatus("ob-backend-status", "✅ Found settings on server!", false);
      
      // Show settings preview
      _renderSettingsPreview("ob-fetched-settings-list", fetchResp.settings);
      document.getElementById("ob-fetched-settings-preview").classList.remove("hidden");
      document.getElementById("ob-backend-settings-actions").classList.remove("hidden");
    } else {
      setStatus("ob-backend-status",
        `ℹ️ ${fetchResp.error || "No settings found on server. Configure manually."}`, false);
      document.getElementById("ob-fetched-settings-preview").classList.add("hidden");
      document.getElementById("ob-backend-settings-actions").classList.add("hidden");
    }
  } catch (e) {
    setStatus("ob-backend-status", `❌ Error: ${e.message}`, true);
  }
}

/**
 * Use the backend settings in the onboarding form
 */
function handleUseBackendSettings() {
  if (!backendSettings) return;
  
  // Map both old (backend_url) and new (agent_url) field names
  const agentUrl = backendSettings.agent_url || backendSettings.backend_url || "http://omb.manotr.com";
  // Map old "inbuilt" to "manotr"
  const mapMode = (v) => v === "inbuilt" ? "manotr" : (v || "manotr");
  
  setVal("ob-agent-url",     agentUrl);
  setVal("ob-mode",          mapMode(backendSettings.mode));
  setVal("ob-llm-provider",  mapMode(backendSettings.llm_provider));
  setVal("ob-llm-api-key",   backendSettings.llm_api_key         || "");
  setVal("ob-llm-model",     backendSettings.llm_model           || "gpt-4o-mini");
  setVal("ob-llm-base-url",  backendSettings.llm_base_url        || "");
  setVal("ob-emb-provider",  mapMode(backendSettings.embedding_provider));
  setVal("ob-emb-api-key",   backendSettings.embedding_api_key   || "");
  setVal("ob-emb-model",     backendSettings.embedding_model     || "text-embedding-3-small");
  setVal("ob-vec-provider",  mapMode(backendSettings.vector_provider));
  setVal("ob-vec-url",       backendSettings.vector_url          || "");
  setVal("ob-vec-api-key",   backendSettings.vector_api_key      || "");
  setVal("ob-user-name",     backendSettings.user_name           || "");
  setVal("ob-user-position", backendSettings.user_position       || "");
  setVal("ob-user-tone",     backendSettings.user_tone           || "professional");
  setVal("ob-system-prompt", backendSettings.system_prompt       || "");
  
  updateModeVisibility("ob");
  setStatus("ob-backend-status", "✅ Settings loaded into form!", false);
}

/**
 * Ignore backend settings and configure manually
 */
function handleIgnoreBackendSettings() {
  backendSettingsLoaded = false;
  backendSettings = null;
  document.getElementById("ob-backend-settings-actions").classList.add("hidden");
  document.getElementById("ob-fetched-settings-preview").classList.add("hidden");
  setStatus("ob-backend-status", "ℹ️ Configuring manually...", false);
}

// ── VIEW CONTROL ────────────────────────────────────────
function showView(id) {
  ALL_VIEWS.forEach(v => document.getElementById(v).classList.add("hidden"));
  document.getElementById(id).classList.remove("hidden");
}
function showMainMenu() { showView("main-menu"); }
function showLoading(txt = "Processing…") {
  document.getElementById("loading-text").textContent = txt;
  showView("loading");
}
function showError(msg) {
  document.getElementById("error-message").textContent = msg;
  showView("error-view");
}
function setStatus(id, msg, isError = false) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = msg;
  el.classList.remove("hidden");
  el.classList.toggle("error", isError);
}
function hideStatus(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add("hidden");
}

// ── SUMMARIZE ──────────────────────────────────────────
async function handleSummarize() {
  try {
    showLoading("Analysing thread…");
    const resp = await send("summarizeThread", { messageId: currentMessageId, accountId: currentAccountId, userEmail: currentAccountEmail });
    currentSummary = resp.summary || "";
    document.getElementById("summary-content").innerHTML = mdToHtml(currentSummary);
    showView("summary-view");
  } catch (e) {
    showError("Summary failed: " + e.message);
  }
}

// ── DRAFT RESPONSE (from summary) ─────────────────────
async function handleDraftResponse() {
  try {
    showLoading("Creating draft…");
    const resp = await send("createDraft", { messageId: currentMessageId, summary: currentSummary, accountId: currentAccountId, userEmail: currentAccountEmail });
    if (resp.success) {
      document.getElementById("draft-message").innerHTML =
        "✅ <strong>Draft opened in compose window.</strong>";
      document.getElementById("draft-processing").innerHTML = "";
      const preview = (resp.draftContent || "").substring(0, 800);
      document.getElementById("draft-preview").textContent =
        preview + ((resp.draftContent||"").length > 800 ? "\n\n…" : "");
      showView("draft-view");
    }
  } catch (e) {
    showError("Draft failed: " + e.message);
  }
}

// ── GENERATE DRAFT (simple, no attachments) ───────────────────
async function handleGenerateDraft() {
  try {
    showLoading("Generating draft…");
    const resp = await send("simpleDraft", { messageId: currentMessageId, accountId: currentAccountId, userEmail: currentAccountEmail });
    if (resp.success) {
      document.getElementById("draft-message").innerHTML =
        "✅ <strong>Draft opened in compose window.</strong>";
      document.getElementById("draft-processing").innerHTML =
        "ℹ️ Generated from email thread (no attachments).";
      const preview = (resp.draftContent || "").substring(0, 800);
      document.getElementById("draft-preview").textContent =
        preview + ((resp.draftContent||"").length > 800 ? "\n\n…" : "");
      showView("draft-view");
    }
  } catch (e) {
    showError("Draft failed: " + e.message);
  }
}

// ── DRAFT WITH ATTACHMENTS ─────────────────────────────
async function handleDraftWithAttachments() {
  try {
    showLoading("Creating draft + indexing attachments…");
    const resp = await send("draftWithAttachments", { messageId: currentMessageId, accountId: currentAccountId, userEmail: currentAccountEmail });
    const pi = resp.processingInfo || {};
    document.getElementById("draft-message").innerHTML =
      "✅ <strong>Draft opened in compose window.</strong>";
    document.getElementById("draft-processing").innerHTML =
      resp.attachmentCount > 0
        ? `📎 ${resp.attachmentCount} attachment(s) indexed.`
        : "ℹ️ No attachments found.";
    const preview = (resp.draftContent || "").substring(0, 800);
    document.getElementById("draft-preview").textContent =
      preview + ((resp.draftContent||"").length > 800 ? "\n\n…" : "");
    showView("draft-view");
  } catch (e) {
    showError("Draft failed: " + e.message);
  }
}

// ── CHAT ───────────────────────────────────────────────
async function handleShowChat() {
  chatHistory = [];
  renderChat();
  showView("chat-view");
}

function renderChat() {
  const box = document.getElementById("chat-history");
  box.innerHTML = "";
  const exQ = document.getElementById("example-questions");
  if (chatHistory.length === 0) {
    exQ.classList.remove("hidden");
    return;
  }
  exQ.classList.add("hidden");
  for (const m of chatHistory) {
    const d = document.createElement("div");
    d.className = "chat-message " + m.role;
    d.innerHTML = `<strong>${m.role === "user" ? "You:" : "AI:"}</strong>` +
      (m.role === "assistant" ? mdToHtml(m.content) : escHtml(m.content));
    box.appendChild(d);
  }
  box.scrollTop = box.scrollHeight;
  document.getElementById("chat-input").value = "";
}

async function handleSendChat() {
  const inp = document.getElementById("chat-input");
  const q   = inp.value.trim();
  if (!q) return;
  chatHistory.push({ role: "user", content: q });
  inp.value = "";
  renderChat();
  showLoading("Thinking…");
  try {
    const resp = await send("chatWithThread", { 
      messageId: currentMessageId, 
      question: q, 
      accountId: currentAccountId, 
      userEmail: currentAccountEmail 
    });
    chatHistory.push({ role: "assistant", content: resp.answer || "(no answer)" });
    renderChat();
    showView("chat-view");
  } catch (e) {
    chatHistory.pop();
    showError("Chat error: " + e.message);
  }
}

// ── ONBOARDING ─────────────────────────────────────────
/**
 * Validate mandatory user profile fields
 */
function _validateUserProfile(prefix) {
  let valid = true;
  const nameVal = getVal(`${prefix}-user-name`).trim();
  const posVal  = getVal(`${prefix}-user-position`).trim();
  
  const nameErr = document.getElementById(`${prefix}-user-name-error`);
  const posErr  = document.getElementById(`${prefix}-user-position-error`);
  
  if (!nameVal) {
    if (nameErr) nameErr.style.display = "";
    valid = false;
  } else {
    if (nameErr) nameErr.style.display = "none";
  }
  
  if (!posVal) {
    if (posErr) posErr.style.display = "";
    valid = false;
  } else {
    if (posErr) posErr.style.display = "none";
  }
  
  return valid;
}

async function handleOnboardingSave() {
  // Validate mode is chosen
  if (!getVal("ob-mode")) {
    setStatus("ob-status", "❌ Please select a Mode.", true);
    return;
  }
  // Validate agent URL for non-Manotr modes
  if (getVal("ob-mode") !== "manotr" && !getVal("ob-agent-url").trim()) {
    setStatus("ob-status", "❌ Please enter the Agent Running URL.", true);
    return;
  }
  // Validate mandatory fields
  if (!_validateUserProfile("ob")) {
    setStatus("ob-status", "❌ Please fill in Name and Position (required fields).", true);
    return;
  }

  const btn = document.getElementById("ob-save-btn");
  if (btn) { btn.disabled = true; btn.textContent = "Saving…"; }

  const acc = allAccounts[onboardingIndex];
  const userEmail = onboardingAccountEmails[acc.id];

  const settings = {
    agent_url          : getVal("ob-agent-url") || MANOTR_AGENT_URL,
    mode               : getVal("ob-mode"),
    llm_provider       : getVal("ob-llm-provider")       || "manotr",
    llm_api_key        : getVal("ob-llm-api-key"),
    llm_model          : getVal("ob-llm-model")          || "gpt-4o-mini",
    llm_base_url       : getVal("ob-llm-base-url"),
    embedding_provider : getVal("ob-emb-provider")       || "manotr",
    embedding_api_key  : getVal("ob-emb-api-key"),
    embedding_model    : getVal("ob-emb-model")          || "text-embedding-3-small",
    vector_provider    : getVal("ob-vec-provider")        || "manotr",
    vector_url         : getVal("ob-vec-url"),
    vector_api_key     : getVal("ob-vec-api-key"),
    user_name          : getVal("ob-user-name"),
    user_position      : getVal("ob-user-position"),
    user_tone          : getVal("ob-user-tone")          || "professional",
    system_prompt      : getVal("ob-system-prompt")
  };

  try {
    await send("completeOnboarding", { settings, accountId: acc.id, userEmail });
    setStatus("ob-status", `✅ Settings saved for ${userEmail}!`, false);
    
    // Move to next account or finish
    if (onboardingIndex < allAccounts.length - 1) {
      onboardingIndex++;
      if (btn) { btn.disabled = false; }
      setTimeout(() => renderOnboardingPage(), 600);
    } else {
      // All accounts configured — finish onboarding
      setStatus("ob-status", "✅ All accounts configured! Starting…", false);
      setTimeout(showMainMenu, 900);
    }
  } catch (e) {
    setStatus("ob-status", "❌ Failed: " + e.message, true);
    if (btn) { btn.disabled = false; btn.textContent = "💾 Save & Next Account"; }
  }
}

async function handleOnboardingSkip() {
  // Skip this account, move to next
  if (onboardingIndex < allAccounts.length - 1) {
    onboardingIndex++;
    renderOnboardingPage();
  } else {
    // Last account skipped — finish
    showMainMenu();
  }
}

// ── SETTINGS ───────────────────────────────────────────

/**
 * Handle account change in settings — reload settings for chosen account
 */
async function handleSettingsAccountChange() {
  const accountId = getVal("s-account-select");
  if (!accountId) return;
  
  try {
    const emailResp = await send("getAccountEmail", { accountId });
    if (emailResp && emailResp.email) {
      currentAccountId = accountId;
      currentAccountEmail = emailResp.email;
      // Reload settings for this account
      const resp = await send("loadSettings", { accountId, userEmail: currentAccountEmail });
      _populateSettingsForm(resp.settings || {});
      setStatus("settings-status", `📧 Loaded settings for ${currentAccountEmail}`, false);
    }
  } catch (e) {
    setStatus("settings-status", `❌ Failed to load: ${e.message}`, true);
  }
}

/**
 * Fetch settings from server in settings view and display preview
 */
async function handleSettingsFetchFromServer() {
  if (!currentAccountEmail) {
    setStatus("settings-status", "❌ No account email resolved", true);
    return;
  }
  try {
    setStatus("settings-status", "🔍 Fetching from server…", false);
    const fetchResp = await send("fetchSettingsFromBackend", { userEmail: currentAccountEmail });
    if (fetchResp.success && fetchResp.settings) {
      // Show preview
      _renderSettingsPreview("s-fetched-settings-list", fetchResp.settings);
      document.getElementById("s-fetched-settings-preview").classList.remove("hidden");
      // Also populate the form
      _populateSettingsForm(fetchResp.settings);
      setStatus("settings-status", "✅ Settings loaded from server!", false);
    } else {
      document.getElementById("s-fetched-settings-preview").classList.add("hidden");
      setStatus("settings-status", `ℹ️ ${fetchResp.error || "No settings found on server."}`, false);
    }
  } catch (e) {
    setStatus("settings-status", `❌ Error: ${e.message}`, true);
  }
}

function _populateSettingsForm(s) {
  const mapMode = (v) => v === "inbuilt" ? "manotr" : (v || "manotr");
  setVal("s-agent-url",    s.agent_url || s.backend_url || "");
  // mode: blank if not set (so user must choose), map legacy "inbuilt" → "manotr"
  setVal("s-mode",         s.mode === "inbuilt" ? "manotr" : (s.mode || ""));
  setVal("s-llm-provider", mapMode(s.llm_provider));
  setVal("s-llm-api-key",  s.llm_api_key         || "");
  setVal("s-llm-model",    s.llm_model           || "gpt-4o-mini");
  setVal("s-llm-base-url", s.llm_base_url        || "");
  setVal("s-emb-provider", mapMode(s.embedding_provider));
  setVal("s-emb-api-key",  s.embedding_api_key   || "");
  setVal("s-emb-model",    s.embedding_model     || "text-embedding-3-small");
  setVal("s-vec-provider", mapMode(s.vector_provider));
  setVal("s-vec-url",      s.vector_url          || "");
  setVal("s-vec-api-key",  s.vector_api_key      || "");
  setVal("s-user-name",    s.user_name           || "");
  setVal("s-user-position",s.user_position       || "");
  setVal("s-user-tone",    s.user_tone           || "professional");
  setVal("s-system-prompt",s.system_prompt       || "");
  updateModeVisibility("s");
}

async function handleOpenSettings() {
  try {
    showLoading("Loading settings…");
    
    // Load accounts for the selector
    const accountsResp = await send("getAccountsList").catch(() => ({ accounts: [] }));
    const selectEl = document.getElementById("s-account-select");
    if (selectEl && accountsResp.accounts) {
      selectEl.innerHTML = "";
      for (const acc of accountsResp.accounts) {
        const option = document.createElement("option");
        option.value = acc.id;
        option.textContent = `${acc.name || acc.id}${acc.email ? ` (${acc.email})` : ""}`;
        if (acc.id === currentAccountId) option.selected = true;
        selectEl.appendChild(option);
      }
    }
    
    // Ensure we have the current account email
    let email = currentAccountEmail;
    if (!email && currentAccountId) {
      try {
        const emailResp = await send("getAccountEmail", { accountId: currentAccountId });
        if (emailResp && emailResp.email) {
          currentAccountEmail = email = emailResp.email;
        }
      } catch (e) {
        console.warn(`[Settings] Could not get email:`, e.message);
      }
    }
    
    const resp = await send("loadSettings", { accountId: currentAccountId, userEmail: email });
    _populateSettingsForm(resp.settings || {});
    hideStatus("settings-status");
    document.getElementById("s-fetched-settings-preview").classList.add("hidden");
    showView("settings-view");
  } catch (e) {
    showError("Could not load settings: " + e.message);
  }
}

async function handleSaveSettings() {
  // Validate mode
  if (!getVal("s-mode")) {
    setStatus("settings-status", "❌ Please select a Mode.", true);
    return;
  }
  // Validate agent URL for non-Manotr modes
  if (getVal("s-mode") !== "manotr" && !getVal("s-agent-url").trim()) {
    setStatus("settings-status", "❌ Please enter the Agent Running URL.", true);
    return;
  }
  // Validate user profile
  const nameVal = getVal("s-user-name").trim();
  const posVal  = getVal("s-user-position").trim();
  if (!nameVal || !posVal) {
    setStatus("settings-status", "❌ Name and Position are required.", true);
    return;
  }
  
  const settings = {
    agent_url         : getVal("s-agent-url"),
    mode              : getVal("s-mode"),
    llm_provider      : getVal("s-llm-provider"),
    llm_api_key       : getVal("s-llm-api-key"),
    llm_model         : getVal("s-llm-model"),
    llm_base_url      : getVal("s-llm-base-url"),
    embedding_provider: getVal("s-emb-provider"),
    embedding_api_key : getVal("s-emb-api-key"),
    embedding_model   : getVal("s-emb-model"),
    vector_provider   : getVal("s-vec-provider"),
    vector_url        : getVal("s-vec-url"),
    vector_api_key    : getVal("s-vec-api-key"),
    user_name         : getVal("s-user-name"),
    user_position     : getVal("s-user-position"),
    user_tone         : getVal("s-user-tone"),
    system_prompt     : getVal("s-system-prompt")
  };
  try {
    await send("saveSettings", { settings, accountId: currentAccountId, userEmail: currentAccountEmail });
    setStatus("settings-status", "✅ Settings saved.", false);
  } catch (e) {
    setStatus("settings-status", "❌ Save failed: " + e.message, true);
  }
}

async function handleSyncSettings() {
  try {
    await send("syncSettings", { accountId: currentAccountId, userEmail: currentAccountEmail });
    setStatus("settings-status", "✅ Synced to backend.", false);
  } catch (e) {
    setStatus("settings-status", "❌ Sync failed: " + e.message, true);
  }
}

async function handleResetSettings() {
  if (!confirm("Reset all settings to defaults?")) return;
  try {
    const resp = await send("resetSettings");
    const s = resp.settings || {};
    handleOpenSettings();        // reload form
    setStatus("settings-status", "✅ Settings reset to defaults.", false);
  } catch (e) {
    setStatus("settings-status", "❌ Reset failed: " + e.message, true);
  }
}

// ── HISTORY (index past emails) ──────────────────────────
async function handleOpenHistory() {
  try {
    showLoading("Loading history settings…");
    const [monthsResp, jobResp, accountsResp] = await Promise.all([
      send("getProcessMonths", { accountId: currentAccountId, userEmail: currentAccountEmail }),
      send("getBulkJobStatus", { accountId: currentAccountId, userEmail: currentAccountEmail }).catch(() => ({ state: null })),
      send("getAccountsList").catch(() => ({ accounts: [] }))  // FIX: Get account list
    ]);
    setVal("adv-months", monthsResp.months || "3");
    hideBulkConfirm();

    // FIX: Populate account selector
    _populateAccountSelector(accountsResp.accounts || [], currentAccountId);

    const isRunning = !!(jobResp.state && jobResp.state.status === "running");
    const runBtn    = document.getElementById("run-bulk-btn");
    const runningMsg = document.getElementById("history-running-msg");
    if (runBtn) {
      runBtn.disabled = isRunning;
      runBtn.title    = isRunning ? "A job is already running. Cancel it first." : "";
    }
    if (runningMsg) runningMsg.classList.toggle("hidden", !isRunning);

    showView("history-view");
  } catch (e) {
    showError("Could not load history settings: " + e.message);
  }
}

// ── ADVANCED ───────────────────────────────────
async function handleOpenAdvanced() {
  try {
    showLoading("Loading advanced settings…");
    const [filtersResp, monitorResp] = await Promise.all([
      send("getDomainFilters", { accountId: currentAccountId, userEmail: currentAccountEmail }),
      send("getMonitorEnabled", { accountId: currentAccountId, userEmail: currentAccountEmail })
    ]);
    localFilters = filtersResp.filters || [];
    renderFilterList();
    const enabled = monitorResp.enabled !== false;   // default true
    const toggle  = document.getElementById("adv-monitor-toggle");
    const label   = document.getElementById("adv-monitor-label");
    if (toggle) toggle.checked = enabled;
    if (label)  label.textContent = enabled ? "Enabled" : "Disabled";
    hideStatus("adv-filter-result");
    hideStatus("adv-monitor-status");
    showView("advanced-view");
  } catch (e) {
    showError("Could not load advanced settings: " + e.message);
  }
}

async function handleMonitorToggle() {
  const toggle  = document.getElementById("adv-monitor-toggle");
  const label   = document.getElementById("adv-monitor-label");
  const enabled = toggle ? toggle.checked : true;
  try {
    await send("setMonitorEnabled", { enabled, accountId: currentAccountId, userEmail: currentAccountEmail });
    if (label) label.textContent = enabled ? "Enabled" : "Disabled";
    setStatus("adv-monitor-status",
      enabled ? "✅ Email monitor started." : "⛔ Email monitor stopped.", false);
  } catch (e) {
    setStatus("adv-monitor-status", "❌ Failed: " + e.message, true);
    // Revert toggle on failure
    if (toggle) toggle.checked = !enabled;
    if (label)  label.textContent = !enabled ? "Enabled" : "Disabled";
  }
}

function renderFilterList() {
  const el = document.getElementById("adv-filter-list");
  el.innerHTML = "";
  if (!localFilters.length) {
    el.innerHTML = '<span style="font-size:12px;color:#777">No filters added yet.</span>';
    return;
  }
  for (const f of localFilters) {
    const tag = document.createElement("span");
    tag.className = "filter-tag";
    tag.innerHTML = `${escHtml(f)}<button class="remove-filter" title="Remove">&times;</button>`;
    tag.querySelector(".remove-filter").addEventListener("click", () => {
      localFilters = localFilters.filter(x => x !== f);
      renderFilterList();
    });
    el.appendChild(tag);
  }
}

function handleAddFilter() {
  const inp = document.getElementById("adv-filter-input");
  const v   = inp.value.trim().toLowerCase();
  if (!v) return;
  if (!localFilters.includes(v)) { localFilters.push(v); renderFilterList(); }
  inp.value = "";
}

async function handleSaveFilters() {
  try {
    await send("saveDomainFilters", { filters: localFilters, accountId: currentAccountId, userEmail: currentAccountEmail });
    await send("saveProcessMonths", { months: getVal("adv-months"), accountId: currentAccountId, userEmail: currentAccountEmail });
    setStatus("adv-filter-result", "✅ Filters & months saved.", false);
  } catch (e) {
    setStatus("adv-filter-result", "❌ Save failed: " + e.message, true);
  }
}

async function handleTestFilters() {
  try {
    setStatus("adv-filter-result", "Testing…", false);
    const resp = await send("testDomainFilters", { accountId: currentAccountId, userEmail: currentAccountEmail });
    if (resp.noFilters) {
      setStatus("adv-filter-result", "ℹ️ No filters configured.", false);
      return;
    }
    let msg = `🧪 Scanned ${resp.threadsScanned||0} messages — ` +
      `${resp.filtered} filtered, ${resp.allowed} allowed.`;
    if (resp.examples && resp.examples.length) {
      msg += "\n" + resp.examples.join("\n");
    }
    setStatus("adv-filter-result", msg, false);
  } catch (e) {
    setStatus("adv-filter-result", "❌ Test failed: " + e.message, true);
  }
}

// ── BULK PROCESSING ────────────────────────────────────
function hideBulkConfirm() {
  const box = document.getElementById("bulk-confirm-box");
  if (box) box.classList.add("hidden");
}

function handleRunBulk() {
  // native confirm() is silently blocked in extension popups — use inline panel instead
  const months = getVal("adv-months");
  const monthLabel = months === "10days" ? "10 days" :
                     months === "1" ? "1 month" :
                     months === "12" ? "1 year" :
                     months === "24" ? "2 years" : `${months} months`;
  const box = document.getElementById("bulk-confirm-box");
  const msg = document.getElementById("bulk-confirm-msg");
  if (msg) msg.textContent = `Index emails from the last ${monthLabel}? This may take several minutes.`;
  if (box) box.classList.remove("hidden");
}

async function handleRunBulkConfirmed() {
  hideBulkConfirm();
  const months = getVal("adv-months");
  const accountId = getVal("history-account-select");  // FIX: Get selected account
  try {
    // Save months & filters first
    await send("saveProcessMonths", { months, accountId: currentAccountId, userEmail: currentAccountEmail });
    await send("saveDomainFilters", { filters: localFilters, accountId: currentAccountId, userEmail: currentAccountEmail });
    showLoading("Starting bulk indexing…");
    // FIX: Pass accountId to bulk process
    await send("runBulkProcess", { months, accountId: accountId || currentAccountId, userEmail: currentAccountEmail });
    handleOpenBulkStatus();
  } catch (e) {
    showError("Bulk process failed to start: " + e.message);
  }
}

async function handleOpenBulkStatus() {
  showView("bulk-status-view");
  await handleRefreshBulkStatus();
}

async function handleRefreshBulkStatus() {
  const refreshBtn    = document.getElementById("bs-refresh-btn");
  const refreshStatus = document.getElementById("bs-refresh-status");
  if (refreshBtn) { refreshBtn.disabled = true; refreshBtn.textContent = "Refreshing…"; }
  if (refreshStatus) {
    refreshStatus.textContent = "⏳ Refreshing…";
    refreshStatus.classList.remove("hidden", "error");
  }
  try {
    const resp  = await send("getBulkJobStatus", { accountId: currentAccountId, userEmail: currentAccountEmail });
    const state = resp.state;
    if (!state) {
      setText("bs-status",   "No job running");
      setText("bs-range",    "—");
      setText("bs-labeled",  "—");
      setText("bs-skipped",  "—");
      setText("bs-filtered", "—");
      setText("bs-errors",   "—");
    } else {
      const st = state.stats || {};
      let statusTxt = state.status || "unknown";
      if (statusTxt === "running")      statusTxt = "⏳ Running\u2026";
      else if (statusTxt === "done")        statusTxt = "✅ Done";
      else if (statusTxt === "done_limit") statusTxt = "✅ Done (limit reached — run again to continue)";
      else if (statusTxt === "cancelled")  statusTxt = "⛔ Cancelled";
      else if (statusTxt === "error")      statusTxt = "❌ Error: " + (state.error || "");

      setText("bs-status",   statusTxt);
      setText("bs-range",    `${state.afterStr || "?"} → ${state.beforeStr || "?"}`);
      setText("bs-labeled",  st.labeled    || 0);
      setText("bs-skipped",  st.skipped    || 0);
      setText("bs-filtered", st.filtered   || 0);
      setText("bs-errors",   st.errors     || 0);

      const total = (st.labeled || 0) + (st.errors || 0);
      const wrap  = document.getElementById("bs-progress-wrap");
      const bar   = document.getElementById("bs-progress-bar");
      if (total > 0 && state.status === "running") {
        wrap.classList.remove("hidden");
        const pct = Math.min(100, (state.offset || 0) / total * 100);
        bar.style.width = pct + "%";
      } else {
        wrap.classList.add("hidden");
      }
    }
    const time = new Date().toLocaleTimeString();
    if (refreshStatus) refreshStatus.textContent = `✅ Refreshed at ${time}`;
  } catch (e) {
    console.error("Bulk status error:", e);
    if (refreshStatus) {
      refreshStatus.textContent = "❌ Refresh failed. Please try again.";
      refreshStatus.classList.add("error");
    }
  } finally {
    if (refreshBtn) { refreshBtn.disabled = false; refreshBtn.textContent = "🔄 Refresh"; }
  }
}

async function handleCancelBulk() {
  try {
    const btn = document.getElementById("bs-cancel-btn");
    if (btn) { btn.disabled = true; btn.textContent = "Cancelling…"; }
    await send("cancelBulkJob", { accountId: currentAccountId, userEmail: currentAccountEmail });
    // Show confirmation banner instead of silently refreshing
    const banner = document.getElementById("bs-cancel-confirm");
    if (banner) banner.classList.remove("hidden");
    // Also refresh the status row so Status changes to "cancelled"
    setTimeout(handleRefreshBulkStatus, 800);
  } catch (e) {
    console.error("Cancel error:", e);
    const btn = document.getElementById("bs-cancel-btn");
    if (btn) { btn.disabled = false; btn.textContent = "⛔ Cancel"; }
  }
}

function handleCancelBulkOk() {
  const banner = document.getElementById("bs-cancel-confirm");
  if (banner) banner.classList.add("hidden");
  const btn = document.getElementById("bs-cancel-btn");
  if (btn) { btn.disabled = false; btn.textContent = "⛔ Cancel"; }
}

// ── HELPERS ────────────────────────────────────────────
async function send(action, data) {
  const resp = await browser.runtime.sendMessage({ action, data });
  if (resp && resp.error) throw new Error(resp.error);
  return resp;
}

function setVal(id, val) {
  const el = document.getElementById(id);
  if (el) el.value = val;
}
function getVal(id) {
  const el = document.getElementById(id);
  return el ? el.value : "";
}
function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function escHtml(t) {
  const d = document.createElement("div");
  d.textContent = t;
  return d.innerHTML;
}

function mdToHtml(text) {
  if (!text) return "";
  text = text.replace(/\n/g, "<br>");
  text = text.replace(/####\s+(.*?)(<br>|$)/g, "<br><strong>$1</strong><br>");
  text = text.replace(/###\s+(.*?)(<br>|$)/g,  "<br><strong>$1</strong><br>");
  text = text.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  text = text.replace(/(?:<br>)---(?:<br>)/g, "<br>━━━━━━━━━━<br>");
  text = text.replace(/(<br>)- (.*?)(?=<br>|$)/g, "$1• $2");
  text = text.replace(/(<br>){3,}/g, "<br><br>");
  return text;
}


