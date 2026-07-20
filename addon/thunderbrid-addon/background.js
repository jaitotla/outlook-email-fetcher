/**
 * OpenMailBot — Thunderbird Add-on
 * background.js — Full-feature background service worker
 *
 * Feature parity with gmail_summariser.gs:
 *  • Summarize thread (full thread, not just current message)
 *  • Chat with thread (RAG)
 *  • Draft with attachments (pipeline API + job polling)
 *  • Create draft response from summary
 *  • Settings management (local + backend sync / reset / fetch)
 *  • Historical bulk email indexing (batch, cancellable, status tracking)
 *  • Domain / email privacy filters
 *  • Bulk-job progress & cancellation UI
 */

"use strict";

// ─────────────────────────────────────────────────────────────────────────────
// CONSTANTS & DEFAULTS
// ─────────────────────────────────────────────────────────────────────────────

const DEFAULT_FLASK_URL  = "http://m15.lsdiedb39c.pagekite.me/";
let   ALLOWED_EXTENSIONS = [".pdf", ".csv", ".pptx", ".ppt", ".xlsx", ".xls", ".docx", ".doc"];

// ─── BACKGROUND EMAIL MONITOR CONSTANTS ──────────────────────────────────────
const MONITOR_ALARM_NAME          = "openmailbot-monitor";
const MONITOR_INTERVAL_MINS       = 1;       // check every minute (mirrors GAS CONFIG.CHECK_INTERVAL_MINUTES)
const MONITOR_LAST_CHECK_KEY      = "monitor_last_check_time";
const MONITOR_PROCESSED_KEY       = "monitor_processed_ids";
const MONITOR_MAX_IDS             = 5000;    // ring-buffer cap for processed-IDs list (FIX: increased from 100 to 5000 to avoid re-processing old emails after restart)
const OFFLINE_QUEUE_KEY           = "monitor_offline_queue"; // messages queued while offline
const OFFLINE_QUEUE_MAX_AGE_MS    = 7 * 24 * 60 * 60 * 1000; // 7 days (cleanup old offline entries)
const MONITOR_STARTUP_CATCHUP_HRS = 24;     // hours to look back when no stored lastCheck (first load / storage cleared)
const MONITOR_MAX_INACTIVITY_HRS  = 12;     // 12-hour inactivity cap: if user hasn't checked in 12+ hours, only process last 12 hours to avoid huge backlog
const STORAGE_CLEANUP_INTERVAL_MS = 6 * 60 * 60 * 1000; // cleanup every 6 hours

// ─── MONITOR CONCURRENCY CONTROL ──────────────────────────────────────────────
let _monitorRunning = false; // FIX: prevent concurrent monitorNewEmails() calls on startup

// ─── THUNDERBIRD LABEL COLORS (mirrors backend _GMAIL_LABEL_COLORS) ───────────
// Key  = lowercase label name (used as Thunderbird tag key)
// Value = hex background color
const THUNDERBIRD_LABEL_COLORS = {
  "response"      : "#4A86E8",
  "fyi"           : "#16A766",
  "notification"  : "#B7B7B7",
  "meeting"       : "#9900FF",
  "awaiting reply": "#FFFF00",
  "awaiting_reply": "#FFFF00",
  "escalation"    : "#CC0000",
  "hotels"        : "#FF9900",
  "airline"       : "#7F6000",
  "airlines"      : "#7F6000",
  "travel"        : "#274E13",
  "restaurant"    : "#FF9900",
  "booking"       : "#4A86E8",
  "bank"          : "#16A766",
  "recruitment"   : "#274E13"
};

// ─── LABEL MAPPING SYSTEM (Backend Labels → Thunderbird Tags) ─────────────────
// Hard-coded mapping replaces fuzzy similarity matching for predictable label assignment

let _labelMappingInitialized = false;

/**
 * Initialize label mapping (LEGACY - using hard-coded mapping instead)
 * Previously did similarity matching; now just logs available tags for reference.
 */
async function _initializeLabelMapping() {
  if (_labelMappingInitialized) return;
  
  try {
    const existingTags = await browser.messages.tags.list();
    console.log(`[OpenMailBot][LabelMapping] Available Thunderbird tags (${existingTags.length}):`);
    existingTags.forEach(tag => {
      console.log(`  • ${tag.key}: ${tag.tag} (color: ${tag.color})`);
    });
    console.log(`[OpenMailBot][LabelMapping] Using HARD-CODED mapping (see HARD_CODED_LABEL_MAPPING constant)`);
    _labelMappingInitialized = true;
  } catch (e) {
    console.error(`[OpenMailBot][LabelMapping] ❌ Failed to list tags: ${e.message}`);
  }
}

/**
 * HARD-CODED LABEL MAPPING: Backend Labels → Thunderbird Tag Keys
 * This mapping defines the exact transformation of backend labels to predefined Thunderbird tags.
 * 
 * Mapping Chart:
 * ────────────────────────────────────────────────────────────────
 * Backend Label   │ Thunderbird Key │ Thunderbird Tag Name
 * ────────────────────────────────────────────────────────────────
 * response        │ fyi             │ FYI
 * FYI             │ fyi             │ FYI
 * Notification    │ notification    │ Notification
 * meeting         │ meeting         │ Meeting
 * Escalation      │ escalation      │ Escalation
 * hotels          │ $label2         │ Work
 * airlines        │ $label2         │ Work
 * travel          │ $label2         │ Work
 * restaurant      │ $label5         │ Later
 * booking         │ $label5         │ Later
 * bank            │ label1          │ Bank
 * Insurance       │ $label1         │ Important
 * Other           │ $label4         │ To Do
 * ────────────────────────────────────────────────────────────────
 */
const HARD_CODED_LABEL_MAPPING = {
  "response": "fyi",
  "fyi": "fyi",
  "notification": "notification",
  "meeting": "meeting",
  "escalation": "escalation",
  "hotels": "$label2",
  "airlines": "$label2",
  "travel": "$label2",
  "restaurant": "$label5",
  "booking": "$label5",
  "bank": "label1",
  "insurance": "$label1",
  "other": "$label4"
};

// Set of all tag keys managed by OpenMailBot — used to remove stale labels before applying a new one
const OPENMAILBOT_MANAGED_TAGS = new Set(Object.values(HARD_CODED_LABEL_MAPPING));

/**
 * Map a backend label to an existing Thunderbird tag key using HARD-CODED mapping.
 * Returns the exact tag key from the mapping; no fuzzy matching.
 */
function _mapBackendLabelToThunderbirdKey(backendLabel) {
  if (!backendLabel) return null;
  
  // Normalize the backend label for lookup (lowercase)
  const normalizedLabel = String(backendLabel).toLowerCase().trim();
  
  // Check hard-coded mapping
  if (HARD_CODED_LABEL_MAPPING[normalizedLabel]) {
    const mappedKey = HARD_CODED_LABEL_MAPPING[normalizedLabel];
    console.log(`[OpenMailBot][LabelMapping] ✅ HARD-CODED: "${backendLabel}" → "${mappedKey}"`);
    return mappedKey;
  }
  
  // Not in mapping — use backend label as-is (will be created as new tag)
  console.log(`[OpenMailBot][LabelMapping] ⚠️  Not in mapping: "${backendLabel}" — will use as tag key`);
  return backendLabel;
}

// ─── PERFORMANCE OPTIMIZATION CACHES ────────────────────────────────────────
// These caches dramatically reduce repeated storage reads and network fetches

// Backend URL cache (1-minute TTL to keep fresh)
let _backendUrlCache = null;
let _backendUrlCacheTime = 0;
const BACKEND_URL_CACHE_TTL_MS = 1000 * 60; // 1 minute

// Settings cache (5-minute TTL per user email)
const _settingsCache = new Map(); // { userEmail -> { settings, cacheTime } }
const SETTINGS_CACHE_TTL_MS = 1000 * 60 * 5; // 5 minutes

// In-memory Set for processed IDs (O(1) instead of O(n))
let _processedIdsSet = null;
let _processedIdsLoaded = false;

// Request deduplication queue
const _requestQueue = new Map(); // { queueKey -> Promise }

// ─── CACHE HELPER FUNCTIONS ───────────────────────────────────────────────────

/**
 * Ensure processed IDs are loaded into memory as a Set for O(1) lookup
 */
async function _ensureProcessedIdsLoaded() {
  if (_processedIdsLoaded) return;
  
  try {
    const r = await browser.storage.local.get(MONITOR_PROCESSED_KEY);
    const ids = r[MONITOR_PROCESSED_KEY] || [];
    _processedIdsSet = new Set(ids);
    _processedIdsLoaded = true;
    console.log(`[Cache][PERF] Loaded ${ids.length} processed IDs into Set for O(1) lookup`);
  } catch (e) {
    console.warn("[Cache] Failed to load processed IDs:", e.message);
    _processedIdsSet = new Set();
    _processedIdsLoaded = true;
  }
}

/**
 * Invalidate settings cache for a specific user (or all if userEmail omitted)
 */
function _invalidateSettingsCache(userEmail) {
  if (userEmail) {
    _settingsCache.delete(userEmail);
    console.log(`[Cache][PERF] Invalidated settings cache for ${userEmail}`);
  } else {
    _settingsCache.clear();
    console.log("[Cache][PERF] Cleared all settings caches");
  }
}

/**
 * Invalidate backend URL cache
 */
function _invalidateBackendUrlCache() {
  _backendUrlCache = null;
  _backendUrlCacheTime = 0;
  console.log("[Cache][PERF] Invalidated backend URL cache");
}

/**
 * Queue a request to prevent duplicates from rapid clicks
 * If same queueKey is already running, return the existing promise
 */
async function _queuedRequest(queueKey, fn) {
  if (_requestQueue.has(queueKey)) {
    console.log(`[Queue][PERF] Request ${queueKey} already in-flight, deduplicating...`);
    return _requestQueue.get(queueKey);
  }

  const promise = (async () => {
    try {
      const result = await fn();
      _requestQueue.delete(queueKey);
      return result;
    } catch (e) {
      _requestQueue.delete(queueKey);
      throw e;
    }
  })();

  _requestQueue.set(queueKey, promise);
  return promise;
}

// ─── ADDON CONFIG (addon_config.json — addon-side only, never sent to server) ─

let _addonConfig = null;

// ─── MANOTR REMOTE CONFIG ────────────────────────────────────────────────────
const MANOTR_REMOTE_CONFIG_URL = "https://omb-s3.s3.us-west-2.amazonaws.com/omb_config.json";
let _manotrBackendUrl = null; // cached value so we only fetch once per session

/**
 * Fetch the backend URL from the Manotr remote S3 config.
 * Caches the result for the lifetime of the background script session.
 * Returns null if the fetch fails (caller should fall back to DEFAULT_FLASK_URL).
 */
async function _fetchManotrBackendUrl() {
  if (_manotrBackendUrl) return _manotrBackendUrl;
  try {
    const resp = await fetch(MANOTR_REMOTE_CONFIG_URL);
    if (resp.ok) {
      const config = await resp.json();
      if (config && config.backend_url) {
        _manotrBackendUrl = config.backend_url.replace(/\/$/, "");
        console.log("[OpenMailBot] Manotr backend URL from remote config:", _manotrBackendUrl);
        return _manotrBackendUrl;
      }
    }
  } catch (e) {
    console.warn("[OpenMailBot] Could not fetch Manotr remote config:", e.message);
  }
  return null;
}

/**
 * Load the bundled addon_config.json file once and cache it.
 * This is the addon-side equivalent of .env / app secrets.
 */
async function getAddonConfig() {
  if (_addonConfig) return _addonConfig;
  try {
    const url  = browser.runtime.getURL("addon_config.json");
    const resp = await fetch(url);
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    _addonConfig = await resp.json();
    // Update allowed attachment extensions from config
    if (Array.isArray(_addonConfig.allowed_attachment_extensions)) {
      ALLOWED_EXTENSIONS = _addonConfig.allowed_attachment_extensions;
    }
    console.log("[OpenMailBot] addon_config.json loaded", _addonConfig);
  } catch (e) {
    console.warn("[OpenMailBot] Could not load addon_config.json, using defaults:", e.message);
    _addonConfig = {
      domain_filters: { blocked_domains: [], blocked_addresses: [] },
      bulk_processing: { default_months: 3, batch_size: 10, max_messages_per_run: 2000, request_delay_ms: 200 },
      allowed_attachment_extensions: ALLOWED_EXTENSIONS
    };
  }
  return _addonConfig;
}

/**
 * Get the merged domain filter list:
 *   stored user filters (browser.storage.local)  UNION  config-file defaults
 * This ensures config-file blocked domains always apply even if storage is cleared.
 */
async function _getMergedDomainFilters() {
  const [storedR, cfg] = await Promise.all([
    browser.storage.local.get("domain_filters"),
    getAddonConfig()
  ]);
  const stored  = storedR.domain_filters || [];
  const cfgDoms = (cfg.domain_filters && cfg.domain_filters.blocked_domains)  || [];
  const cfgAddr = (cfg.domain_filters && cfg.domain_filters.blocked_addresses) || [];
  const merged  = [...new Set([...stored, ...cfgDoms, ...cfgAddr])];
  return merged;
}

const DEFAULT_SETTINGS = {
  agent_url                 : DEFAULT_FLASK_URL,
  mode                      : "manotr",
  llm_provider              : "manotr",
  llm_api_key               : "",
  llm_model                 : "gpt-4o-mini",
  llm_base_url              : "",
  embedding_provider        : "manotr",
  embedding_api_key         : "",
  embedding_model           : "text-embedding-3-small",
  vector_provider           : "manotr",
  vector_url                : "",
  vector_api_key            : "",
  user_name                 : "",
  user_position             : "",
  user_tone                 : "professional",
  system_prompt             : "",
  monitor_inactivity_hours  : "12"
};

/* keep a reference so other functions below can use DEFAULT_FLASK_SERVER_URL */
const DEFAULT_FLASK_SERVER_URL = DEFAULT_FLASK_URL;

// ─── SETTINGS HELPERS ──────────────────────────────────────────────────────────

/**
 * Get the email address of the current/specified account
 * Tries multiple properties to find email address
 */
async function getAccountEmail(accountId) {
  try {
    const allAccounts = await browser.accounts.list();
    console.log(`[Settings] Available accounts:`, allAccounts.map(a => ({ id: a.id, name: a.name, email: a.email, type: a.type })));
    
    let targetAccount = null;
    
    if (accountId) {
      targetAccount = allAccounts.find(a => a.id === accountId);
      if (!targetAccount) {
        console.warn(`[Settings] Account ID not found: ${accountId}`);
      }
    } else {
      // Fallback: get first mail account
      targetAccount = allAccounts.find(a => a.type !== "none");
    }
    
    if (!targetAccount) {
      console.error("[Settings] No suitable account found");
      return null;
    }
    
    // Try different email property paths
    // 1. Direct email property
    if (targetAccount.email) {
      console.log(`[Settings] Found email via .email: ${targetAccount.email}`);
      return targetAccount.email;
    }
    
    // 2. Check identities array (Thunderbird stores email in identities)
    if (targetAccount.identities && targetAccount.identities.length > 0) {
      const email = targetAccount.identities[0].email;
      if (email) {
        console.log(`[Settings] Found email via .identities[0].email: ${email}`);
        return email;
      }
    }
    
    // 3. Check defaultIdentity
    if (targetAccount.defaultIdentity && targetAccount.defaultIdentity.email) {
      const email = targetAccount.defaultIdentity.email;
      console.log(`[Settings] Found email via .defaultIdentity.email: ${email}`);
      return email;
    }
    
    // 4. Last resort: use account name/ID if it looks like an email
    if (targetAccount.name && targetAccount.name.includes("@")) {
      console.log(`[Settings] Using account name as email: ${targetAccount.name}`);
      return targetAccount.name;
    }
    
    console.error(`[Settings] Could not extract email from account:`, targetAccount);
    return null;
  } catch (e) {
    console.error("Failed to get account email:", e.message, e.stack);
    return null;
  }
}

/**
 * Settings Retrieval - Now Server-Based Only
 * All user settings are stored on the backend server.
 * The addon fetches settings on-demand using account email as user_id.
 * NO LOCAL STORAGE is used for user settings.
 */
/**
 * Get backend URL from addon config (stored locally)
 * This is the ONLY local storage usage for settings - for addon config, not user settings
 */
async function _getBackendUrlFromConfig() {
  // ⚡ PERF: Fast path — return cached if valid (1-minute TTL)
  if (_backendUrlCache && (Date.now() - _backendUrlCacheTime < BACKEND_URL_CACHE_TTL_MS)) {
    console.log("[Cache][PERF] Using cached backend URL");
    return _backendUrlCache;
  }

  try {
    const r = await browser.storage.local.get("user_settings");
    const userSettings = r.user_settings || {};
    const mode = userSettings.mode || DEFAULT_SETTINGS.mode;

    // When mode is "manotr", always resolve from the remote S3 config so the URL stays current
    if (mode === "manotr") {
      const manotrUrl = await _fetchManotrBackendUrl();
      if (manotrUrl) {
        _backendUrlCache = manotrUrl;
        _backendUrlCacheTime = Date.now();
        return manotrUrl;
      }
      // Fall through to default if remote config is unreachable
    } else {
      // For local/external modes use the URL the user explicitly configured
      const userUrl = userSettings.agent_url || userSettings.backend_url;
      if (userUrl) {
        const cleanUrl = userUrl.replace(/\/$/, "");
        _backendUrlCache = cleanUrl;
        _backendUrlCacheTime = Date.now();
        return cleanUrl;
      }
    }

    // Fall back to addon_config.json (used on first run before any settings are saved)
    const cfg = await getAddonConfig();
    // Support both agent_url (new) and backend_url (legacy)
    let fallbackUrl = null;
    if (cfg.agent_url) {
      fallbackUrl = cfg.agent_url.replace(/\/$/, "");
    } else if (cfg.backend_url) {
      fallbackUrl = cfg.backend_url.replace(/\/$/, "");
    }
    
    if (fallbackUrl) {
      _backendUrlCache = fallbackUrl;
      _backendUrlCacheTime = Date.now();
      return fallbackUrl;
    }
  } catch (e) {
    console.warn("[Settings] Could not read backend config:", e.message);
  }
  
  const defaultUrl = DEFAULT_FLASK_URL.replace(/\/$/, "");
  _backendUrlCache = defaultUrl;
  _backendUrlCacheTime = Date.now();
  return defaultUrl;
}

/**
 * REMOVED: _getSettings() - no longer reading from local storage
 * Replaced with server-based fetching via _fetchSettingsFromBackend()
 */

/**
 * REMOVED: _getSettingsForAccount() - replaced with _fetchSettingsFromBackend(userEmail)
 * All settings now come from backend server, not local storage
 */

/**
 * Fetch settings from backend by user email - ALWAYS FROM SERVER
 * Source of truth is the backend MongoDB, not local storage
 * ⚡ PERF: Settings are cached for 5 minutes to reduce network traffic
 */
async function _fetchSettingsFromBackend(userEmail) {
  if (!userEmail) {
    console.warn("[Settings] No user email provided to fetch settings");
    return Object.assign({}, DEFAULT_SETTINGS);
  }
  
  // ⚡ PERF: Fast path — return cached if valid (5-minute TTL)
  if (_settingsCache.has(userEmail)) {
    const cached = _settingsCache.get(userEmail);
    if (Date.now() - cached.cacheTime < SETTINGS_CACHE_TTL_MS) {
      console.log(`[Cache][PERF] Using cached settings for ${userEmail}`);
      return cached.settings;
    }
  }
  
  try {
    const backendUrl = await _getBackendUrlFromConfig();
    
    // Try GET first (preferred)
    console.log(`[Settings] 🔄 Fetching from backend for: ${userEmail}`);
    let resp = await fetch(`${backendUrl}/api/settings?user_id=${encodeURIComponent(userEmail)}`, {
      method: "GET",
      headers: { "Content-Type": "application/json" }
    });
    
    // If GET not allowed (405), try POST as fallback
    if (resp.status === 405) {
      console.log(`[Settings] GET returned 405, trying POST fallback...`);
      resp = await fetch(`${backendUrl}/api/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userEmail })
      });
    }
    
    if (resp.ok) {
      const data = await resp.json();
      const settings = Object.assign({}, DEFAULT_SETTINGS, data.settings || data);
      console.log(`[Settings] ✅ Got settings from backend for ${userEmail}`);
      
      // ⚡ Cache the settings
      _settingsCache.set(userEmail, { settings, cacheTime: Date.now() });
      return settings;
    } else if (resp.status === 404) {
      console.log(`[Settings] ℹ️ No settings on backend for ${userEmail}, using defaults`);
      const settings = Object.assign({}, DEFAULT_SETTINGS);
      _settingsCache.set(userEmail, { settings, cacheTime: Date.now() });
      return settings;
    } else {
      const errText = await resp.text().catch(() => "");
      console.warn(`[Settings] ⚠️ Backend error ${resp.status}: ${errText}`);
      return Object.assign({}, DEFAULT_SETTINGS);
    }
  } catch (e) {
    console.warn(`[Settings] ❌ Failed to fetch from backend: ${e.message}`);
    return Object.assign({}, DEFAULT_SETTINGS);
  }
}

async function getBackendUrl() {
  // Use config as source of truth - NO stored settings fallback
  return await _getBackendUrlFromConfig();
}

// ─── SETTINGS HANDLERS ─────────────────────────────────────────────────────────

async function handleLoadSettings({ accountId, userEmail }) {
  // Always fetch from backend using userEmail
  if (!userEmail) {
    console.warn("[Settings] No userEmail provided to loadSettings");
    return { success: true, settings: Object.assign({}, DEFAULT_SETTINGS) };
  }
  const settings = await _fetchSettingsFromBackend(userEmail);
  return { success: true, settings };
}

async function handleLoadSettingsForAccount({ accountId }) {
  // This handler is deprecated - use handleLoadSettings with userEmail instead
  console.warn("[Deprecated] handleLoadSettingsForAccount called - use userEmail instead");
  return { success: true, settings: Object.assign({}, DEFAULT_SETTINGS) };
}

async function handleSaveSettings({ settings, accountId, userEmail }) {
  if (!userEmail) {
    return { success: false, error: "User email required to save settings" };
  }
  
  const merged = Object.assign({}, DEFAULT_SETTINGS, settings);
  
  // Save ONLY to backend - this is source of truth (NO local storage)
  try {
    console.log(`[Settings] 💾 Saving to backend for: ${userEmail}`);
    await _syncSettingsToBackend(merged, userEmail);
    console.log(`[Settings] ✅ Settings saved on backend for ${userEmail}`);

    // ⚡ PERF: Invalidate caches so fresh data is fetched on next request
    _invalidateSettingsCache(userEmail);
    _invalidateBackendUrlCache();

    // Also persist agent_url locally so _getBackendUrlFromConfig() uses the user's value immediately
    if (merged.agent_url) {
      const r = await browser.storage.local.get("user_settings");
      const local = Object.assign({}, r.user_settings || {}, { agent_url: merged.agent_url });
      await _safeStorageSet({ user_settings: local }, "persist agent_url locally");
    }

    // Start background monitor now that settings are configured
    if (merged.agent_url) {
      _ensureMonitorAlarm();
      console.log("[Settings] ▶ Background monitor enabled after settings save");
    }

    return { success: true, settings: merged };
  } catch (e) {
    console.error(`[Settings] ❌ Failed to save to backend: ${e.message}`);
    return { success: false, error: e.message };
  }
}

async function handleResetSettings() {
  // Reset to defaults - no local storage persistence
  console.log("[Settings] Reset to defaults");
  return { success: true, settings: Object.assign({}, DEFAULT_SETTINGS) };
}

// ── ONBOARDING HANDLERS ────────────────────────────────────────────────────────

async function handleCheckOnboarding() {
  const r = await browser.storage.local.get("onboarding_complete");
  return { complete: !!r.onboarding_complete };
}

async function handleCompleteOnboarding({ settings, accountId, userEmail }) {
  if (!userEmail) {
    return { success: false, error: "User email required for onboarding" };
  }
  
  const merged = Object.assign({}, DEFAULT_SETTINGS, settings);
  
  // Save to backend
  try {
    console.log(`[Onboarding] 💾 Saving settings to backend for: ${userEmail}`);
    await _syncSettingsToBackend(merged, userEmail);
    console.log("[OpenMailBot][Onboarding] ✅ Settings synced to backend");

    // ⚡ PERF: Invalidate caches after onboarding so fresh data is fetched
    _invalidateSettingsCache(userEmail);
    _invalidateBackendUrlCache();

    // Also persist critical settings locally so they're immediately available
    if (merged.agent_url || merged.draft_font) {
      const r = await browser.storage.local.get("user_settings");
      const local = Object.assign({}, r.user_settings || {}, { 
        agent_url: merged.agent_url,
        draft_font: merged.draft_font || "arial"
      });
      await _safeStorageSet({ user_settings: local }, "persist agent_url and draft_font locally");
    }

    // Mark onboarding complete (persisted locally — applies globally once any account is configured)
    await _safeStorageSet({ onboarding_complete: true }, "mark onboarding complete");
    
    // Track which accounts have been configured
    const r = await browser.storage.local.get("configured_accounts");
    const configured = r.configured_accounts || [];
    if (!configured.includes(userEmail)) {
      configured.push(userEmail);
      await _safeStorageSet({ configured_accounts: configured }, "track configured account");
    }
    
    // Start background monitor now that onboarding is complete
    if (merged.agent_url) {
      _ensureMonitorAlarm();
      console.log("[Onboarding] ▶ Background monitor enabled after onboarding");
    }
    
    return { success: true };
  } catch (e) {
    console.error("[OpenMailBot][Onboarding] ❌ Backend sync failed:", e.message);
    return { success: false, error: e.message };
  }
}

async function handleSyncSettings({ accountId, userEmail, settings: passedSettings }) {
  if (!userEmail) {
    return { success: false, error: "User email required to sync settings" };
  }
  // Fetch current settings from backend and save (idempotent)
  try {
    const settings = passedSettings || await _fetchSettingsFromBackend(userEmail);
    await _syncSettingsToBackend(settings, userEmail);
    
    // Also persist draft_font locally so it's immediately available
    if (settings && settings.draft_font) {
      const r = await browser.storage.local.get("user_settings");
      const local = Object.assign({}, r.user_settings || {}, { 
        draft_font: settings.draft_font,
        agent_url: settings.agent_url || (r.user_settings?.agent_url)
      });
      await _safeStorageSet({ user_settings: local }, "persist draft_font locally");
    }
    
    return { success: true };
  } catch (e) {
    return { success: false, error: e.message };
  }
}

/**
 * Try to fetch settings from backend and return them without saving locally
 * (user can confirm before saving)
 */
async function handleFetchSettingsFromBackend({ userEmail }) {
  if (!userEmail) {
    return { success: false, error: "User email required" };
  }
  try {
    const backendSettings = await _fetchSettingsFromBackend(userEmail);
    if (backendSettings) {
      return { success: true, settings: backendSettings };
    } else {
      return { success: false, error: "No settings found on server for this account" };
    }
  } catch (e) {
    return { success: false, error: e.message };
  }
}

async function _syncSettingsToBackend(settings, userEmail) {
  if (!userEmail) {
    throw new Error("User email required to sync settings to backend");
  }
  const base = await _getBackendUrlFromConfig();
  const resp = await fetch(`${base}/api/settings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userEmail, settings })
  });
  if (!resp.ok) {
    const errText = await resp.text();
    throw new Error(`Backend ${resp.status}: ${errText}`);
  }
  return resp.json();
}

// ─── DOMAIN FILTER HANDLERS ───────────────────────────────────────────────────────

/**
 * Returns both user-saved filters AND the config-file defaults (merged, deduplicated).
 * The UI always shows the merged list so users know what's actually active.
 */
async function handleGetDomainFilters({ accountId, userEmail }) {
  // FIX: Could support per-account filters in future if needed
  const filters = await _getMergedDomainFilters();
  return { success: true, filters };
}

async function handleSaveDomainFilters({ filters, accountId, userEmail }) {
  // FIX: Save only the user-defined filters; config-file defaults are always merged at read time
  const unique = [...new Set((filters||[]).map(f=>f.toLowerCase().trim()).filter(Boolean))];
  await _safeStorageSet({ domain_filters: unique }, "save domain filters");
  return { success: true, filters: unique };
}

async function handleTestDomainFilters() {
  try {
    const filters = await _getMergedDomainFilters();
    if (!filters.length) return { success:true, filterCount:0, filtered:0, allowed:0, examples:[], noFilters:true };
    const accounts = await browser.accounts.list();
    if (!accounts.length) return { success:true, filterCount:filters.length, filtered:0, allowed:0, examples:[] };
    const inbox = _findInboxFolder(accounts[0].folders);
    if (!inbox) return { success:true, filterCount:filters.length, filtered:0, allowed:0, examples:[] };
    const page = await browser.messages.list(inbox);
    const msgs = (page.messages||[]).slice(0,20);
    let filtered=0; let allowed=0; const examples=[];
    for (const msg of msgs) {
      const block = _shouldFilterEmail(msg.author,filters)||(msg.recipients||[]).some(r=>_shouldFilterEmail(r,filters));
      if (block) { filtered++; if(examples.length<5) examples.push(`🚫 ${(msg.subject||"").substring(0,50)} (From: ${msg.author})`); }
      else allowed++;
    }
    return { success:true, filterCount:filters.length, filtered, allowed, examples, threadsScanned:msgs.length };
  } catch(e) { throw new Error("Filter test: "+e.message); }
}

function _findInboxFolder(folders) {
  if (!folders) return null;
  for (const f of folders) {
    if (f.type==="inbox") return f;
    const sub = _findInboxFolder(f.subFolders);
    if (sub) return sub;
  }
  return null;
}

function _shouldFilterEmail(address, filters) {
  if (!address||!filters||!filters.length) return false;
  const raw  = address.toLowerCase().trim();
  const m    = raw.match(/<(.+?)>/);
  const addr = m ? m[1] : raw;
  for (const f of filters) {
    const fl = f.toLowerCase().trim();
    if (!fl) continue;
    if (fl.includes("@")) { if (addr===fl) return true; }
    else { const d=addr.split("@")[1]; if(d&&d===fl) return true; }
  }
  return false;
}

// ─── BULK PROCESSING ─────────────────────────────────────────────────────────────────

// ─── MONITOR ENABLE/DISABLE ───────────────────────────────────────────────────────────────────────
const MONITOR_ENABLED_KEY = "monitor_enabled";

async function handleGetMonitorEnabled({ accountId, userEmail }) {
  // FIX: Could support per-account monitor settings in future
  const r = await browser.storage.local.get(MONITOR_ENABLED_KEY);
  // Default to true if never set
  const enabled = r[MONITOR_ENABLED_KEY] !== false;
  return { success: true, enabled };
}

async function handleSetMonitorEnabled({ enabled, accountId, userEmail }) {
  // FIX: Could support per-account monitor settings in future
  await _safeStorageSet({ [MONITOR_ENABLED_KEY]: enabled }, "set monitor enabled");
  if (enabled) {
    _ensureMonitorAlarm();
    console.log("[OpenMailBot][Monitor] ▶ Monitor ENABLED by user");
  } else {
    await browser.alarms.clear(MONITOR_ALARM_NAME);
    console.log("[OpenMailBot][Monitor] ⏹ Monitor DISABLED by user");
  }
  return { success: true, enabled };
}

async function handleSaveProcessMonths({ months, accountId, userEmail }) {
  // FIX: Could support per-account months in future if needed
  await _safeStorageSet({ process_last_n_months: months||"3" }, "save process months");
  return { success: true };
}

async function handleGetProcessMonths({ accountId, userEmail }) {
  // FIX: Could support per-account months in future if needed
  const r = await browser.storage.local.get("process_last_n_months");
  return { success: true, months: r.process_last_n_months||"3" };
}

// FIX: Get list of all mail accounts for account selector
async function handleGetAccountsList() {
  try {
    const allAccounts = await browser.accounts.list();
    const accounts = allAccounts
      .filter(a => a.type !== "none")  // Skip "Local Folders" and non-mail accounts
      .map(a => ({ id: a.id, name: a.name || a.id, email: a.email }));
    return { success: true, accounts };
  } catch (e) {
    console.error("[OpenMailBot] Failed to get accounts:", e.message);
    return { success: false, accounts: [], error: e.message };
  }
}

/**
 * Get email for a specific account
 */
async function handleGetAccountEmail({ accountId }) {
  try {
    if (!accountId) {
      return { success: false, error: "No account ID provided" };
    }
    
    const email = await getAccountEmail(accountId);
    if (email) {
      console.log(`[Settings] Successfully got email for account ${accountId}: ${email}`);
      return { success: true, email };
    } else {
      console.error(`[Settings] Could not get email for account: ${accountId}`);
      return { 
        success: false, 
        error: `Could not determine email for account ${accountId}. Check browser console for account details.`
      };
    }
  } catch (e) {
    console.error("[Settings] handleGetAccountEmail error:", e.message, e);
    return { success: false, error: e.message };
  }
}

async function handleGetBulkJobStatus({ accountId, userEmail }) {
  // FIX: Could support per-account job status in future
  const r = await browser.storage.local.get(["bulk_job_state","bulk_job_abort","bulk_job_pause"]);
  return { 
    success: true, 
    state: r.bulk_job_state||null, 
    aborted: r.bulk_job_abort===true,
    paused: r.bulk_job_pause===true
  };
}

async function handleCancelBulkJob({ accountId, userEmail }) {
  // FIX: Could support per-account bulk jobs in future
  try {
    // Cancel clears both pause and abort, so job won't resume
    await _safeStorageSet({ 
      bulk_job_abort: true,
      bulk_job_pause: false,
      bulk_job_state: null 
    }, "cancel bulk job");
  } catch (e) {
    console.warn("[BulkJob] Could not set abort flag:", e.message);
  }
  return { success: true };
}

async function handlePauseBulkJob({ accountId, userEmail }) {
  // Pause (different from cancel): preserves state for resuming later
  try {
    await _safeStorageSet({ bulk_job_pause: true }, "pause bulk job");
    console.log("[BulkJob] ⏸ Pause requested - job will save checkpoint and stop");
  } catch (e) {
    console.warn("[BulkJob] Could not set pause flag:", e.message);
  }
  return { success: true };
}

async function handleResumeBulkJob({ accountId, userEmail }) {
  // Resume from paused state
  const r = await browser.storage.local.get("bulk_job_state");
  const state = r.bulk_job_state;
  
  if (!state) {
    return { error: "No paused job found to resume" };
  }
  
  if (state.status !== "paused") {
    return { error: `Cannot resume job with status: ${state.status}. Only paused jobs can be resumed.` };
  }
  
  try {
    // Clear pause flag and set status to running
    await _safeStorageSet({ 
      bulk_job_pause: false,
      bulk_job_abort: false
    }, "resume bulk job");
    
    // Update state to running and increment resume count
    const resumedState = Object.assign({}, state, {
      status: "running",
      resume_count: (state.resume_count || 0) + 1,
      paused_at: null
    });
    await _safeStorageSet({ bulk_job_state: resumedState }, "update state to resuming");
    
    console.log(`[BulkJob] ▶️ Resuming job (resume_count=${resumedState.resume_count})`);
    
    // Start async resume process (don't await, let it run in background)
    _resumeBulkAsync(resumedState, accountId, userEmail).catch(e => {
      console.error("[BulkJob] Resume process error:", e.message);
      _safeStorageSet({ 
        bulk_job_state: Object.assign({}, resumedState, { 
          status: "error", 
          error: `Resume failed: ${e.message}` 
        }) 
      }, "resume error").catch(err => 
        console.error("[Storage] Could not save resume error:", err.message)
      );
    });
    
    return { success: true, state: resumedState };
  } catch (e) {
    return { error: `Failed to resume: ${e.message}` };
  }
}

async function handleRunBulkProcess({ months, accountId, userEmail }) {
  console.log("\n\n");
  console.log("🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴");
  console.log("🔴 BULK INDEX EMAIL BUTTON CLICKED!");
  console.log("🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴\n");
  
  const cfg = await getAddonConfig();
  const is10Days = (months === "10days");
  const n      = is10Days ? 0 : parseInt(months || String((cfg.bulk_processing && cfg.bulk_processing.default_months) || 3), 10);
  const before = new Date();
  const after  = new Date();
  if (is10Days) {
    after.setDate(after.getDate() - 10);
  } else {
    after.setMonth(after.getMonth() - n);
  }
  
  console.log(`[OpenMailBot][BulkStart] Processing last ${is10Days ? "10 days" : n + " months"}`);
  console.log(`[OpenMailBot][BulkStart] Date range: ${after.toLocaleDateString()} → ${before.toLocaleDateString()}`);
  console.log(`[OpenMailBot][BulkStart] FIX: Selected account ID: ${accountId || "(all accounts)"}`);
  console.log(`[OpenMailBot][BulkStart] FIX: User email: ${userEmail || "Unknown"}`);
  console.log(`[OpenMailBot][BulkStart] Backend URL: ${await getBackendUrl()}`);
  console.log(`[OpenMailBot][BulkStart] User ID: ${userEmail || await getUserId()}`);
  console.log(`[OpenMailBot][BulkStart] Config: ${JSON.stringify(cfg, null, 2)}\n`);
  
  const state = {
    n: is10Days ? 10 : n, 
    months: is10Days ? "10days" : String(n),
    afterStr : after.toLocaleDateString(),
    beforeStr: before.toLocaleDateString(),
    accountId: accountId || null,
    userEmail: userEmail || null,  // FIX: Store user email in state
    status   : "running",
    offset   : 0,
    stats    : { threadsScanned:0, messagesFound:0, labeled:0, skipped:0, filtered:0, errors:0 },
    
    // ── PAUSE/RESUME CHECKPOINT ──────────────────────────────
    checkpoint: {
      from_date: after.toISOString().split('T')[0],
      to_date: before.toISOString().split('T')[0],
      account_index: 0,
      account_id: null,
      folder_index: 0,
      folder_path: null,
      message_page_id: null,
      message_batch_index: 0,
      message_offset: 0,
      last_message_id: null,
      last_subject: null,
      last_processed_time: null
    },
    
    // ── PAUSE METADATA ────────────────────────────────────
    paused_at: null,
    pause_reason: null,
    resume_count: 0
  };
  await _safeStorageSet({ 
    bulk_job_state: state, 
    bulk_job_abort: false,
    bulk_job_pause: false
  }, "start bulk job");
  _runBulkAsync(n, after, before, state, accountId, userEmail).catch(e => {
    console.error("\n[OpenMailBot] BULK PROCESS ERROR:", e.message);
    console.error("[OpenMailBot] Stack:", e.stack);
    _safeStorageSet({ bulk_job_state: Object.assign({}, state, { status:"error", error:e.message }) }, "bulk job error").catch(err => 
      console.error("[Storage] Could not save bulk error state:", err.message)
    );
  });
  return { success: true, state };
}

/**
 * Resume a paused bulk job from saved checkpoint
 * Restores iteration state and continues processing
 */
async function _resumeBulkAsync(state, accountId, userEmail) {
  const cfg        = await getAddonConfig();
  const bp         = cfg.bulk_processing || {};
  const BATCH      = bp.batch_size           || 10;
  const MAX_MSGS   = bp.max_messages_per_run || 2000;
  const DELAY_MS   = bp.request_delay_ms     || 200;
  
  const checkpoint = state.checkpoint || {};
  const afterStr = checkpoint.from_date;
  const beforeStr = checkpoint.to_date;
  
  const after = new Date(afterStr + 'T00:00:00Z');
  const before = new Date(beforeStr + 'T23:59:59Z');
  
  console.log(`\n[OpenMailBot][Resume] ▶️ RESUMING from checkpoint`);
  console.log(`[OpenMailBot][Resume] Date range: ${afterStr} → ${beforeStr}`);
  console.log(`[OpenMailBot][Resume] Resume count: ${state.resume_count}`);
  console.log(`[OpenMailBot][Resume] Last processed: ${checkpoint.last_subject || "(none)"} (ID: ${checkpoint.last_message_id})`);
  console.log(`[OpenMailBot][Resume] Starting from account_index=${checkpoint.account_index}, folder_index=${checkpoint.folder_index}\n`);
  
  let defaultUserId = userEmail;
  if (!defaultUserId) {
    if (accountId) {
      try {
        defaultUserId = await getAccountEmail(accountId);
      } catch (e) {
        console.warn(`[OpenMailBot][Resume] Could not get email for account: ${e.message}`);
      }
    }
    if (!defaultUserId) {
      defaultUserId = await getUserId();
    }
  }
  
  const backendUrl = await getBackendUrl();
  const filters    = await _getMergedDomainFilters();
  
  let totalProcessed = 0;
  const allAccounts = await browser.accounts.list();
  const accounts = accountId
    ? allAccounts.filter(a => a.id === accountId)
    : allAccounts;
  
  console.log(`[OpenMailBot][Resume] Processing ${accounts.length} account(s)`);
  
  // Start from checkpoint account_index
  for (let acctIdx = checkpoint.account_index || 0; acctIdx < accounts.length; acctIdx++) {
    if (totalProcessed >= MAX_MSGS) break;
    
    const acc = accounts[acctIdx];
    let accountEmail = defaultUserId;
    try {
      const email = await getAccountEmail(acc.id);
      if (email) accountEmail = email;
    } catch (e) {
      console.warn(`[OpenMailBot][Resume] Could not get email for account, using default`);
    }
    
    state.checkpoint.account_index = acctIdx;
    state.checkpoint.account_id = acc.id;
    
    const allFolders = _collectAllFolders(acc.folders);
    console.log(`[OpenMailBot][Resume] Account ${acctIdx}: ${acc.name} - ${allFolders.length} folder(s)`);
    
    // Start from checkpoint folder_index (reset if new account)
    const folderStartIdx = acctIdx === (checkpoint.account_index || 0) ? (checkpoint.folder_index || 0) : 0;
    
    for (let folderIdx = folderStartIdx; folderIdx < allFolders.length; folderIdx++) {
      if (totalProcessed >= MAX_MSGS) break;
      
      const folder = allFolders[folderIdx];
      state.checkpoint.folder_index = folderIdx;
      state.checkpoint.folder_path = folder.name;
      
      let page;
      try {
        page = await browser.messages.list(folder);
      } catch (e) {
        console.warn(`[OpenMailBot][Resume] Cannot list folder: ${folder.name}`);
        continue;
      }
      
      // If resuming within the same folder, try to restore page continuation
      if (acctIdx === (checkpoint.account_index || 0) && 
          folderIdx === (checkpoint.folder_index || 0) && 
          checkpoint.message_page_id) {
        try {
          console.log(`[OpenMailBot][Resume] Restoring page: ${checkpoint.message_page_id}`);
          page = await browser.messages.continueList(checkpoint.message_page_id);
        } catch (e) {
          console.warn(`[OpenMailBot][Resume] Could not restore page, starting fresh: ${e.message}`);
          // Fallback: restart folder (page ID may have expired)
          try {
            page = await browser.messages.list(folder);
          } catch (e2) {
            console.warn(`[OpenMailBot][Resume] Cannot restart folder either`);
            continue;
          }
        }
      }
      
      let pageCount = 0;
      while (page) {
        pageCount++;
        
        // Check for pause
        const pc = await browser.storage.local.get("bulk_job_pause");
        if (pc.bulk_job_pause) {
          console.log(`[OpenMailBot][Resume] ⏸ Pause detected during resuming`);
          state.status = "paused";
          state.paused_at = new Date().toISOString();
          state.pause_reason = "user";
          state.message_page_id = page.id;  // Save for resume
          try {
            await _safeStorageSet({ 
              bulk_job_state: state,
              bulk_job_pause: true 
            }, "pause during resume");
          } catch (e) {
            console.error("[Resume] Could not save pause state:", e.message);
          }
          return;
        }
        
        // Check for abort
        const ac = await browser.storage.local.get("bulk_job_abort");
        if (ac.bulk_job_abort) {
          console.log(`[OpenMailBot][Resume] 🛑 Abort detected during resuming`);
          state.status = "cancelled";
          try {
            await _safeStorageSet({ bulk_job_state: state }, "cancel during resume");
          } catch (e) {
            console.error("[Resume] Could not save cancel state:", e.message);
          }
          return;
        }
        
        const rawMsgs = page.messages || [];
        console.log(`[OpenMailBot][Resume] Page ${pageCount}: ${rawMsgs.length} message(s)`);
        state.stats.threadsScanned += rawMsgs.length;
        
        // Filter messages
        const msgs = rawMsgs.filter(m => {
          const d = m.date ? new Date(m.date) : null;
          if (!d || isNaN(d.getTime())) return false;
          if (d < after || d > before) return false;
          if (_shouldFilterEmail(m.author, filters)) { state.stats.filtered++; return false; }
          if ((m.recipients||[]).some(r => _shouldFilterEmail(r, filters))) { state.stats.filtered++; return false; }
          return true;
        });
        
        state.stats.messagesFound += msgs.length;
        
        // Process batches
        for (let i = 0; i < msgs.length; i += BATCH) {
          if (totalProcessed >= MAX_MSGS) break;
          
          // Skip batches we already processed (for resume in middle of folder)
          if (acctIdx === (checkpoint.account_index || 0) && 
              folderIdx === (checkpoint.folder_index || 0) && 
              pageCount === 1 && 
              checkpoint.message_batch_index && 
              Math.floor(i / BATCH) < checkpoint.message_batch_index) {
            console.log(`[OpenMailBot][Resume] Skipping already-processed batch ${Math.floor(i/BATCH)}`);
            continue;
          }
          
          for (const msg of msgs.slice(i, i + BATCH)) {
            if (totalProcessed >= MAX_MSGS) break;
            
            try {
              const full = await browser.messages.getFull(msg.id);
              const tid = _getCanonicalThreadId(msg, full);
              const atts = await _getAttachments(msg.id);
              
              if (atts.length) {
                const storeAttsUrl = `${backendUrl}/api/store-attachments`;
                await _storeAtts(backendUrl, accountEmail, tid, String(msg.id), atts);
              }
              
              const labelEmailUrl = `${backendUrl}/api/label-email`;
              const msgData = _fmtMsg(msg, full);
              const labelResult = await _labelEmailOnServer(backendUrl, accountEmail, tid, [msgData]);
              const assignedLabel = labelResult && (labelResult.label || labelResult.category);
              
              if (assignedLabel) {
                await _applyThunderbirdTag(msg.id, assignedLabel);
              }
              
              state.stats.labeled++;
              state.checkpoint.last_message_id = msg.id;
              state.checkpoint.last_subject = msg.subject;
              state.checkpoint.last_processed_time = new Date().toISOString();
              totalProcessed++;
            } catch (e) {
              console.error(`[Resume] Error processing msg ${msg.id}:`, e.message);
              state.stats.errors++;
              totalProcessed++;
            }
            
            await new Promise(r => setTimeout(r, DELAY_MS));
          }
          
          state.offset = state.stats.labeled + state.stats.errors;
          state.checkpoint.message_batch_index = Math.floor(i / BATCH) + 1;
          try {
            await _safeStorageSet({ bulk_job_state: state }, "update resume progress");
          } catch (e) {
            console.warn(`[Resume] Could not save progress: ${e.message}`);
          }
        }
        
        if (page.id) {
          try {
            page = await browser.messages.continueList(page.id);
            state.checkpoint.message_page_id = page ? page.id : null;
          } catch (e) {
            console.warn(`[Resume] continueList failed: ${e.message}`);
            break;
          }
        } else {
          break;
        }
      }
      
      // Reset page tracking for next folder
      state.checkpoint.message_page_id = null;
      state.checkpoint.message_batch_index = 0;
    }
  }
  
  const finalStatus = totalProcessed >= MAX_MSGS ? "done_limit" : "done";
  console.log(`[OpenMailBot][Resume] ■ Finished | status=${finalStatus} | totalProcessed=${totalProcessed}`);
  try {
    await _safeStorageSet({ 
      bulk_job_state: Object.assign({}, state, { status: finalStatus }) 
    }, "save resume final status");
  } catch (e) {
    console.error(`[Resume] Could not save final status: ${e.message}`);
  }
}

async function _runBulkAsync(n, after, before, state, accountId, userEmail) {
  const cfg        = await getAddonConfig();
  const bp         = cfg.bulk_processing || {};
  const BATCH      = bp.batch_size           || 10;
  const MAX_MSGS   = bp.max_messages_per_run || 2000;
  const DELAY_MS   = bp.request_delay_ms     || 200;

  // FIX: Use passed userEmail, or extract from the actual account being processed
  let defaultUserId = userEmail;
  if (!defaultUserId) {
    // Try to get email from the selected account if provided
    if (accountId) {
      try {
        defaultUserId = await getAccountEmail(accountId);
        console.log(`[OpenMailBot][BulkIndex] Got email for account ${accountId}: ${defaultUserId}`);
      } catch (e) {
        console.warn(`[OpenMailBot][BulkIndex] Could not get email for account ${accountId}:`, e.message);
      }
    }
    // Last resort: use first account
    if (!defaultUserId) {
      defaultUserId = await getUserId();
      console.warn("[OpenMailBot][BulkIndex] No userEmail passed, using default");
    }
  }
  
  const backendUrl = await getBackendUrl();
  const filters    = await _getMergedDomainFilters();

  console.log(`[OpenMailBot][BulkIndex] ▶ Starting bulk index | user=${defaultUserId} | backendUrl=${backendUrl} | dateRange=${after.toLocaleDateString()} → ${before.toLocaleDateString()} | BATCH=${BATCH} | MAX_MSGS=${MAX_MSGS} | domainFilters=${filters.length}`);

  let totalProcessed = 0;

  const allAccounts = await browser.accounts.list();
  // FIX: Filter to selected account if provided
  const accounts = accountId
    ? allAccounts.filter(a => a.id === accountId)
    : allAccounts;
  
  if (accountId && accounts.length === 0) {
    console.warn(`[OpenMailBot][BulkIndex] ⚠️ Selected account not found: ${accountId}`);
    return;
  }
  
  console.log(`[OpenMailBot][BulkIndex] Found ${accounts.length} mail account(s) to process${accountId ? ` (filtered to: ${accountId})` : ""}`);
  
  for (let acctIdx = 0; acctIdx < accounts.length; acctIdx++) {
    if (totalProcessed >= MAX_MSGS) break;
    
    const acc = accounts[acctIdx];
    state.checkpoint.account_index = acctIdx;
    state.checkpoint.account_id = acc.id;
    
    // FIX: Get the email address for THIS specific account
    let accountEmail = defaultUserId;
    try {
      const email = await getAccountEmail(acc.id);
      if (email) {
        accountEmail = email;
        console.log(`[OpenMailBot][BulkIndex] Account email resolved: ${acc.id} → ${accountEmail}`);
      }
    } catch (e) {
      console.warn(`[OpenMailBot][BulkIndex] Could not get email for account ${acc.id}, using default: ${e.message}`);
    }

    console.log(`[OpenMailBot][BulkIndex] Processing account: ${acc.name||acc.id} (${accountEmail})`);
    
    // Search ALL folders, not just inbox, to catch Sent/other folders
    const allFolders = _collectAllFolders(acc.folders);
    console.log(`[OpenMailBot][BulkIndex] Found ${allFolders.length} folder(s) to scan`);
    
    for (let folderIdx = 0; folderIdx < allFolders.length; folderIdx++) {
      if (totalProcessed >= MAX_MSGS) break;

      const folder = allFolders[folderIdx];
      state.checkpoint.folder_index = folderIdx;
      state.checkpoint.folder_path = folder.name;
      
      console.log(`[OpenMailBot][BulkIndex] 📂 Scanning folder: "${folder.name}" (type=${folder.type||"unknown"})`);

      let page;
      try {
        page = await browser.messages.list(folder);
      } catch(e) {
        console.warn("[OpenMailBot] Cannot list folder:", folder.name, e.message);
        continue;
      }

      let pageNum = 0;
      while (page) {
        pageNum++;
        
        // ── PAUSE CHECK ──────────────────────────────────────────
        const pc = await browser.storage.local.get("bulk_job_pause");
        if (pc.bulk_job_pause) {
          console.log(`[OpenMailBot][BulkIndex] ⏸ Pause detected - saving checkpoint`);
          state.status = "paused";
          state.paused_at = new Date().toISOString();
          state.pause_reason = "user";
          state.checkpoint.message_page_id = page.id;  // Save pagination token
          try {
            await _safeStorageSet({ 
              bulk_job_state: state,
              bulk_job_pause: true 
            }, "pause bulk job with checkpoint");
          } catch (e) {
            console.error("[OpenMailBot][BulkIndex] Could not save pause checkpoint:", e.message);
          }
          return;
        }
        
        // ── ABORT CHECK ──────────────────────────────────────────
        const ac = await browser.storage.local.get("bulk_job_abort");
        if (ac.bulk_job_abort) {
          console.log(`[OpenMailBot][BulkIndex] 🛑 Abort detected`);
          try {
            await _safeStorageSet({ bulk_job_state: Object.assign({}, state, { status:"cancelled" }) }, "bulk job cancelled");
          } catch (e) {
            console.error("[OpenMailBot][BulkIndex] Could not save cancelled status:", e.message);
          }
          return;
        }

        const rawMsgs = page.messages || [];
        console.log(`[OpenMailBot][BulkIndex] Page ${pageNum} has ${rawMsgs.length} message(s)`);
        state.stats.threadsScanned += rawMsgs.length;

        // Filter by date and domain
        const msgs = rawMsgs.filter(m => {
          const d = m.date ? new Date(m.date) : null;
          if (!d || isNaN(d.getTime())) return false;   // skip messages with no/invalid date
          if (d < after || d > before)  return false;   // outside date window
          if (_shouldFilterEmail(m.author, filters))    { state.stats.filtered++; return false; }
          if ((m.recipients||[]).some(r => _shouldFilterEmail(r, filters))) { state.stats.filtered++; return false; }
          return true;
        });

        console.log(`[OpenMailBot][BulkIndex] After filtering: ${msgs.length} message(s) to process`);
        state.stats.messagesFound += msgs.length;

        // Process in batches
        for (let i = 0; i < msgs.length; i += BATCH) {
          if (totalProcessed >= MAX_MSGS) break;

          // ── PAUSE & ABORT CHECK IN BATCH ────────────────────────
          const pc2 = await browser.storage.local.get("bulk_job_pause");
          if (pc2.bulk_job_pause) {
            console.log(`[OpenMailBot][BulkIndex] ⏸ Pause detected in batch - saving checkpoint`);
            state.status = "paused";
            state.paused_at = new Date().toISOString();
            state.checkpoint.message_page_id = page.id;
            state.checkpoint.message_batch_index = Math.floor(i / BATCH);
            try {
              await _safeStorageSet({ 
                bulk_job_state: state,
                bulk_job_pause: true 
              }, "pause in batch");
            } catch (e) {
              console.error("[BulkIndex] Could not save pause in batch:", e.message);
            }
            return;
          }
          
          const ac2 = await browser.storage.local.get("bulk_job_abort");
          if (ac2.bulk_job_abort) {
            console.log(`[OpenMailBot][BulkIndex] 🛑 Abort detected in batch loop`);
            try {
              await _safeStorageSet({ bulk_job_state: Object.assign({}, state, { status:"cancelled" }) }, "bulk job cancelled in batch");
            } catch (e) {
              console.error("[OpenMailBot][BulkIndex] Could not save batch cancelled status:", e.message);
            }
            return;
          }

          console.log(`[OpenMailBot][BulkIndex] Processing batch ${Math.floor(i/BATCH)+1} (${Math.min(BATCH, msgs.length-i)} messages)`);

          for (const msg of msgs.slice(i, i + BATCH)) {
            if (totalProcessed >= MAX_MSGS) break;
            try {
              const full = await browser.messages.getFull(msg.id);
              const tid  = _getCanonicalThreadId(msg, full);
              // Store attachments FIRST so label-email's CheckAndStoreAttachmentsPipeline can find them on disk
              const atts = await _getAttachments(msg.id);
              if (atts.length) {
                const storeAttsUrl = `${backendUrl}/api/store-attachments`;
                console.log(`[OpenMailBot][BulkIndex] POST ${storeAttsUrl} | thread_id=${tid} | msg_id=${msg.id} | attachments=${atts.length} [${atts.map(a=>a.filename).join(", ")}]`);
                // FIX: Use account-specific email (accountEmail)
                await _storeAtts(backendUrl, accountEmail, tid, String(msg.id), atts);
                console.log(`[OpenMailBot][BulkIndex] ✓ store-attachments OK | thread_id=${tid}`);
              }
              // Call /api/label-email (full pipeline: preprocess → vector embed → label → graph store)
              // This is the correct endpoint — /api/log-email only dumps JSON to disk with no indexing
              const labelEmailUrl = `${backendUrl}/api/label-email`;
              const msgData = _fmtMsg(msg, full);
              console.log(`[OpenMailBot][BulkIndex] ╔════════════════════════════════════════`);
              console.log(`[OpenMailBot][BulkIndex] ║ CALLING: POST ${labelEmailUrl}`);
              console.log(`[OpenMailBot][BulkIndex] ║ thread_id: ${tid}`);
              console.log(`[OpenMailBot][BulkIndex] ║ msg_id: ${msg.id}`);
              console.log(`[OpenMailBot][BulkIndex] ║ subject: "${msg.subject}"`);
              console.log(`[OpenMailBot][BulkIndex] ║ from: "${msg.author}"`);
              // FIX: Use account-specific email in payload
              console.log(`[OpenMailBot][BulkIndex] ║ payload: ${JSON.stringify({ user_id:accountEmail, thread_id:tid, messages: [msgData] }, null, 2)}`);
              console.log(`[OpenMailBot][BulkIndex] ╚════════════════════════════════════════`);
              const labelResult = await _labelEmailOnServer(backendUrl, accountEmail, tid, [msgData]);
              const assignedLabel = labelResult && (labelResult.label || labelResult.category);
              console.log(`[OpenMailBot][BulkIndex] ✓ label-email OK | thread_id=${tid} | label=${assignedLabel||"(none)"}`);

              // ── Apply the label as a Thunderbird tag on the actual message ──
              if (assignedLabel) {
                await _applyThunderbirdTag(msg.id, assignedLabel);
              }

              // ── UPDATE CHECKPOINT ────────────────────────────────────
              state.stats.labeled++;
              state.checkpoint.last_message_id = msg.id;
              state.checkpoint.last_subject = msg.subject;
              state.checkpoint.last_processed_time = new Date().toISOString();
              totalProcessed++;
            } catch(e) {
              console.error(`[OpenMailBot][BulkIndex] ✗ Error processing msg_id=${msg.id} subject="${msg.subject}":`, e.message);
              state.stats.errors++;
              totalProcessed++;
            }
            // Brief delay between requests to avoid overwhelming the server
            await new Promise(r => setTimeout(r, DELAY_MS));
          }

          state.offset = state.stats.labeled + state.stats.errors;
          state.checkpoint.message_batch_index = Math.floor(i / BATCH) + 1;
          try {
            await _safeStorageSet({ bulk_job_state: state }, "update bulk job progress");
          } catch (e) {
            console.warn(`[OpenMailBot][BulkIndex] Could not save progress: ${e.message}`);
          }
        }

        if (page.id) {
          try { 
            page = await browser.messages.continueList(page.id);
            state.checkpoint.message_page_id = page ? page.id : null;
          }
          catch(e) { 
            console.warn("[OpenMailBot] continueList:", e.message); 
            break; 
          }
        } else {
          break;
        }
      }
      
      // Reset page tracking when moving to next folder
      state.checkpoint.message_page_id = null;
      state.checkpoint.message_batch_index = 0;
    }
  }

  const finalStatus = totalProcessed >= MAX_MSGS ? "done_limit" : "done";
  console.log(`[OpenMailBot][BulkIndex] ■ Finished | status=${finalStatus} | totalProcessed=${totalProcessed} | labeled=${state.stats.labeled} | errors=${state.stats.errors} | filtered=${state.stats.filtered}`);
  try {
    await _safeStorageSet({ bulk_job_state: Object.assign({}, state, { status: finalStatus }) }, "save bulk job final status");
  } catch (e) {
    console.error(`[OpenMailBot][BulkIndex] Could not save final status: ${e.message}`);
  }
}

// ─── THUNDERBIRD TAG APPLICATION ─────────────────────────────────────────────

/**
 * Apply a backend label (from /api/label-email) as a Thunderbird tag on a message.
 * 
 * WORKFLOW:
 * 1. Initialize label mapping (if needed) — maps backend labels to existing Thunderbird tags
 * 2. Apply semantic mapping to find best matching tag
 * 3. Create tag if it doesn't exist
 * 4. Apply tag to message using multiple fallback methods
 *
 * KEY FIXES:
 * 1. Use browser.* consistently (not messenger.* which is unreliable in MV2)
 * 2. Thunderbird tag keys must be lowercase, no spaces (use underscores)
 * 3. tags.create() in TB 121+ takes (key, color, label) or (key, label, color) depending on version
 * 4. Wrap each step independently so one failure doesn't kill the other
 * 5. Add detailed logging at every step to pinpoint failures
 * 6. FIX: Skip re-labeling if message already has ANY OpenMailBot-managed tag (prevents multiple labels)
 *
 * @param {number} messageId  - Thunderbird internal message id
 * @param {string} labelName  - Raw label string returned by /api/label-email (backend label)
 */
async function _applyThunderbirdTag(messageId, labelName) {
  if (!labelName) return;

  // ── Step 0: Initialize label mapping if needed ────────────────────────────
  if (!_labelMappingInitialized) {
    console.log(`[OpenMailBot][Tag] Label mapping not initialized, initializing now...`);
    await _initializeLabelMapping();
  }

  // ── FIX: Check if email already has an OpenMailBot-managed tag ────────────────────
  // If it does, skip re-labeling to prevent multiple labels on the same email
  try {
    const msgMeta     = await browser.messages.get(messageId);
    const currentTags = Array.isArray(msgMeta.tags) ? msgMeta.tags : [];
    const hasExistingTag = currentTags.some(t => OPENMAILBOT_MANAGED_TAGS.has(t));
    
    if (hasExistingTag) {
      console.log(`[OpenMailBot][Tag] ✅ Message ${messageId} already has OpenMailBot tag: ${JSON.stringify(currentTags)}`);
      console.log(`[OpenMailBot][Tag] ⊘ Skipping re-label with "${labelName}" to prevent multiple labels`);
      return;
    }
  } catch (e) {
    console.warn(`[OpenMailBot][Tag] Could not check existing tags: ${e.message} — continuing anyway`);
  }

  // ── Step 1: Map backend label to Thunderbird tag key ──────────────────────
  const mappedKey = _mapBackendLabelToThunderbirdKey(labelName);
  // Sanitize the key: lowercase, replace spaces with underscores, remove special chars
  const key     = (mappedKey || labelName).toLowerCase().replace(/\s+/g, "_").replace(/[^a-z0-9_]/g, "");
  const display = labelName.charAt(0).toUpperCase() + labelName.slice(1).toLowerCase();
  const color   = (
    THUNDERBIRD_LABEL_COLORS[labelName.toLowerCase()] ||
    THUNDERBIRD_LABEL_COLORS[key] ||
    THUNDERBIRD_LABEL_COLORS[mappedKey] ||
    "#888888"
  ).toUpperCase();

  console.log(`[OpenMailBot][Tag] ▶ Applying tag | msgId=${messageId} | backendLabel="${labelName}" | mappedKey="${mappedKey}" | finalKey="${key}" | color=${color}`);

  // ── Step 2: Ensure tag exists ─────────────────────────────────────────────
  try {
    const existingTags = await browser.messages.tags.list();
    const tagExists = existingTags.some(t => (t.key || "").toLowerCase() === key);
    if (!tagExists) {
      // TB 128+: create(key, color, label) | TB 121-127: create(key, label, color)
      try {
        await browser.messages.tags.create(key, color, display);
        console.log(`[OpenMailBot][Tag] ✅ Created tag (key,color,label): "${key}"`);
      } catch (e1) {
        console.warn(`[OpenMailBot][Tag] create(key,color,label) failed: ${e1.message} — trying (key,label,color)`);
        await browser.messages.tags.create(key, display, color);
        console.log(`[OpenMailBot][Tag] ✅ Created tag (key,label,color): "${key}"`);
      }
    } else {
      console.log(`[OpenMailBot][Tag] Tag "${key}" already exists`);
    }
  } catch (e) {
    console.error(`[OpenMailBot][Tag] ❌ tags.create/list failed: ${e.message}`);
    // Continue anyway — tag may already exist even if list() failed
  }

  // ── Step 3: Apply tag to message ──────────────────────────────────────────
  // Thunderbird messages.update({ tags }) REPLACES tags, so we must merge first.
  // The tags array must contain the exact key strings (e.g. "notification", "$label1").

  // METHOD A: browser.messages.update with merged tags array
  try {
    const msgMeta     = await browser.messages.get(messageId);
    const currentTags = Array.isArray(msgMeta.tags) ? msgMeta.tags : [];
    console.log(`[OpenMailBot][Tag] Current tags on msg ${messageId}: ${JSON.stringify(currentTags)}`);

    // Remove any stale OpenMailBot-assigned tags before applying the new one
    const filteredTags = currentTags.filter(t => !OPENMAILBOT_MANAGED_TAGS.has(t));
    const updatedTags = filteredTags.includes(key) ? filteredTags : [...filteredTags, key];

    if (updatedTags.length === currentTags.length && currentTags.includes(key)) {
      console.log(`[OpenMailBot][Tag] ✅ Tag "${key}" already on message — nothing to do`);
      return;
    }

    console.log(`[OpenMailBot][Tag] Calling browser.messages.update(${messageId}, { tags: ${JSON.stringify(updatedTags)} })`);
    await browser.messages.update(messageId, { tags: updatedTags });

    // Verify it actually stuck
    const verify = await browser.messages.get(messageId);
    const verifyTags = Array.isArray(verify.tags) ? verify.tags : [];
    console.log(`[OpenMailBot][Tag] Post-update tags: ${JSON.stringify(verifyTags)}`);

    if (verifyTags.includes(key)) {
      console.log(`[OpenMailBot][Tag] ✅ Tag "${key}" successfully applied to msg ${messageId}`);
      return;
    } else {
      console.warn(`[OpenMailBot][Tag] ⚠️ update() returned no error but tag not found in verify — trying Method B`);
    }
  } catch (e) {
    console.warn(`[OpenMailBot][Tag] Method A (browser.messages.update) failed: ${e.message} — trying Method B`);
  }

  // METHOD B: messenger.messages.update (some TB versions require this namespace)
  try {
    const msgMeta     = await messenger.messages.get(messageId);
    const currentTags = Array.isArray(msgMeta.tags) ? msgMeta.tags : [];
    const filteredTagsB = currentTags.filter(t => !OPENMAILBOT_MANAGED_TAGS.has(t));
    const updatedTags = filteredTagsB.includes(key) ? filteredTagsB : [...filteredTagsB, key];

    console.log(`[OpenMailBot][Tag] Method B: messenger.messages.update(${messageId}, { tags: ${JSON.stringify(updatedTags)} })`);
    await messenger.messages.update(messageId, { tags: updatedTags });

    const verify = await messenger.messages.get(messageId);
    const verifyTags = Array.isArray(verify.tags) ? verify.tags : [];
    console.log(`[OpenMailBot][Tag] Method B post-update tags: ${JSON.stringify(verifyTags)}`);

    if (verifyTags.includes(key)) {
      console.log(`[OpenMailBot][Tag] ✅ Method B: Tag "${key}" applied to msg ${messageId}`);
      return;
    } else {
      console.warn(`[OpenMailBot][Tag] ⚠️ Method B: tag not found after update`);
    }
  } catch (e) {
    console.warn(`[OpenMailBot][Tag] Method B (messenger.messages.update) failed: ${e.message}`);
  }

  // METHOD C: Use the tags.update API if available (TB 128+ alternative)
  try {
    if (browser.messages.tags && browser.messages.tags.update) {
      console.log(`[OpenMailBot][Tag] Method C: browser.messages.tags.update`);
      await browser.messages.tags.update(messageId, { tags: [key] });
      console.log(`[OpenMailBot][Tag] ✅ Method C succeeded`);
      return;
    }
  } catch (e) {
    console.warn(`[OpenMailBot][Tag] Method C failed: ${e.message}`);
  }

  // METHOD D: Try updating with object format { [key]: true }
  try {
    console.log(`[OpenMailBot][Tag] Method D: object-format tags`);
    await browser.messages.update(messageId, { tags: { [key]: true } });
    const verify = await browser.messages.get(messageId);
    console.log(`[OpenMailBot][Tag] Method D post-update tags: ${JSON.stringify(verify.tags)}`);
    console.log(`[OpenMailBot][Tag] ✅ Method D: attempted`);
  } catch (e) {
    console.warn(`[OpenMailBot][Tag] Method D failed: ${e.message}`);
  }

  console.error(`[OpenMailBot][Tag] ❌ ALL METHODS FAILED for tag "${key}" on msg ${messageId}`);
}

/**
 * Ensure the 1-minute repeating alarm exists.
 * Safe to call multiple times — checks before creating.
 */
function _ensureMonitorAlarm() {
  browser.alarms.get(MONITOR_ALARM_NAME).then(existing => {
    if (!existing) {
      browser.alarms.create(MONITOR_ALARM_NAME, {
        delayInMinutes : 1,
        periodInMinutes: MONITOR_INTERVAL_MINS
      });
      console.log("[OpenMailBot][Monitor] Alarm created (interval=" + MONITOR_INTERVAL_MINS + " min)");
    } else {
      console.log("[OpenMailBot][Monitor] Alarm already registered");
    }
  }).catch(() => {
    browser.alarms.create(MONITOR_ALARM_NAME, {
      delayInMinutes : 1,
      periodInMinutes: MONITOR_INTERVAL_MINS
    });
  });
}

// ─── MAIN MONITOR LOOP ───────────────────────────────────────────────────────

/**
 * Check for auto-generated drafts and open them in a compose window.
 * 
 * This function is called during every monitor cycle to poll the backend for
 * new auto-drafts generated by label-email-async (when "Escalation" or "Response"
 * labels are assigned).
 * 
 * When drafts are found:
 * 1. Fetch them from the /api/auto-drafts/{user_id} endpoint
 * 2. For each draft, open it in a compose window
 * 3. The drafts are automatically consumed (won't be returned again)
 */
async function _checkAndOpenAutoDrafts(userId, backendUrl) {
  if (!userId || !backendUrl) return;
  
  try {
    const response = await fetch(`${backendUrl}/api/auto-drafts/${encodeURIComponent(userId)}`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
    });
    
    if (!response.ok) {
      if (response.status !== 404) { // 404 is expected when no drafts
        console.warn(`[AutoDraft] Fetch failed: ${response.status}`);
      }
      return;
    }
    
    const data = await response.json();
    const autoDrafts = data.auto_drafts || [];
    
    if (autoDrafts.length === 0) {
      return; // No auto-drafts to process
    }
    
    console.log(`[AutoDraft] 🚀 Found ${autoDrafts.length} auto-draft(s) from backend`);
    
    for (const draft of autoDrafts) {
      try {
        const { thread_id, draft_content, subject, created_at } = draft;
        
        console.log(`[AutoDraft] 📝 Opening auto-draft for thread: ${thread_id}`);
        console.log(`[AutoDraft]    Subject: ${subject}`);
        console.log(`[AutoDraft]    Content length: ${draft_content.length} chars`);
        console.log(`[AutoDraft]    Generated at: ${created_at}`);
        
        // Open compose window with the auto-draft
        // Since we don't have the recipient email from this endpoint, we'll open a blank compose
        // and populate it with the draft content via the message body
        const composeDetails = {
          plainTextBody: draft_content,
          isPlainText: true,
        };
        
        // Try to parse subject to extract recipient if it starts with "To: "
        if (subject && subject.includes("To:")) {
          const toMatch = subject.match(/To:\s*([^\n]+)/);
          if (toMatch) {
            composeDetails.to = [toMatch[1].trim()];
          }
        }
        
        // Set subject if available (remove "To: " prefix if present)
        if (subject) {
          composeDetails.subject = subject.replace(/^To:\s*[^\n]+\n?/, '').substring(0, 100);
        }
        
        await browser.compose.beginNew(composeDetails);
        console.log(`[AutoDraft] ✅ Compose window opened for thread: ${thread_id}`);
      } catch (e) {
        console.error(`[AutoDraft] ❌ Failed to open draft: ${e.message}`);
      }
    }
  } catch (e) {
    console.error(`[AutoDraft] ❌ Error checking auto-drafts: ${e.message}`);
  }
}

/**
 * Mirrors GAS monitorEmails():
 * - Scans inbox/sent folders for messages newer than the last check time
 * - Skips already-processed message IDs
 * - Applies domain filter
 * - Sends each new message to /api/label-email-async
 * - Polls for the label result and applies it as a Thunderbird tag
 * 
 * FIX: Added concurrency guard to prevent multiple simultaneous runs on startup
 * This prevents duplicate email processing when onInstalled/onStartup/onNewMailReceived fire together
 */
async function monitorNewEmails() {
  // FIX: Concurrency guard — prevent running simultaneously
  if (_monitorRunning) {
    console.log("[OpenMailBot][Monitor] ⏸ Monitor already running, skipping this call");
    return;
  }
  _monitorRunning = true;
  try {
    // FIX: Drain any messages that were queued while offline (inside the lock)
    await _drainOfflineQueue().catch(e => console.warn("[Monitor] drainOfflineQueue:", e.message));

    const backendUrl = await getBackendUrl();
    if (!backendUrl) { console.log("[OpenMailBot][Monitor] No backend URL — skipping"); return; }

    // Load last check time (when monitor last ran)
    const lastCheckData = await browser.storage.local.get(MONITOR_LAST_CHECK_KEY);
    let lastCheck = lastCheckData[MONITOR_LAST_CHECK_KEY]
      ? new Date(lastCheckData[MONITOR_LAST_CHECK_KEY])
      : new Date(Date.now() - (MONITOR_STARTUP_CATCHUP_HRS * 60 * 60 * 1000));
    
    const now = new Date();

    // ─── INACTIVITY CAP: Load from storage or use default ─────────────────────────
    // Users can configure this in addon settings; defaults to MONITOR_MAX_INACTIVITY_HRS
    let maxInactivityHrs = MONITOR_MAX_INACTIVITY_HRS;
    try {
      const storageData = await browser.storage.local.get(["monitor_inactivity_hours", "user_settings"]);
      if (storageData.monitor_inactivity_hours) {
        maxInactivityHrs = parseInt(storageData.monitor_inactivity_hours, 10) || MONITOR_MAX_INACTIVITY_HRS;
      } else if (storageData.user_settings && storageData.user_settings.monitor_inactivity_hours) {
        maxInactivityHrs = parseInt(storageData.user_settings.monitor_inactivity_hours, 10) || MONITOR_MAX_INACTIVITY_HRS;
      }
    } catch (e) {
      console.warn(`[Monitor] Could not load inactivity cap from storage: ${e.message}`);
    }

    // ─── INACTIVITY CAP: If user hasn't been active for cap+ hours, only scan last cap hours ────
    // This prevents processing huge backlogs when user is inactive (not an ideal customer)
    const hoursSinceLastCheck = (now - lastCheck) / (1000 * 60 * 60);
    if (hoursSinceLastCheck > maxInactivityHrs) {
      const cappedTime = new Date(now.getTime() - (maxInactivityHrs * 60 * 60 * 1000));
      console.log(`[OpenMailBot][Monitor] ⏱️ INACTIVITY CAP: Last check was ${hoursSinceLastCheck.toFixed(1)}h ago (> ${maxInactivityHrs}h threshold).`);
      console.log(`[OpenMailBot][Monitor] ⏱️ Capping to last ${maxInactivityHrs} hours: ${lastCheck.toISOString()} → ${cappedTime.toISOString()}`);
      lastCheck = cappedTime;
    }

    // FIX: Save the "now" timestamp immediately as the new check boundary
    // This prevents other concurrent calls from scanning the same time window again
    try {
      await _safeStorageSet({ [MONITOR_LAST_CHECK_KEY]: now.toISOString() }, "update monitor last check time at start");
    } catch (e) {
      console.warn(`[Monitor] Could not save initial check time: ${e.message}`);
    }

    const filters  = await _getMergedDomainFilters();
    const allAccounts = await browser.accounts.list();
    // Skip "Local Folders" and other non-mail virtual accounts (type === "none")
    let accounts = allAccounts.filter(a => a.type !== "none");
    
    // FIX: Filter to ONLY configured accounts (those that completed onboarding)
    // This prevents labeling requests for accounts user never set up
    try {
      const r = await browser.storage.local.get("configured_accounts");
      const configured = r.configured_accounts || [];
      
      if (configured.length > 0) {
        const beforeFilter = accounts.length;
        // Get email for each account and filter to only those in configured list
        const configuredAccounts = [];
        for (const acc of accounts) {
          try {
            const email = await getAccountEmail(acc.id);
            if (email && configured.includes(email)) {
              configuredAccounts.push(acc);
            } else if (email) {
              console.log(`[OpenMailBot][Monitor] ⊘ Skipping unconfigured account: ${email}`);
            }
          } catch (e) {
            console.warn(`[OpenMailBot][Monitor] Could not get email for account ${acc.id}: ${e.message}`);
          }
        }
        accounts = configuredAccounts;
        const afterFilter = accounts.length;
        console.log(`[OpenMailBot][Monitor] Account filtering: ${beforeFilter} total → ${afterFilter} configured (${beforeFilter - afterFilter} skipped)`);
      } else {
        console.log(`[OpenMailBot][Monitor] ℹ️ No configured accounts yet — monitor will skip all`);
        accounts = []; // If no accounts configured, process nothing
      }
    } catch (e) {
      console.warn(`[OpenMailBot][Monitor] Could not filter by configured_accounts: ${e.message}`);
      // Fallback: if storage read fails, still process all (conservative)
    }
    
    console.log(`[OpenMailBot][Monitor] Domain filters: ${filters.length} | Accounts: ${accounts.length}`);

    let found = 0, processed = 0, filtered = 0, skipped = 0, errors = 0;

    for (const acc of accounts) {
      // FIX: Get per-account email for correct user_id in multi-account setups
      let accountEmail = null;
      try {
        accountEmail = await getAccountEmail(acc.id);
        console.log(`[OpenMailBot][Monitor] Processing account: ${acc.name||acc.id} (${accountEmail})`);
      } catch (e) {
        console.warn(`[OpenMailBot][Monitor] Could not get email for account ${acc.id}:`, e.message);
      }

      const allFolders = _collectAllFolders(acc.folders);
      for (const folder of allFolders) {
        try {
          let page = await browser.messages.list(folder);
          while (page) {
            const candidates = (page.messages || []).filter(m => {
              const d = m.date ? new Date(m.date) : null;
              return d && d > lastCheck && d <= now;
            });
            found += candidates.length;

            for (const msg of candidates) {
              const outcome = await _processMonitorMessage(msg, filters, accountEmail).catch(e => {
                console.error(`[Monitor] ❌ Process error msg ${msg.id}: ${e.message}`);
                return "error";
              });
              if      (outcome === "processed") processed++;
              else if (outcome === "filtered")  filtered++;
              else if (outcome === "skipped")   skipped++;
              else                              errors++;
            }

            if (page.id) {
              try { page = await browser.messages.continueList(page.id); } catch(e) { break; }
            } else { break; }
          }
        } catch(e) {
          console.warn(`[OpenMailBot][Monitor] Folder error (${folder.name}): ${e.message}`);
        }
      }
    }

    // ─── POLL FOR AUTO-GENERATED DRAFTS (from label-email-async pipeline) ─────────
    // Every monitor cycle, check if there are new auto-drafts waiting to be opened
    try {
      const userId = await getUserId();
      if (userId) {
        await _checkAndOpenAutoDrafts(userId, await getBackendUrl());
      }
    } catch (e) {
      console.warn(`[OpenMailBot][Monitor] Auto-draft polling failed: ${e.message}`);
    }

    console.log(`[OpenMailBot][Monitor] === COMPLETE | found=${found} processed=${processed} filtered=${filtered} skipped=${skipped} errors=${errors} ===`);
  } finally {
    _monitorRunning = false;
  }
}

/**
 * Process a single message in the background monitor.
 * Returns: "processed" | "filtered" | "skipped" | "error"
 */
async function _processMonitorMessage(msg, filters, accountEmail) {
  const msgId = String(msg.id);

  // Skip already-processed
  if (await _isMonitorMsgProcessed(msgId)) {
    console.log(`[Monitor] ⊘ Skipped (already processed): ${msgId} "${msg.subject}"`);
    return "skipped";
  }

  // Domain filter
  if (!filters) filters = await _getMergedDomainFilters();
  if (_shouldFilterEmail(msg.author, filters) ||
      (msg.recipients || []).some(r => _shouldFilterEmail(r, filters))) {
    console.log(`[Monitor] 🚫 Filtered: "${msg.subject}" from=${msg.author}`);
    await _markMonitorMsgProcessed(msgId);
    return "filtered";
  }

  try {
    // ── Offline guard — queue for later if no network ─────────────────────
    if (!navigator.onLine) {
      await _queueOfflineMessage(msg);
      console.log(`[Monitor] 📴 Offline — queued msg ${msgId} "${msg.subject}" for later`);
      return "skipped";
    }

    // FIX: Use passed accountEmail or extract from message context
    let userId = accountEmail;
    if (!userId) {
      userId = await getAccountEmailFromMessage(msg.id).catch(() => null);
    }
    if (!userId) {
      userId = await getUserId(msg.id);
    }
    const backendUrl = await getBackendUrl();
    const full       = await browser.messages.getFull(msg.id);
    const threadId   = _getCanonicalThreadId(msg, full);
    const msgData    = _fmtMsg(msg, full);

    console.log(`[Monitor] → Processing: "${msg.subject}" (from: ${msg.author})`);

    // Store attachments first so the pipeline can embed them
    const atts = await _getAttachments(msg.id);
    if (atts.length) {
      await _storeAtts(backendUrl, userId, threadId, msgId, atts)
        .catch(e => console.warn("[Monitor] storeAtts failed:", e.message));
    }

    // POST to /api/label-email-async  → server queues the labeling pipeline
    // access_token is required by the server (used for Gmail push in GAS flow).
    // In Thunderbird, labeling is applied locally after polling, so a sentinel is sent.
    const resp = await fetch(`${backendUrl}/api/label-email-async`, {
      method : "POST",
      headers: { "Content-Type": "application/json" },
      body   : JSON.stringify({
        user_id      : userId,
        thread_id    : threadId,
        messages     : [msgData],
        attachments  : atts,
        access_token : "thunderbird_addon"
      })
    });

    if (resp.ok) {
      const data = await resp.json();
      console.log(`[Monitor] ✓ Queued: "${msg.subject}" | job_id=${data.job_id || "(sync)"}`);

      if (data.job_id) {
        // Async response — poll for label, then apply tag (non-blocking)
        _pollAndApplyMonitorLabel(msg.id, data.job_id, backendUrl).catch(e =>
          console.warn(`[Monitor] Label poll failed for msg ${msgId}: ${e.message}`)
        );
      } else {
        // Synchronous response — apply label immediately
        const label = data.label || data.category;
        if (label) {
          await _applyThunderbirdTag(msg.id, label);
          console.log(`[Monitor] ✅ Label "${label}" applied to "${msg.subject}"`);
        }
      }
    } else {
      const errText = await resp.text().catch(() => "");
      console.warn(`[Monitor] ⚠️ Server ${resp.status}: ${errText.substring(0, 200)}`);
    }

    await _markMonitorMsgProcessed(msgId);
    return "processed";
  } catch(e) {
    console.error(`[Monitor] ❌ Error for msg ${msgId}: ${e.message}`);
    return "error";
  }
}

// ─── MONITOR PERSISTENCE HELPERS ─────────────────────────────────────────────

async function _isMonitorMsgProcessed(msgId) {
  // ⚡ PERF: Use Set for O(1) instead of array.includes() O(n)
  await _ensureProcessedIdsLoaded();
  return _processedIdsSet.has(msgId);
}

async function _markMonitorMsgProcessed(msgId) {
  // ⚡ PERF: Use Set for O(1) operations
  await _ensureProcessedIdsLoaded();
  
  if (_processedIdsSet.has(msgId)) return;
  
  _processedIdsSet.add(msgId);
  
  // Ring buffer — evict oldest IDs to stay under cap
  const ids = Array.from(_processedIdsSet);
  if (ids.length > MONITOR_MAX_IDS) {
    const trimmed = ids.slice(-MONITOR_MAX_IDS);
    _processedIdsSet = new Set(trimmed);
    try {
      await _safeStorageSet({ [MONITOR_PROCESSED_KEY]: trimmed }, "mark message processed (ring buffer)");
    } catch (e) {
      console.warn(`[Monitor] Could not mark message processed: ${e.message}`);
    }
  } else {
    try {
      await _safeStorageSet({ [MONITOR_PROCESSED_KEY]: ids }, "mark message processed");
    } catch (e) {
      console.warn(`[Monitor] Could not mark message processed: ${e.message}`);
    }
  }
}

// ─── OFFLINE QUEUE HELPERS ───────────────────────────────────────────────────

/**
 * Save message metadata to the offline queue (persisted in storage).
 * Avoids marking the message processed so it can be retried when online.
 */
async function _queueOfflineMessage(msg) {
  const r = await browser.storage.local.get(OFFLINE_QUEUE_KEY);
  let queue = r[OFFLINE_QUEUE_KEY] || [];
  const msgId = String(msg.id);
  // Deduplicate by id
  if (!queue.some(q => q.id === msgId)) {
    queue.push({
      id        : msgId,
      subject   : msg.subject   || "",
      author    : msg.author    || "",
      date      : msg.date      ? new Date(msg.date).toISOString() : null,
      headerMessageId: msg.headerMessageId || null,
      recipients: msg.recipients || []
    });
    // Keep queue bounded to 500 entries
    if (queue.length > 500) queue = queue.slice(-500);
    try {
      await _safeStorageSet({ [OFFLINE_QUEUE_KEY]: queue }, "queue offline message");
    } catch (e) {
      console.warn(`[Monitor] Could not queue offline message: ${e.message}`);
    }
  }
}

/**
 * Drain the offline queue — called when network comes back online.
 * Processes each queued message through the normal labeling pipeline.
 * Entries are removed one-by-one as they succeed or fail.
 */
async function _drainOfflineQueue() {
  if (!navigator.onLine) return;

  const r = await browser.storage.local.get(OFFLINE_QUEUE_KEY);
  const queue = r[OFFLINE_QUEUE_KEY] || [];
  if (!queue.length) return;

  console.log(`[Monitor][OfflineQueue] 🔄 Draining ${queue.length} queued message(s)`);
  const filters = await _getMergedDomainFilters();

  // Work through a snapshot; mutate storage after each item
  for (const item of [...queue]) {
    if (!navigator.onLine) {
      console.log(`[Monitor][OfflineQueue] 📴 Went offline again — stopping drain`);
      break;
    }
    try {
      // Reconstruct a minimal msg object compatible with _processMonitorMessage
      const msg = {
        id              : Number(item.id),
        subject         : item.subject,
        author          : item.author,
        date            : item.date,
        headerMessageId : item.headerMessageId,
        recipients      : item.recipients
      };
      const outcome = await _processMonitorMessage(msg, filters);
      console.log(`[Monitor][OfflineQueue] ${outcome === "processed" ? "✅" : "⊘"} msg ${item.id} "${item.subject}" → ${outcome}`);
    } catch(e) {
      console.warn(`[Monitor][OfflineQueue] ❌ msg ${item.id}: ${e.message}`);
    }
    // Remove this entry from the stored queue regardless of outcome
    const cur = await browser.storage.local.get(OFFLINE_QUEUE_KEY);
    const remaining = (cur[OFFLINE_QUEUE_KEY] || []).filter(q => q.id !== item.id);
    await browser.storage.local.set({ [OFFLINE_QUEUE_KEY]: remaining });
  }
  console.log(`[Monitor][OfflineQueue] ✅ Drain complete`);
}

// ─── STORAGE QUOTA CLEANUP ─────────────────────────────────────────────────────

/**
 * Cleanup stale/old data from storage.local to prevent QuotaExceededError.
 * AGGRESSIVE MODE: Runs immediately and clears maximum data to free space.
 * 
 * Cleans up:
 * - Clear ALL offline queue
 * - Keep only last 20 processed message IDs
 * - Delete completed/failed bulk job states
 * - Clear any old account-specific settings
 */
async function _cleanupStorageQuota() {
  const now = Date.now();
  const allStore = await browser.storage.local.get(null);
  const updates = {};
  let freedBytes = 0;

  try {
    // 1. AGGRESSIVE: Clear entire offline queue (can always reprocess)
    if (allStore[OFFLINE_QUEUE_KEY]) {
      console.log(`[Storage] Clearing offline queue (was ${(allStore[OFFLINE_QUEUE_KEY] || []).length} items)`);
      updates[OFFLINE_QUEUE_KEY] = [];
      freedBytes += JSON.stringify(allStore[OFFLINE_QUEUE_KEY]).length;
    }

    // 2. AGGRESSIVE: Trim processed message IDs to just 20 (minimal tracking)
    if (allStore[MONITOR_PROCESSED_KEY] && Array.isArray(allStore[MONITOR_PROCESSED_KEY])) {
      const ids = allStore[MONITOR_PROCESSED_KEY];
      if (ids.length > 20) {
        const trimmed = ids.slice(-20);
        console.log(`[Storage] Trimmed processed IDs from ${ids.length} to 20`);
        updates[MONITOR_PROCESSED_KEY] = trimmed;
        freedBytes += JSON.stringify(ids).length - JSON.stringify(trimmed).length;
      }
    }

    // 3. Clean bulk job state if exists
    if (allStore.bulk_job_state && allStore.bulk_job_state.status !== "running") {
      console.log(`[Storage] Removed bulk job state`);
      updates.bulk_job_state = null;
      freedBytes += JSON.stringify(allStore.bulk_job_state).length;
    }

    // 4. Remove old account-specific settings (keep only current user_settings)
    for (const key in allStore) {
      if (key.startsWith("user_settings_") && key !== "user_settings") {
        console.log(`[Storage] Removing old account-specific settings: ${key}`);
        updates[key] = null;
        freedBytes += JSON.stringify(allStore[key]).length;
      }
    }

    // 5. Clear bulk_job_abort flag
    if (allStore.bulk_job_abort) {
      updates.bulk_job_abort = null;
      freedBytes += 5;
    }

    // Apply updates
    if (Object.keys(updates).length > 0) {
      // Convert nulls to actual delete operations
      for (const key in updates) {
        if (updates[key] === null) {
          delete updates[key];
        }
      }
      
      if (Object.keys(updates).length > 0) {
        await browser.storage.local.set(updates);
        console.log(`[Storage] ✅ Aggressive cleanup complete | freed ~${Math.round(freedBytes / 1024)}KB`);
      }
    }
  } catch (e) {
    console.error(`[Storage] Cleanup failed: ${e.message}`);
  }
}

/**
 * Schedule periodic storage cleanup (every 6 hours)
 */
let _storageCleanupTimer = null;

function _scheduleStorageCleanup() {
  if (_storageCleanupTimer) clearInterval(_storageCleanupTimer);
  
  _storageCleanupTimer = setInterval(() => {
    console.log(`[Storage] Running scheduled cleanup...`);
    _cleanupStorageQuota().catch(e => console.error("[Storage] Cleanup error:", e.message));
  }, STORAGE_CLEANUP_INTERVAL_MS);

  console.log(`[Storage] Cleanup scheduled every ${STORAGE_CLEANUP_INTERVAL_MS / 1000 / 60 / 60} hours`);
}

/**
 * Safe storage.set wrapper: catches QuotaExceededError, cleans up, and retries once.
 * Use this for ANY critical save operations to prevent quota failures.
 */
async function _safeStorageSet(updates, operation = "save") {
  try {
    await browser.storage.local.set(updates);
  } catch (err) {
    if (err.message && err.message.includes("QuotaExceeded")) {
      console.warn(`[Storage] QuotaExceeded on ${operation} — cleaning up and retrying...`);
      
      // Run aggressive cleanup
      await _cleanupStorageQuota();
      
      // Give cleanup a moment to complete
      await new Promise(r => setTimeout(r, 100));
      
      try {
        // Retry the save
        await browser.storage.local.set(updates);
        console.log(`[Storage] ✅ Retry succeeded after cleanup for ${operation}`);
      } catch (retryErr) {
        console.error(`[Storage] ❌ Retry FAILED even after cleanup: ${retryErr.message}`);
        throw new Error(`Storage quota still exceeded after cleanup: ${retryErr.message}`);
      }
    } else {
      throw err;
    }
  }
}

// ─── LABEL POLL & APPLY (for async /api/label-email-async responses) ─────────

/**
 * Poll /api/job-status/:jobId until done, then apply the returned label as a Thunderbird tag.
 * Mirrors GAS _pollLabelingJob().
 */
async function _pollAndApplyMonitorLabel(messageId, jobId, backendUrl, maxMs = 120000) {
  if (!backendUrl) backendUrl = await getBackendUrl();
  let waited = 0;
  while (waited < maxMs) {
    await new Promise(r => setTimeout(r, 5000));
    waited += 5000;
    try {
      const resp = await fetch(`${backendUrl}/api/job-status/${jobId}`);
      if (resp.ok) {
        const d = await resp.json();
        if (d.status === "done") {
          const label = d.result && (d.result.label || d.result.category);
          if (label) {
            await _applyThunderbirdTag(messageId, label);
            console.log(`[Monitor] ✅ Poll → label="${label}" applied to msg ${messageId}`);
          } else {
            console.log(`[Monitor] ℹ️ Job ${jobId} done but no label returned`);
          }
          return;
        }
        if (d.status === "error") throw new Error("Job error: " + (d.error || "unknown"));
      }
    } catch(e) {
      if (e.message.startsWith("Job error:")) throw e;
      console.warn(`[Monitor][Poll] ${e.message}`);
    }
  }
  throw new Error(`Label poll timeout for job ${jobId} after ${maxMs / 1000}s`);
}

/**
 * Collect all leaf folders from a folder tree (recursively).
 */
function _collectAllFolders(folders) {
  if (!folders) return [];
  const priority = ["inbox", "sent"];
  const result   = [];
  function walk(flist) {
    for (const f of (flist || [])) {
      // Skip trash, junk and drafts to avoid re-indexing noise
      if (["trash","junk","drafts","templates","outbox"].includes((f.type||""))) continue;
      result.push(f);
      walk(f.subFolders);
    }
  }
  // Add priority folders first
  const sorted = [...(folders||[])].sort((a,b) => {
    const ai = priority.indexOf(a.type||"x");
    const bi = priority.indexOf(b.type||"x");
    return (ai===-1?99:ai) - (bi===-1?99:bi);
  });
  walk(sorted);
  return result;
}

// ─── INIT ────────────────────────────────────────────────────────────────────

browser.runtime.onInstalled.addListener(async () => {
  console.log("[OpenMailBot] installed / updated — loading addon_config.json");

  // Load config file (addon-side secrets/defaults)
  const cfg = await getAddonConfig();

  // Seed user_settings if not yet stored, or update agent_url / llm defaults on every reinstall/update
  const r = await browser.storage.local.get(["user_settings", "domain_filters"]);
  if (!r.user_settings) {
    // Fresh install — write full defaults from config
    const defaults = Object.assign({}, DEFAULT_SETTINGS);
    if (cfg.agent_url || cfg.backend_url) defaults.agent_url = cfg.agent_url || cfg.backend_url;
    if (cfg.llm_defaults && cfg.llm_defaults.model)            defaults.llm_model       = cfg.llm_defaults.model;
    if (cfg.llm_defaults && cfg.llm_defaults.embedding_model)  defaults.embedding_model = cfg.llm_defaults.embedding_model;
    await browser.storage.local.set({ user_settings: defaults });
    console.log("[OpenMailBot] user_settings seeded from addon_config.json");
  } else {
    // Reinstall / update — always apply agent_url and llm_defaults from addon_config.json
    const patch = {};
    if (cfg.agent_url || cfg.backend_url) patch.agent_url = cfg.agent_url || cfg.backend_url;
    if (cfg.llm_defaults && cfg.llm_defaults.model)           patch.llm_model       = cfg.llm_defaults.model;
    if (cfg.llm_defaults && cfg.llm_defaults.embedding_model) patch.embedding_model = cfg.llm_defaults.embedding_model;
    if (Object.keys(patch).length) {
      await browser.storage.local.set({ user_settings: Object.assign({}, r.user_settings, patch) });
      console.log("[OpenMailBot] user_settings updated from addon_config.json:", patch);
    }
  }

  // Seed domain_filters from config file if storage is empty
  if (!r.domain_filters || r.domain_filters.length === 0) {
    const cfgDoms  = (cfg.domain_filters && cfg.domain_filters.blocked_domains)  || [];
    const cfgAddrs = (cfg.domain_filters && cfg.domain_filters.blocked_addresses) || [];
    const combined = [...new Set([...cfgDoms, ...cfgAddrs].map(f => f.toLowerCase().trim()).filter(Boolean))];
    if (combined.length > 0) {
      await browser.storage.local.set({ domain_filters: combined });
      console.log("[OpenMailBot] domain_filters seeded from addon_config.json:", combined);
    }
  }

  // Seed process_months from config
  const mp = await browser.storage.local.get("process_last_n_months");
  if (!mp.process_last_n_months) {
    const defMonths = String((cfg.bulk_processing && cfg.bulk_processing.default_months) || 3);
    await browser.storage.local.set({ process_last_n_months: defMonths });
  }

  // Run immediate storage cleanup and schedule recurring cleanup
  _cleanupStorageQuota().catch(e => console.warn("[Storage] Initial cleanup failed:", e.message));
  _scheduleStorageCleanup();

  // FIX: Do NOT call monitorNewEmails() here to avoid duplicate processing
  // It will be called from onStartup instead (which is the proper event for this)
  console.log("[OpenMailBot][Install] ℹ️ Monitor will be started on next Thunderbird startup");
});

// Re-register alarm on every Thunderbird startup (alarms don't persist across restarts in MV2)
// Also run an immediate catch-up to process emails that arrived while the PC was offline/shutdown.
browser.runtime.onStartup.addListener(async () => {
  console.log("[OpenMailBot] startup — checking configuration status");
  
  // Run cleanup and schedule recurring cleanup on startup
  _cleanupStorageQuota().catch(e => console.warn("[Storage] Startup cleanup failed:", e.message));
  _scheduleStorageCleanup();

  // Only start monitor if onboarding is complete and backend URL is configured
  const onboardingCheck = await browser.storage.local.get("onboarding_complete");
  if (onboardingCheck.onboarding_complete) {
    const backendUrl = await getBackendUrl();
    if (backendUrl) {
      _ensureMonitorAlarm();
      console.log("[OpenMailBot][Startup] ▶ Background monitor enabled");
      
      // Immediate catch-up scan — don't wait 1 minute for the first alarm tick
      const r = await browser.storage.local.get(MONITOR_ENABLED_KEY);
      if (r[MONITOR_ENABLED_KEY] !== false) {
        monitorNewEmails().catch(e =>
          console.error("[OpenMailBot][Monitor] Startup catch-up error:", e.message)
        );
      }
    } else {
      console.log("[OpenMailBot][Startup] ⏸ Background monitor not started (no backend URL configured)");
    }
  } else {
    console.log("[OpenMailBot][Startup] ⏸ Background monitor not started (onboarding incomplete)");
  }
});

// ─── ALARM HANDLER (fires every MONITOR_INTERVAL_MINS) ───────────────────────
browser.alarms.onAlarm.addListener(alarm => {
  if (alarm.name === MONITOR_ALARM_NAME) {
    browser.storage.local.get(MONITOR_ENABLED_KEY).then(r => {
      if (r[MONITOR_ENABLED_KEY] === false) {
        console.log("[OpenMailBot][Monitor] Alarm fired but monitor is disabled — skipping");
        return;
      }
      monitorNewEmails().catch(e =>
        console.error("[OpenMailBot][Monitor] Unhandled error in monitorNewEmails:", e.message)
      );
    });
  }
});

// ─── IMMEDIATE NEW-MAIL HOOK ─────────────────────────────────────────────────
// Fires as soon as Thunderbird receives a new message — no need to wait for the next alarm tick.
if (browser.messages && browser.messages.onNewMailReceived) {
  browser.messages.onNewMailReceived.addListener(async (folder, messages) => {
    const r = await browser.storage.local.get(MONITOR_ENABLED_KEY);
    if (r[MONITOR_ENABLED_KEY] === false) {
      console.log("[OpenMailBot][Monitor] onNewMailReceived: monitor disabled — skipping");
      return;
    }
    console.log(`[OpenMailBot][Monitor] onNewMailReceived: ${messages.length} msg(s) in "${folder.name}"`);
    
    // FIX: Resolve account email from the folder's account for correct user_id
    let accountEmail = null;
    if (folder && folder.accountId) {
      try {
        accountEmail = await getAccountEmail(folder.accountId);
        console.log(`[OpenMailBot][Monitor] onNewMailReceived: account email = ${accountEmail}`);
      } catch (e) {
        console.warn(`[OpenMailBot][Monitor] Could not resolve email for folder account:`, e.message);
      }
    }
    
    const filters = await _getMergedDomainFilters();
    for (const msg of messages) {
      await _processMonitorMessage(msg, filters, accountEmail).catch(e =>
        console.warn(`[OpenMailBot][Monitor] processMsg failed (${msg.id}): ${e.message}`)
      );
    }
  });
}

// ─── ONLINE EVENT — drain offline queue when network is restored ─────────────
self.addEventListener("online", () => {
  console.log("[OpenMailBot][Monitor] 🌐 Network back online — draining offline queue");
  _drainOfflineQueue().catch(e => console.warn("[Monitor][online] drainOfflineQueue:", e.message));
});

// ─── MESSAGE ROUTER ──────────────────────────────────────────────────────────

browser.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const msgStartTime = performance.now();
  console.log(`%c[BG-listener] 📨 Message received at ${new Date().toLocaleTimeString('en-US', {hour12:false,hour:'2-digit',minute:'2-digit',second:'2-digit',fractionalSecondDigits:3})} | action: "${message.action}"`, "color:#0066FF;font-weight:bold");

  const handlers = {
    summarizeThread      : () => handleSummarizeThread(message.data),
    draftWithAttachments : () => handleDraftWithAttachments(message.data),
    simpleDraft          : () => handleSimpleDraft(message.data),
    createDraft          : () => handleCreateDraft(message.data),
    chatWithThread       : () => handleChatWithThread(message.data),
    loadSettings         : () => handleLoadSettings(message.data || {}),
    loadSettingsForAccount: () => handleLoadSettingsForAccount(message.data),
    saveSettings         : () => handleSaveSettings(message.data),
    resetSettings        : () => handleResetSettings(),
    syncSettings         : () => handleSyncSettings(message.data || {}),
    fetchSettingsFromBackend: () => handleFetchSettingsFromBackend(message.data),
    checkOnboarding      : () => handleCheckOnboarding(),
    completeOnboarding   : () => handleCompleteOnboarding(message.data),
    getDomainFilters     : () => handleGetDomainFilters(message.data || {}),
    saveDomainFilters    : () => handleSaveDomainFilters(message.data),
    testDomainFilters    : () => handleTestDomainFilters(message.data),
    runBulkProcess       : () => handleRunBulkProcess(message.data),
    getBulkJobStatus     : () => handleGetBulkJobStatus(message.data || {}),
    cancelBulkJob        : () => handleCancelBulkJob(message.data || {}),
    pauseBulkJob         : () => handlePauseBulkJob(message.data || {}),
    resumeBulkJob        : () => handleResumeBulkJob(message.data || {}),
    saveProcessMonths    : () => handleSaveProcessMonths(message.data),
    getProcessMonths     : () => handleGetProcessMonths(message.data || {}),
    getAccountsList      : () => handleGetAccountsList(),
    getAccountEmail      : () => handleGetAccountEmail(message.data),
    getMonitorEnabled    : () => handleGetMonitorEnabled(message.data || {}),
    setMonitorEnabled    : () => handleSetMonitorEnabled(message.data || {})
  };

  const fn = handlers[message.action];
  if (!fn) { 
    console.error(`%c[BG-listener] ❌ Unknown action: ${message.action}`, "color:#CC0000");
    sendResponse({ error: "Unknown action: " + message.action }); 
    return false; 
  }
  
  fn().then(result => {
    const duration = (performance.now() - msgStartTime).toFixed(0);
    console.log(`%c[BG-listener] ✅ Handler "${message.action}" completed in ${duration}ms, sending response`, "color:#0066FF;font-weight:bold");
    sendResponse(result);
  }).catch(e => {
    const duration = (performance.now() - msgStartTime).toFixed(0);
    console.error(`%c[BG-listener] ❌ Handler "${message.action}" failed after ${duration}ms: ${e.message}`, "color:#CC0000;font-weight:bold");
    sendResponse({ error: e.message });
  });
  return true;
});

// ─── THREAD HELPERS ──────────────────────────────────────────────────────────────────

// ── CACHE FOR THREAD RESULTS (to avoid re-fetching same thread) ──────────
let _threadMessageCache = {};
const CACHE_EXPIRY_MS = 60000; // Cache for 60 seconds

/**
 * Generate a synthetic threadId based on subject line and earliest date
 * Used when Thunderbird doesn't provide a native threadId
 */
function generateSyntheticThreadId(subject, date) {
  const normalized = (subject || "").replace(/^(Re|Fwd?|AW|WG):\s*/gi,"").trim().toLowerCase();
  const dateKey = date ? new Date(date).toISOString().split('T')[0] : "unknown";
  const hash = normalized.split('').reduce((a, c) => ((a << 5) - a) + c.charCodeAt(0), 0).toString(16);
  const syntheticId = `synthetic_${hash}_${dateKey}`;
  return syntheticId;
}

/**
 * Get all messages in the same thread (subject-based, full thread).
 * Returns array of { meta, full } objects sorted oldest-first.
 */
async function getThreadMessages(messageId) {
  const funcStartTime = performance.now();
  console.log(`%c[getThreadMessages] ▶️  Fetching messages for ID: ${messageId} | 💾 cache size: ${Object.keys(_threadMessageCache).length}`, "color:#9900CC;font-weight:bold");
  
  try {
    const msg = await browser.messages.get(messageId);
    console.log(`%c[getThreadMessages] ✓ Got initial message | threadId: ${msg.threadId || '(empty)'} | subject: ${msg.subject}`, "color:#9900CC");

    // ─ DIAGNOSTIC: Why is threadId missing? ────────────────────────────────
    if (!msg.threadId) {
      console.log(`%c[getThreadMessages] 🔍 DIAGNOSTIC: threadId is EMPTY - investigating...`, "color:#FF6B00;font-weight:bold;font-size:11px");
      console.log(`%c[getThreadMessages]   • Folder type: ${msg.folder?.type || 'unknown'}`, "color:#FF6B00;font-size:11px");
      console.log(`%c[getThreadMessages]   • Account type: ${msg.folder?.accountId || 'unknown'}`, "color:#FF6B00;font-size:11px");
      console.log(`%c[getThreadMessages]   • API available: ${typeof browser.messages.query === 'function' ? 'YES' : 'NO'}`, "color:#FF6B00;font-size:11px");
      
      // Generate synthetic threadId as workaround
      const syntheticId = generateSyntheticThreadId(msg.subject, msg.date);
      console.log(`%c[getThreadMessages]   ✨ Generated synthetic threadId: ${syntheticId}`, "color:#FF6B00;font-size:11px");
    }

    // ── CACHE CHECK: Return cached result if available (within 60s expiry) ────
    if (msg.threadId && _threadMessageCache[msg.threadId]) {
      const cached = _threadMessageCache[msg.threadId];
      const ageMs = performance.now() - cached.timestamp;
      if (ageMs < CACHE_EXPIRY_MS) {
        console.log(`%c[getThreadMessages] 💾 CACHE HIT (${ageMs.toFixed(0)}ms old): ${cached.messages.length} messages — SAVES TIME!`, "color:#00CC00;font-weight:bold;font-size:12px");
        return cached.messages;
      } else {
        console.log(`%c[getThreadMessages] 💾 CACHE EXPIRED (${ageMs.toFixed(0)}ms old), fetching fresh`, "color:#FF9900");
        delete _threadMessageCache[msg.threadId];
      }
    }

    // ── Fast path: use native threadId query (Thunderbird 121+) ──────────
    // Avoids listing the entire folder (O(n) messages) and filtering by subject.
    if (msg.threadId && typeof browser.messages.query === "function") {
      console.log(`%c[getThreadMessages] 🚀 Fast path: Using native threadId query (Thunderbird 121+)`, "color:#9900CC;font-weight:bold");
      try {
        const t0 = performance.now();
        const page = await browser.messages.query({ threadId: msg.threadId });
        console.log(`%c[getThreadMessages]   Query returned: ${page.messages?.length || 0} messages in ${(performance.now()-t0).toFixed(0)}ms`, "color:#9900CC");
        
        const threadMsgs = (page && page.messages && page.messages.length > 0)
          ? page.messages : null;
        if (threadMsgs) {
          const sorted = threadMsgs
            .sort((a, b) => new Date(a.date) - new Date(b.date))
            .slice(0, 30);
          console.log(`%c[getThreadMessages]   Sorted & sliced to ${sorted.length} messages`, "color:#9900CC");
          
          const getFFullStartTime = performance.now();
          const results = await Promise.all(sorted.map(async m => {
            try { return { meta: m, full: await browser.messages.getFull(m.id) }; }
            catch (e) { console.warn(`%c[getThreadMessages]   ⚠️  getFull failed for ${m.id}: ${e.message}`, "color:#FF9900"); return null; }
          }));
          console.log(`%c[getThreadMessages]   getFull() on ${sorted.length} msgs took ${(performance.now()-getFFullStartTime).toFixed(0)}ms`, "color:#9900CC");
          
          const filtered = results.filter(Boolean);
          
          // 💾 CACHE the result for this thread to avoid re-fetching
          if (msg.threadId) {
            _threadMessageCache[msg.threadId] = { messages: filtered, timestamp: performance.now() };
            console.log(`%c[getThreadMessages]   💾 Cached ${filtered.length} messages for thread: ${msg.threadId}`, "color:#00AA00;font-size:11px");
          }
          
          const funcDuration = (performance.now()-funcStartTime).toFixed(0);
          console.log(`%c[getThreadMessages] ✅ Fast path complete: ${filtered.length} msgs in ${funcDuration}ms`, "color:#00AA00;font-weight:bold");
          return filtered;
        }
      } catch (e) {
        const fallbackTime = (performance.now()-funcStartTime).toFixed(0);
        console.warn(`%c[getThreadMessages] ⚠️  Fast path failed after ${fallbackTime}ms: ${e.message}, falling back to slow path...`, "color:#FF9900");
      }
    } else {
      console.log(`%c[getThreadMessages] 🐢 No native threadId available`, "color:#FF9900;font-weight:bold");
    }

    // ─────────────────────────────────────────────────────────────────────────
    // ✨ 3-STRATEGY SEARCH ENGINE: FASTEST FIRST (Early Exit on Match)
    // ─────────────────────────────────────────────────────────────────────────
    
    const norm = s => (s||"").replace(/^(Re|Fwd?|AW|WG):\s*/gi,"").trim().toLowerCase();
    const baseSubject = norm(msg.subject);
    const senderEmail = msg.author || msg.from || "";
    
    console.log(`%c[getThreadMessages] 🚀 3-STRATEGY INTELLIGENT SEARCH (Fastest First)`, "color:#0066FF;font-weight:bold;font-size:12px");
    console.log(`%c[getThreadMessages]   • Sender: ${senderEmail || "unknown"}`, "color:#0066FF;font-size:10px");
    console.log(`%c[getThreadMessages]   • Subject: "${baseSubject}"`, "color:#0066FF;font-size:10px");
    
    let results = [];
    const searchStartTime = performance.now();
    
    // ─────────────────────────────────────────────────────────────────────────
    // STRATEGY 1: threadId Query (<10ms)
    // ─────────────────────────────────────────────────────────────────────────
    if (msg.threadId && typeof browser.messages.query === "function") {
      try {
        const t = performance.now();
        const queryResult = await browser.messages.query({ threadId: msg.threadId });
        
        if (queryResult.messages && queryResult.messages.length > 0) {
          console.log(`%c[getThreadMessages] ✅ STRATEGY 1 ✓ threadId: ${queryResult.messages.length} msgs in ${(performance.now()-t).toFixed(0)}ms`, "color:#00AA00;font-weight:bold;font-size:11px");
          const sorted = queryResult.messages.sort((a, b) => new Date(a.date) - new Date(b.date)).slice(0, 30);
          const getFFullStartTime = performance.now();
          results = (await Promise.all(sorted.map(async m => {
            try { return { meta: m, full: await browser.messages.getFull(m.id) }; }
            catch(e) { console.warn(`%c[getThreadMessages]     ⚠️  getFull failed for ${m.id}`, "color:#FF9900"); return null; }
          }))).filter(Boolean);
          console.log(`%c[getThreadMessages]   getFull() took ${(performance.now()-getFFullStartTime).toFixed(0)}ms`, "color:#0066FF;font-size:9px");
          const syntheticId = generateSyntheticThreadId(msg.subject, msg.date);
          _threadMessageCache[syntheticId] = { messages: results, timestamp: performance.now() };
          const funcDuration = (performance.now()-funcStartTime).toFixed(0);
          console.log(`%c[getThreadMessages] ✨ RESULT: ${results.length} msgs in ${funcDuration}ms (Strategy 1)`, "color:#00AA00;font-weight:bold");
          return results;
        }
      } catch (e) {
        console.warn(`%c[getThreadMessages] ⚠️  STRATEGY 1 failed: ${e.message}`, "color:#FF9900;font-size:10px");
      }
    }
    
    // ─────────────────────────────────────────────────────────────────────────
    // STRATEGY 2: from + subject (<50ms)
    // ─────────────────────────────────────────────────────────────────────────
    if (typeof browser.messages.query === "function" && senderEmail && baseSubject) {
      try {
        const t = performance.now();
        const queryResult = await browser.messages.query({ from: senderEmail, subject: baseSubject });
        
        if (queryResult.messages && queryResult.messages.length > 0) {
          console.log(`%c[getThreadMessages] ✅ STRATEGY 2 ✓ from+subject: ${queryResult.messages.length} msgs in ${(performance.now()-t).toFixed(0)}ms`, "color:#00AA00;font-weight:bold;font-size:11px");
          const sorted = queryResult.messages.sort((a, b) => new Date(a.date) - new Date(b.date)).slice(0, 30);
          const getFFullStartTime = performance.now();
          results = (await Promise.all(sorted.map(async m => {
            try { return { meta: m, full: await browser.messages.getFull(m.id) }; }
            catch(e) { console.warn(`%c[getThreadMessages]     ⚠️  getFull failed for ${m.id}`, "color:#FF9900"); return null; }
          }))).filter(Boolean);
          console.log(`%c[getThreadMessages]   getFull() took ${(performance.now()-getFFullStartTime).toFixed(0)}ms`, "color:#0066FF;font-size:9px");
          const syntheticId = generateSyntheticThreadId(msg.subject, msg.date);
          _threadMessageCache[syntheticId] = { messages: results, timestamp: performance.now() };
          const funcDuration = (performance.now()-funcStartTime).toFixed(0);
          console.log(`%c[getThreadMessages] ✨ RESULT: ${results.length} msgs in ${funcDuration}ms (Strategy 2)`, "color:#00AA00;font-weight:bold");
          return results;
        } else {
          console.log(`%c[getThreadMessages] ℹ️  STRATEGY 2: 0 results, trying Strategy 3...`, "color:#FF9900;font-size:10px");
        }
      } catch (e) {
        console.warn(`%c[getThreadMessages] ⚠️  STRATEGY 2 failed: ${e.message}`, "color:#FF9900;font-size:10px");
      }
    }
    
    // ─────────────────────────────────────────────────────────────────────────
    // STRATEGY 3: subject only (<100ms)
    // ─────────────────────────────────────────────────────────────────────────
    if (typeof browser.messages.query === "function" && baseSubject) {
      try {
        const t = performance.now();
        const queryResult = await browser.messages.query({ subject: baseSubject });
        
        if (queryResult.messages && queryResult.messages.length > 0) {
          console.log(`%c[getThreadMessages] ✅ STRATEGY 3 ✓ subject: ${queryResult.messages.length} msgs in ${(performance.now()-t).toFixed(0)}ms`, "color:#00AA00;font-weight:bold;font-size:11px");
          const sorted = queryResult.messages.sort((a, b) => new Date(a.date) - new Date(b.date)).slice(0, 30);
          const getFFullStartTime = performance.now();
          results = (await Promise.all(sorted.map(async m => {
            try { return { meta: m, full: await browser.messages.getFull(m.id) }; }
            catch(e) { console.warn(`%c[getThreadMessages]     ⚠️  getFull failed for ${m.id}`, "color:#FF9900"); return null; }
          }))).filter(Boolean);
          console.log(`%c[getThreadMessages]   getFull() took ${(performance.now()-getFFullStartTime).toFixed(0)}ms`, "color:#0066FF;font-size:9px");
          const syntheticId = generateSyntheticThreadId(msg.subject, msg.date);
          _threadMessageCache[syntheticId] = { messages: results, timestamp: performance.now() };
          const funcDuration = (performance.now()-funcStartTime).toFixed(0);
          console.log(`%c[getThreadMessages] ✨ RESULT: ${results.length} msgs in ${funcDuration}ms (Strategy 3)`, "color:#00AA00;font-weight:bold");
          return results;
        } else {
          console.log(`%c[getThreadMessages] ℹ️  STRATEGY 3: 0 results, using fallback folder scan...`, "color:#FF9900;font-size:10px");
        }
      } catch (e) {
        console.warn(`%c[getThreadMessages] ⚠️  STRATEGY 3 failed: ${e.message}`, "color:#FF9900;font-size:10px");
      }
    }
    
    // ─────────────────────────────────────────────────────────────────────────
    // FALLBACK: Limited folder scan (Early exit on match, max 500 messages)
    // ─────────────────────────────────────────────────────────────────────────
    console.log(`%c[getThreadMessages] 🔍 FALLBACK: Limited folder scan with early exit...`, "color:#FF6600;font-weight:bold;font-size:11px");
    
    const folder = msg.folder;
    if (!folder) {
      console.log(`%c[getThreadMessages]   ⚠️  No folder found, returning original message only`, "color:#FF9900");
      return [{ meta: msg, full: await browser.messages.getFull(messageId) }];
    }
    
    const listStartTime = performance.now();
    let allMsgs = [];
    let page = await browser.messages.list(folder);
    let pageCount = 0;
    const MAX_MSGS_TO_SCAN = 500; // Early exit after 500 messages
    let foundMatch = false;
    
    while (page && allMsgs.length < MAX_MSGS_TO_SCAN && !foundMatch) {
      pageCount++;
      const msgCount = (page.messages || []).length;
      allMsgs = allMsgs.concat(page.messages || []);
      
      // Early exit check: Do we have a match yet?
      const quickCheck = allMsgs.filter(m => norm(m.subject) === baseSubject);
      if (quickCheck.length > 0) {
        console.log(`%c[getThreadMessages]   ✅ Match found on page ${pageCount}! Stopping scan early.`, "color:#00AA00;font-weight:bold;font-size:10px");
        foundMatch = true;
        break;
      }
      
      const elapsedMs = performance.now() - listStartTime;
      console.log(`%c[getThreadMessages]   Page ${pageCount}: ${msgCount} msgs (total: ${allMsgs.length}, ${elapsedMs.toFixed(0)}ms)`, "color:#FF6600;font-size:9px");
      
      if (page.id && allMsgs.length < MAX_MSGS_TO_SCAN) { 
        page = await browser.messages.continueList(page.id); 
      } else { 
        break; 
      }
    }
    
    const scanDuration = (performance.now()-listStartTime).toFixed(0);
    console.log(`%c[getThreadMessages]   📊 Scanned ${allMsgs.length} messages in ${pageCount} pages (${scanDuration}ms)`, "color:#FF6600;font-size:10px");
    
    // Now find matching messages by subject
    const filterStartTime = performance.now();
    let thread = [];
    
    // Step 1: Try exact ID match
    thread = allMsgs.filter(m => m.id===messageId || String(m.id)===String(messageId));
    
    // Step 2: Try exact subject match
    if (thread.length === 0) {
      thread = allMsgs.filter(m => norm(m.subject)===baseSubject);
      console.log(`%c[getThreadMessages]   📊 Exact subject match: ${thread.length} found`, "color:#FF6600;font-size:9px");
    }
    
    // Step 3: Try flexible matching
    if (thread.length === 0) {
      const baseWords = baseSubject.split(/\s+/).filter(w => w.length > 2);
      if (baseWords.length > 0) {
        thread = allMsgs.filter(m => {
          const normMsgSubj = norm(m.subject);
          const wordMatches = baseWords.filter(w => normMsgSubj.includes(w)).length;
          const minKeywords = Math.max(1, Math.ceil(baseWords.length * 0.5));
          return wordMatches >= minKeywords;
        });
        console.log(`%c[getThreadMessages]   📊 Flexible keywords: ${thread.length} found`, "color:#FF6600;font-size:9px");
      }
    }
    
    // Sort and limit
    thread = thread
      .sort((a,b) => new Date(a.date)-new Date(b.date))
      .slice(0,30);
    
    console.log(`%c[getThreadMessages]   ✅ FALLBACK: Found ${thread.length} messages in ${(performance.now()-filterStartTime).toFixed(0)}ms`, "color:#FF6600;font-size:10px");
    
    // Ensure we always return at least the original message
    if (thread.length === 0) {
      console.log(`%c[getThreadMessages]   ⚠️  No matches found in folder, returning original message`, "color:#FF9900;font-size:11px");
      thread = [msg];
    }
    
    // Get full message bodies
    const getFFullStartTime = performance.now();
    const fullResults = await Promise.all(thread.map(async m => {
      try { 
        return { meta: m, full: await browser.messages.getFull(m.id) }; 
      } catch(e) { 
        console.warn(`%c[getThreadMessages]   ⚠️  getFull failed for ${m.id}: ${e.message}`, "color:#FF9900"); 
        return null; 
      }
    }));
    console.log(`%c[getThreadMessages]   getFull() on ${thread.length} msgs took ${(performance.now()-getFFullStartTime).toFixed(0)}ms`, "color:#FF9900");
    
    results = fullResults.filter(Boolean);
    
    // 💾 CACHE using synthetic threadId
    const cacheId = generateSyntheticThreadId(msg.subject, msg.date);
    _threadMessageCache[cacheId] = { messages: results, timestamp: performance.now() };
    console.log(`%c[getThreadMessages]   💾 Cached ${results.length} messages`, "color:#FF6600;font-size:10px");
    
    const funcDuration = (performance.now()-funcStartTime).toFixed(0);
    console.log(`%c[getThreadMessages] ✨ RESULT: ${results.length} msgs in ${funcDuration}ms (FALLBACK folder scan)`, "color:#00AA00;font-weight:bold");
    return results;
  } catch(e) {
    const funcDuration = (performance.now()-funcStartTime).toFixed(0);
    console.error(`%c[getThreadMessages] ❌ Exception after ${funcDuration}ms: ${e.message}`, "color:#CC0000");
    const msg  = await browser.messages.get(messageId);
    const full = await browser.messages.getFull(messageId);
    return [{ meta: msg, full }];
  }
}

function buildThreadText(items) {
  return items.map(({meta,full}) =>
    `From: ${meta.author||"Unknown"}\nDate: ${meta.date?new Date(meta.date).toISOString():""}\nSubject: ${meta.subject||""}\n\n${extractPlainText(full)}`
  ).join("\n\n---\n\n");
}

/**
 * Extract plain text from message parts
 */
function extractPlainText(messagePart) {
  let text = "";
  
  if (messagePart.body) {
    text += messagePart.body;
  }
  
  if (messagePart.parts) {
    for (const part of messagePart.parts) {
      if (part.contentType === "text/plain") {
        text += part.body || "";
      } else if (part.parts) {
        text += extractPlainText(part);
      }
    }
  }
  
  return text;
}

// ─── FEATURE HANDLERS ─────────────────────────────────────────────────────────────

async function handleSummarizeThread({ messageId, accountId, userEmail }) {
  const bgStartTime = performance.now();
  console.log(`%c[BG] ▶️  handleSummarizeThread RECEIVED at ${new Date().toLocaleTimeString('en-US', {hour12:false,hour:'2-digit',minute:'2-digit',second:'2-digit',fractionalSecondDigits:3})}`, "color:#0066FF;font-weight:bold;font-size:12px");
  console.log(`%c  messageId: ${messageId} | accountId: ${accountId} | userEmail: ${userEmail}`, "color:#0066FF");
  
  // ⚡ PERF: Wrap with _queuedRequest to prevent duplicate requests from rapid clicks
  return _queuedRequest(`summarize_${messageId}`, async () => {
    const _t0 = performance.now();

    // ── Resolve userId, backendUrl and thread messages IN PARALLEL ───────────
    // Previously these ran sequentially (userId → backendUrl → getThreadMessages)
    // costing 1-3 s before any data was sent.
    console.log(`%c[BG] ⚙️  Starting parallel init (userId, backendUrl, getThreadMessages)...`, "color:#0066FF");
    const parallelStartTime = performance.now();
    
    const [resolvedEmail, backendUrl, items] = await Promise.all([
    // 1. User email resolution
    userEmail
      ? (console.log(`%c  [1/3] Using provided userEmail: ${userEmail}`, "color:#0066FF"), Promise.resolve(userEmail))
      : (console.log(`%c  [1/3] Resolving user email from message...`, "color:#0066FF"), 
         getAccountEmailFromMessage(messageId)
          .then(e => (console.log(`%c    → Got email: ${e}`, "color:#0066FF"), e || getUserId(messageId)))),
    // 2. Backend URL (storage read)
    (console.log(`%c  [2/3] Fetching backend URL from storage...`, "color:#0066FF"), getBackendUrl().then(url => (console.log(`%c    → Backend URL: ${url}`, "color:#0066FF"), url))),
    // 3. Fetch thread messages (may use fast threadId path)
    (console.log(`%c  [3/3] Fetching thread messages...`, "color:#0066FF"), getThreadMessages(messageId).then(m => (console.log(`%c    → Got ${m.length} messages`, "color:#0066FF"), m))),
  ]);
    
    const parallelDuration = (performance.now() - parallelStartTime).toFixed(0);
    console.log(`%c[BG] ✅ Parallel init completed in ${parallelDuration}ms (total: ${(performance.now()-_t0).toFixed(0)}ms)`, "color:#0066FF;font-weight:bold");

    const userId = resolvedEmail;
    console.log(`%c[BG] ⚡ Init complete — user=${userId} | backend=${backendUrl}`, "color:#0066FF");

    const threadText = buildThreadText(items);
    const firstMeta  = items[0].meta;
    const threadId   = _getCanonicalThreadId(firstMeta, items[0].full);

    // 1. Log all thread emails to server (so vector store is up-to-date) — MUST finish before summarize
    console.log(`%c[BG] 📤 Step 1: Logging ${items.length} emails to server for thread ${threadId}...`, "color:#0066FF");
    const logStartTime = performance.now();
    try { 
      await _logEmailsToServer(backendUrl, userId, threadId, items.map(({meta,full})=>_fmtMsg(meta,full))); 
      const logDuration = (performance.now() - logStartTime).toFixed(0);
      console.log(`%c[BG] ✅ Logged emails in ${logDuration}ms (total: ${(performance.now()-_t0).toFixed(0)}ms)`, "color:#00AA00");
    }
    catch(e) { 
      const logDuration = (performance.now() - logStartTime).toFixed(0);
      console.warn(`%c[BG] ⚠️  Log emails failed after ${logDuration}ms: ${e.message}`, "color:#FF9900"); 
    }

    console.log(`%c[BG] 📤 Step 2: Firing summarization request (total: ${(performance.now()-_t0).toFixed(0)}ms)...`, "color:#0066FF");

    // 2. Store attachments in BACKGROUND — does NOT block the summarize request
    (async () => {
      console.log(`%c[BG] 📎 Background: Starting attachment storage (non-blocking)...`, "color:#0066FF");
      for (const {meta} of items) {
        try { 
          const a=await _getAttachments(meta.id); 
          if(a.length) {
            await _storeAtts(backendUrl,userId,threadId,String(meta.id),a);
            console.log(`%c[BG] 📎 Stored ${a.length} attachment(s) for message ${meta.id}`, "color:#0066FF");
          }
        }
        catch(e) { console.warn(`%c[BG] ⚠️  Attachment storage failed: ${e.message}`, "color:#FF9900"); }
      }
    })();

    // 3. Try server-side RAG summarization (/api/summarize-thread uses indexed content)
    let summary;
    console.log(`%c[BG] 📡 Step 3: Calling /api/summarize-thread (${backendUrl}/api/summarize-thread)...`, "color:#0066FF");
    const ragStartTime = performance.now();
    try {
      const resp = await fetch(`${backendUrl}/api/summarize-thread`, {
        method : "POST",
        headers: { "Content-Type": "application/json" },
        body   : JSON.stringify({ user_id: userId, thread_id: threadId })
      });
      const ragDuration = (performance.now() - ragStartTime).toFixed(0);
      console.log(`%c[BG]   Response status: ${resp.status} ${resp.statusText} (${ragDuration}ms)`, "color:#0066FF");
      
      if (resp.ok) {
        const data = await resp.json();
        console.log(`%c[BG]   Response has job_id: ${!!data.job_id} | direct summary: ${!!(data.summary || data.response || data.answer)}`, "color:#0066FF");
        
        const result = data.job_id ? await _pollJobStatus(data.job_id) : data;
        summary = result.summary || result.response || result.answer;
        if (summary) {
          const totalTime = (performance.now()-_t0).toFixed(0);
          console.log(`%c[BG] ✅ RAG summary received: ${summary.length} chars in ${totalTime}ms`, "color:#00AA00;font-weight:bold");
        }
      }
    } catch(e) {
      const ragDuration = (performance.now() - ragStartTime).toFixed(0);
      console.warn(`%c[BG] ⚠️  /api/summarize-thread failed after ${ragDuration}ms: ${e.message}, falling back to /chat...`, "color:#FF9900");
    }

    // 4. Fallback: client-side prompt sent to /chat
    if (!summary) {
      console.log(`%c[BG] 📡 Step 4: Using fallback /chat API (total: ${(performance.now()-_t0).toFixed(0)}ms)...`, "color:#FF9900");
      const fallbackStartTime = performance.now();
      try {
        summary = await callFlaskAPI(threadText, "summarize");
        const fallbackDuration = (performance.now() - fallbackStartTime).toFixed(0);
        console.log(`%c[BG] ✅ Fallback /chat completed: ${summary.length} chars in ${fallbackDuration}ms`, "color:#FF9900;font-weight:bold");
      } catch(e) {
        const fallbackDuration = (performance.now() - fallbackStartTime).toFixed(0);
        console.error(`%c[BG] ❌ /chat fallback failed after ${fallbackDuration}ms: ${e.message}`, "color:#CC0000");
        throw e;
      }
    }

    const totalDuration = (performance.now()-_t0).toFixed(0);
    console.log(`%c[BG] 🏁 handleSummarizeThread COMPLETE in ${totalDuration}ms | summary: ${(summary || "").length} chars`, "color:#0066FF;font-weight:bold;font-size:12px");
    return { success: true, summary, threadId, messageId };
  });
}

async function handleCreateDraft({ messageId, summary, accountId, userEmail }) {
  const prefs  = await getUserPreferences(userEmail);
  const prompt = [
    "### Draft Response Email",
    `I am ${prefs.name} (${prefs.position}).`,
    `Write a ${prefs.tone} email response that:`,
    "- Acknowledges the current status",
    "- Restates pending actions",
    "- Requests the next expected step",
    "- Does NOT introduce new information",
    "",
    "Email format only. No explanations.",
    prefs.custom_instructions ? `\nAdditional instructions: ${prefs.custom_instructions}` : "",
    "",
    "Summary:", summary
  ].join("\n");
  const draftContent = await callFlaskAPI(prompt, "draft");
  const msg     = await browser.messages.get(messageId);
  const subject = msg.subject.match(/^Re:/i) ? msg.subject : `Re: ${msg.subject}`;
  await browser.compose.beginNew({ to:[msg.author], subject, plainTextBody:draftContent, isPlainText:true });
  return { success: true, draftContent };
}

async function handleDraftWithAttachments({ messageId, accountId, userEmail }) {
  // ⚡ PERF: Wrap with _queuedRequest to prevent duplicate requests from rapid clicks
  return _queuedRequest(`draft_${messageId}`, async () => {
    const _t0 = performance.now();

    // ── Parallel init: userId + backendUrl + thread messages ─────────────────
    const [resolvedEmail, backendUrl, items] = await Promise.all([
    userEmail
      ? Promise.resolve(userEmail)
      : getAccountEmailFromMessage(messageId).then(e => e || getUserId(messageId)),
    getBackendUrl(),
    getThreadMessages(messageId),
  ]);
  const userId   = resolvedEmail;
  const firstMeta = items[0].meta;
  const threadId  = _getCanonicalThreadId(firstMeta, items[0].full);
  console.log(`[DraftWithAttachments] ⚡ Init in ${(performance.now()-_t0).toFixed(0)}ms — user=${userId}`);

  // Log thread + fetch prefs + draft font in parallel
  const [, prefs, draftFont] = await Promise.all([
    _logEmailsToServer(backendUrl, userId, threadId, items.map(({meta,full})=>_fmtMsg(meta,full)))
      .catch(e => console.warn("logEmail:", e.message)),
    getUserPreferences(userId),
    (async () => { const r = await browser.storage.local.get("user_settings"); return (r.user_settings?.draft_font || "arial"); })(),
  ]);

  // Store attachments in parallel with the draft API call
  // (server pipeline reads from vector DB which may already have them from previous sessions)
  let totalAtts = 0;
  const attStorePromise = (async () => {
    for (const {meta} of items) {
      try {
        const a = await _getAttachments(meta.id);
        if (a.length) {
          totalAtts += a.length;
          await _storeAtts(backendUrl, userId, threadId, String(meta.id), a);
          console.log(`[DraftAtts] ✅ Stored ${a.length} att(s) for msg ${meta.id}`);
        }
      } catch(e) { console.warn("[DraftAtts] storeAtts:", e.message); }
    }
  })();

  console.log(`[DraftWithAttachments] ⚡ Firing pipeline at ${(performance.now()-_t0).toFixed(0)}ms`);
  const [result] = await Promise.all([
    callPipelineAPI({ user_id:userId, thread_id:threadId, message_id:String(messageId), user_preferences:prefs }),
    attStorePromise,
  ]);

  const draftContent   = result.draft_content || result.response || "No draft content received";
  const processingInfo = result.processing_info || {};
  const lastMeta       = items[items.length-1].meta;
  const subject        = lastMeta.subject.match(/^Re:/i) ? lastMeta.subject : `Re: ${lastMeta.subject}`;

  // Map font value to CSS font-family
  const fontFamilyMap = {
    "arial": "Arial, sans-serif",
    "times-new-roman": "'Times New Roman', serif",
    "courier-new": "'Courier New', monospace",
    "georgia": "Georgia, serif",
    "verdana": "Verdana, sans-serif",
    "impact": "Impact, sans-serif",
    "papyrus": "Papyrus, cursive",
    "comic-sans": "'Comic Sans MS', cursive"
  };
  const fontFamily = fontFamilyMap[draftFont] || "Arial, sans-serif";
  
  // Note: Thunderbird's compose.beginNew() API only supports plainTextBody
  // To apply font, we'll store the font preference and embed it as a comment
  // Users must format the message manually or Thunderbird must support HTML composition
  const draftWithFontInfo = `<html><body style="font-family: ${fontFamily};">${draftContent.replace(/\n/g, '<br>')}</body></html>`;
  
  console.log(`[DraftWithAttachments] Font selected: ${draftFont} -> ${fontFamily}`);
  
  // Use plainTextBody as that's what Thunderbird API supports
  // Prepend font info so user knows which font should be used
  const annotatedDraft = `[Using font: ${draftFont}]\n\n${draftContent}`;
  await browser.compose.beginNew({ to:[lastMeta.author], subject, plainTextBody:annotatedDraft, isPlainText:true });
  
    return { success:true, draftContent, processingInfo, attachmentCount:totalAtts, selectedFont:draftFont, fontInfo: `${draftFont} (${fontFamily})` };
  });
}

async function handleSimpleDraft({ messageId, accountId, userEmail }) {
  // ⚡ PERF: Wrap with _queuedRequest to prevent duplicate requests from rapid clicks
  return _queuedRequest(`simple_draft_${messageId}`, async () => {
    const _t0 = performance.now();

    // ── Parallel init ────────────────────────────────────────────────────────
    const [resolvedEmail, backendUrl, items] = await Promise.all([
    userEmail
      ? Promise.resolve(userEmail)
      : getAccountEmailFromMessage(messageId).then(e => e || getUserId(messageId)),
    getBackendUrl(),
    getThreadMessages(messageId),
  ]);
  const userId    = resolvedEmail;
  const firstMeta = items[0].meta;
  const threadId  = _getCanonicalThreadId(firstMeta, items[0].full);
  console.log(`[SimpleDraft] ⚡ Init in ${(performance.now()-_t0).toFixed(0)}ms — user=${userId}`);

  // Log emails + fetch prefs + draft font in parallel, then call draft API
  const [, prefs, draftFont] = await Promise.all([
    _logEmailsToServer(backendUrl, userId, threadId, items.map(({meta, full}) => _fmtMsg(meta, full)))
      .catch(e => console.warn("[SimpleDraft] logEmail:", e.message)),
    getUserPreferences(userId),
    (async () => { const r = await browser.storage.local.get("user_settings"); return (r.user_settings?.draft_font || "arial"); })(),
  ]);

  console.log(`[SimpleDraft] ⚡ Firing draft API at ${(performance.now()-_t0).toFixed(0)}ms`);
  // Call /api/draft (simple draft, no attachment context)
  const resp = await fetch(`${backendUrl}/api/draft`, {
    method : "POST",
    headers: { "Content-Type": "application/json" },
    body   : JSON.stringify({ user_id: userId, thread_id: threadId, user_preferences: prefs })
  });
  if (!resp.ok) { const t = await resp.text(); throw new Error(`Draft API (${resp.status}): ${t}`); }
  const initial = await resp.json();
  const result  = initial.job_id ? await _pollJobStatus(initial.job_id) : initial;

  const draftContent = result.draft_content || result.response || "No draft content received";
  const lastMeta     = items[items.length - 1].meta;
  const subject      = lastMeta.subject.match(/^Re:/i) ? lastMeta.subject : `Re: ${lastMeta.subject}`;
  
  // Map font value to CSS font-family
  const fontFamilyMap = {
    "arial": "Arial, sans-serif",
    "times-new-roman": "'Times New Roman', serif",
    "courier-new": "'Courier New', monospace",
    "georgia": "Georgia, serif",
    "verdana": "Verdana, sans-serif",
    "impact": "Impact, sans-serif",
    "papyrus": "Papyrus, cursive",
    "comic-sans": "'Comic Sans MS', cursive"
  };
  const fontFamily = fontFamilyMap[draftFont] || "Arial, sans-serif";
  
  // Note: Thunderbird's compose.beginNew() API only supports plainTextBody
  // Prepend font info so user knows which font should be used
  const annotatedDraft = `[Using font: ${draftFont}]\n\n${draftContent}`;
  
  console.log(`[SimpleDraft] Font selected: ${draftFont} -> ${fontFamily}`);
  
    await browser.compose.beginNew({ to: [lastMeta.author], subject, plainTextBody: annotatedDraft, isPlainText: true });
    return { success: true, draftContent, selectedFont: draftFont, fontInfo: `${draftFont} (${fontFamily})` };
  });
}

async function handleChatWithThread({ messageId, question, accountId, userEmail }) {
  // ⚡ PERF: Wrap with _queuedRequest to prevent duplicate requests from rapid clicks
  return _queuedRequest(`chat_${messageId}`, async () => {
    const _t0 = performance.now();

    // ── Parallel init ────────────────────────────────────────────────────────
    const [resolvedEmail, backendUrl, items] = await Promise.all([
    userEmail
      ? Promise.resolve(userEmail)
      : getAccountEmailFromMessage(messageId).then(e => e || getUserId(messageId)),
    getBackendUrl(),
    getThreadMessages(messageId),
  ]);
  const userId    = resolvedEmail;
  const firstMeta = items[0].meta;
  const threadId  = _getCanonicalThreadId(firstMeta, items[0].full);
  console.log(`[ChatWithThread] ⚡ Init in ${(performance.now()-_t0).toFixed(0)}ms — user=${userId}`);

  // Log emails to server (must complete before chat so context is indexed)
  try { await _logEmailsToServer(backendUrl,userId,threadId,items.map(({meta,full})=>_fmtMsg(meta,full))); }
  catch(e) { console.warn("logEmail:",e.message); }

  // Store attachments in BACKGROUND — chat API will use whatever is already indexed
  (async () => {
    for (const {meta} of items) {
      try { const a=await _getAttachments(meta.id); if(a.length) await _storeAtts(backendUrl,userId,threadId,String(meta.id),a); }
      catch(e) { console.warn("storeAtts:",e.message); }
    }
  })();

  console.log(`[ChatWithThread] ⚡ Firing chat API at ${(performance.now()-_t0).toFixed(0)}ms`);
  const resp = await fetch(`${backendUrl}/api/chat-with-thread`, {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({ user_id:userId, thread_id:threadId, question })
  });
  if (!resp.ok) { const t=await resp.text(); throw new Error(`Chat API (${resp.status}): ${t}`); }
  const initial = await resp.json();
  const result  = initial.job_id ? await _pollJobStatus(initial.job_id) : initial;
    if (!result.success) throw new Error(result.error||"Unknown server error");
    return { success:true, answer:result.answer, processingInfo:result.processing_info||{} };
  });
}





// ─── SERVER COMMUNICATION ───────────────────────────────────────────────────────────

async function _logEmailsToServer(backendUrl, userId, threadId, messages) {
  const funcStartTime = performance.now();
  console.log(`%c[_logEmailsToServer] ▶️  POSTing ${messages.length} messages to ${backendUrl}/api/log-email`, "color:#00CC00");
  
  try {
    const fetchStartTime = performance.now();
    const resp = await fetch(`${backendUrl}/api/log-email`, {
      method:"POST", 
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ user_id:userId, thread_id:threadId, messages })
    });
    const fetchDuration = (performance.now() - fetchStartTime).toFixed(0);
    console.log(`%c[_logEmailsToServer]   Response received: HTTP ${resp.status} in ${fetchDuration}ms`, "color:#00CC00");
    
    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(`log-email: server ${resp.status}: ${text}`);
    }
    
    const result = await resp.text();
    const funcDuration = (performance.now() - funcStartTime).toFixed(0);
    console.log(`%c[_logEmailsToServer] ✅ Complete in ${funcDuration}ms`, "color:#00AA00;font-weight:bold");
    return result;
  } catch(e) {
    const funcDuration = (performance.now() - funcStartTime).toFixed(0);
    console.error(`%c[_logEmailsToServer] ❌ Error after ${funcDuration}ms: ${e.message}`, "color:#CC0000");
    throw e;
  }
}

/**
 * Call /api/label-email — full processing pipeline:
 * preprocess → vector embed → label → graph store.
 * Used by bulk indexing instead of /api/log-email which only dumps JSON to disk.
 */
async function _labelEmailOnServer(backendUrl, userId, threadId, messages) {
  const fullUrl = `${backendUrl}/api/label-email`;
  const payload = { user_id:userId, thread_id:threadId, messages };
  const payloadStr = JSON.stringify(payload);
  
  console.log(`[OpenMailBot][API] 📤 REQUEST`);
  console.log(`[OpenMailBot][API] URL: ${fullUrl}`);
  console.log(`[OpenMailBot][API] Method: POST`);
  console.log(`[OpenMailBot][API] Content-Type: application/json`);
  console.log(`[OpenMailBot][API] Payload size: ${payloadStr.length} bytes`);
  console.log(`[OpenMailBot][API] Full payload: ${payloadStr}`);
  
  try {
    const resp = await fetch(fullUrl, {
      method:"POST", 
      headers:{"Content-Type":"application/json"},
      body: payloadStr
    });
    
    console.log(`[OpenMailBot][API] 📥 RESPONSE`);
    console.log(`[OpenMailBot][API] Status: ${resp.status} ${resp.statusText}`);
    console.log(`[OpenMailBot][API] OK: ${resp.ok}`);
    
    const respText = await resp.text();
    console.log(`[OpenMailBot][API] Body size: ${respText.length} bytes`);
    console.log(`[OpenMailBot][API] Body: ${respText}`);
    
    if (!resp.ok) {
      throw new Error(`label-email: server ${resp.status}: ${respText}`);
    }
    
    try {
      const json = JSON.parse(respText);
      console.log(`[OpenMailBot][API] ✅ Parsed JSON: ${JSON.stringify(json)}`);
      return json;
    } catch (parseErr) {
      console.log(`[OpenMailBot][API] Response is not JSON, returning raw text`);
      return respText;
    }
  } catch (err) {
    console.error(`[OpenMailBot][API] ❌ FETCH ERROR: ${err.message}`);
    throw err;
  }
}

async function _storeAtts(backendUrl, userId, threadId, messageId, attachments) {
  const funcStartTime = performance.now();
  const fullUrl = `${backendUrl}/api/store-attachments`;
  const payload = { user_id:userId, thread_id:threadId, message_id:messageId, attachments };
  const payloadStr = JSON.stringify(payload);
  
  console.log(`%c[_storeAtts] ▶️  POSTing ${attachments.length} attachment(s) for message ${messageId}`, "color:#FF8800");
  console.log(`%c[_storeAtts]   URL: ${fullUrl}`, "color:#FF8800");
  console.log(`%c[_storeAtts]   Payload size: ${payloadStr.length} bytes`, "color:#FF8800");
  
  try {
    const fetchStartTime = performance.now();
    const resp = await fetch(fullUrl, {
      method:"POST", 
      headers:{"Content-Type":"application/json"},
      body: payloadStr
    });
    const fetchDuration = (performance.now() - fetchStartTime).toFixed(0);
    console.log(`%c[_storeAtts]   Response: HTTP ${resp.status} in ${fetchDuration}ms`, "color:#FF8800");
    
    const respText = await resp.text();
    
    if (!resp.ok) {
      console.error(`%c[_storeAtts] ❌ Error: ${resp.status} - ${respText.substring(0, 200)}`, "color:#CC0000");
      throw new Error(`store-attachments: server ${resp.status}: ${respText}`);
    }
    
    const funcDuration = (performance.now() - funcStartTime).toFixed(0);
    console.log(`%c[_storeAtts] ✅ Complete in ${funcDuration}ms`, "color:#FF8800;font-weight:bold");
    return respText;
  } catch (err) {
    const funcDuration = (performance.now() - funcStartTime).toFixed(0);
    console.error(`%c[_storeAtts] ❌ Exception after ${funcDuration}ms: ${err.message}`, "color:#CC0000;font-weight:bold");
    throw err;
  }
}

/**
 * Extract a canonical cross-client thread ID that is consistent between
 * Gmail Add-on (Apps Script) and Thunderbird.
 *
 * ┌──────────────────────┬──────────────────────────────────────────────────────┐
 * │ Source               │ Thread ID format                                      │
 * ├──────────────────────┼──────────────────────────────────────────────────────┤
 * │ Gmail Add-on (GAS)   │ thread.getId() → 16-char lowercase hex e.g.           │
 * │                      │   "17f1a2b3c4d5e6f7"                                  │
 * │ Thunderbird (IMAP)   │ X-GM-THRID header → decimal e.g. "1728455344230334865"│
 * │                      │ → convert BigInt(decimal).toString(16) → same hex     │
 * │ Outlook (IMAP)       │ Conversation-ID header (used as-is)                   │
 * │ Generic IMAP         │ First <id> in References chain (RFC 5322 thread root) │
 * └──────────────────────┴──────────────────────────────────────────────────────┘
 *
 * Priority order:
 *   1. X-GM-THRID       — Gmail native thread ID (decimal → hex conversion)
 *   2. Conversation-ID  — Outlook/Exchange thread ID
 *   3. References chain — RFC thread-root Message-ID (cross-provider fallback)
 *   4. In-Reply-To      — direct parent (single-reply fallback)
 *   5. headerMessageId  — own Message-ID (root of a new thread)
 *   6. String(meta.id)  — Thunderbird internal numeric ID (last resort)
 *
 * @param {object} meta  MessageHeader from browser.messages.get/list
 * @param {object} full  MessagePart from browser.messages.getFull
 * @returns {string}     Canonical thread ID shared across all clients for the same thread
 */
function _getCanonicalThreadId(meta, full) {
  const headers = full && full.headers ? full.headers : {};

  // ── Priority 1: X-GM-THRID — Gmail's native thread ID exposed via IMAP ──────
  // Google delivers this as a decimal integer string in the IMAP FETCH response.
  // Gmail Add-on's thread.getId() returns the same value in lowercase hex, so we
  // convert: BigInt(decimal).toString(16) to get the identical hex string.
  const xGmThridRaw = (headers["x-gm-thrid"] || headers["X-GM-THRID"] || [])[0];
  if (xGmThridRaw) {
    const decimal = String(xGmThridRaw).trim();
    if (/^\d{10,20}$/.test(decimal)) {
      try {
        const hexId = BigInt(decimal).toString(16);  // e.g. "17f1a2b3c4d5e6f7"
        console.log(`[OpenMailBot][ThreadId] X-GM-THRID ${decimal} → hex: ${hexId}`);
        return hexId;
      } catch (e) {
        console.warn(`[OpenMailBot][ThreadId] X-GM-THRID BigInt conversion failed: ${e.message}`);
      }
    }
  }

  // ── Priority 2: Outlook / Exchange Conversation-ID ────────────────────────────
  const convId = (headers["conversation-id"] || headers["Conversation-ID"] || [])[0];
  if (convId && convId.trim()) {
    const normalised = convId.trim();
    console.log(`[OpenMailBot][ThreadId] Outlook Conversation-ID: ${normalised}`);
    return normalised;
  }

  // ── Priority 3: RFC References chain — first entry is the thread root ─────────
  // Same Message-ID appears in the References header on every message in the thread,
  // regardless of which mail client sends or receives it.
  const refs = (headers["references"] || headers["References"] || [])[0];
  if (refs) {
    const ids = refs.match(/<[^>]+>/g);
    if (ids && ids.length > 0) return ids[0].slice(1, -1);  // strip < >
  }

  // ── Priority 4: In-Reply-To — direct parent (equals root for single-reply threads) ──
  const inReplyTo = (headers["in-reply-to"] || headers["In-Reply-To"] || [])[0];
  if (inReplyTo) {
    const ids = inReplyTo.match(/<[^>]+>/g);
    if (ids && ids.length > 0) return ids[0].slice(1, -1);  // strip < >
  }

  // ── Priority 5: Own Message-ID (this IS the root — no prior chain) ──────────
  if (meta.headerMessageId) return meta.headerMessageId;

  // ── Priority 6: Thunderbird internal numeric ID (last resort) ────────────────
  return String(meta.id);
}

function _fmtMsg(meta, full) {
  return {
    message_id   : String(meta.id||""),
    from_address : meta.author||"",
    to           : meta.recipients||[],
    subject      : meta.subject||"",
    timestamp    : meta.date ? new Date(meta.date).toISOString() : new Date().toISOString(),
    body         : extractPlainText(full)
  };
}

async function _getAttachments(messageId) {
  const funcStartTime = performance.now();
  console.log(`%c[_getAttachments] ▶️  Listing attachments for message: ${messageId}`, "color:#FF6B00");
  
  try {
    const listStart = performance.now();
    const atts = await browser.messages.listAttachments(messageId);
    console.log(`%c[_getAttachments]   Found ${atts.length} attachment(s) in ${(performance.now()-listStart).toFixed(0)}ms`, "color:#FF6B00");
    
    if (atts.length === 0) {
      console.log(`%c[_getAttachments] ✅ No attachments to process`, "color:#FF6B00");
      return [];
    }
    
    const result = [];
    for (let i = 0; i < atts.length; i++) {
      const att = atts[i];
      const name = (att.name||"").toLowerCase();
      console.log(`%c[_getAttachments]   [${i+1}/${atts.length}] Checking: ${att.name}`, "color:#FF6B00");
      
      const isAllowed = ALLOWED_EXTENSIONS.some(ext => name.endsWith(ext));
      if (!isAllowed) {
        console.log(`%c[_getAttachments]     ⏭️  Skipping — extension not whitelisted`, "color:#FF9900");
        continue;
      }
      
      try {
        const fileStart = performance.now();
        const file = await browser.messages.getAttachmentFile(messageId, att.partName);
        const buf  = await file.arrayBuffer();
        const encoded = _ab2b64(buf);
        const duration = (performance.now() - fileStart).toFixed(0);
        console.log(`%c[_getAttachments]     ✅ ${att.name}: ${buf.byteLength} bytes → ${encoded.length} b64 chars (${duration}ms)`, "color:#00AA00");
        result.push({ filename:att.name, content:encoded, mime_type:att.contentType||"application/octet-stream" });
      } catch(e) { 
        console.error(`%c[_getAttachments]     ❌ Error processing ${att.name}: ${e.message}`, "color:#CC0000");
      }
    }
    
    const funcDuration = (performance.now() - funcStartTime).toFixed(0);
    console.log(`%c[_getAttachments] ✅ Complete: ${result.length}/${atts.length} attachment(s) ready in ${funcDuration}ms`, "color:#FF6B00;font-weight:bold");
    return result;
  } catch(e) { 
    const funcDuration = (performance.now() - funcStartTime).toFixed(0);
    console.error(`%c[_getAttachments] ❌ Exception after ${funcDuration}ms: ${e.message}`, "color:#CC0000");
    return [];
  }
}

function _ab2b64(buffer) {
  let bin=""; const bytes=new Uint8Array(buffer);
  for (let i=0;i<bytes.byteLength;i++) bin+=String.fromCharCode(bytes[i]);
  return btoa(bin);
}

async function _pollJobStatus(jobId, maxMs=120000) {
  const funcStartTime = performance.now();
  console.log(`%c[_pollJobStatus] ▶️  Polling job: ${jobId} (max ${maxMs}ms) — REDUCED INTERVAL = FASTER RESPONSE`, "color:#FF00FF;font-weight:bold");
  
  const backendUrl = await getBackendUrl();
  let waited = 0;
  let pollCount = 0;
  const pollInterval = 1000; // ⚡ OPTIMIZED: Reduced from 3000ms to 1000ms — Saves 6+ seconds per async job!
  console.log(`%c[_pollJobStatus] ⏱️  Poll interval: ${pollInterval}ms (was 3000ms)`, "color:#FF00FF");
  
  while (waited < maxMs) {
    await new Promise(r=>setTimeout(r,pollInterval)); 
    waited+=pollInterval;
    pollCount++;
    console.log(`%c[_pollJobStatus] Poll #${pollCount} at ${waited}ms...`, "color:#FF00FF");
    
    try {
      const pollStart = performance.now();
      const resp = await fetch(`${backendUrl}/api/job-status/${jobId}`);
      const pollDuration = (performance.now() - pollStart).toFixed(0);
      console.log(`%c[_pollJobStatus]   Status response: HTTP ${resp.status} in ${pollDuration}ms`, "color:#FF00FF");
      
      if (resp.ok) {
        const d = await resp.json();
        console.log(`%c[_pollJobStatus]   Job status: ${d.status}`, "color:#FF00FF");
        
        if (d.status==="done") {
          const funcDuration = (performance.now() - funcStartTime).toFixed(0);
          console.log(`%c[_pollJobStatus] ✅ Job complete in ${funcDuration}ms after ${pollCount} polls`, "color:#00AA00;font-weight:bold");
          return d.result;
        }
        if (d.status==="error") {
          const funcDuration = (performance.now() - funcStartTime).toFixed(0);
          console.error(`%c[_pollJobStatus] ❌ Job error after ${funcDuration}ms: ${d.error}`, "color:#CC0000");
          throw new Error("Job error: "+d.error);
        }
      }
    } catch(e) { 
      console.warn(`%c[_pollJobStatus] ⚠️  Poll #${pollCount} error: ${e.message}`, "color:#FF9900"); 
    }
  }
  
  const funcDuration = (performance.now() - funcStartTime).toFixed(0);
  console.error(`%c[_pollJobStatus] ❌ Timeout after ${funcDuration}ms (${pollCount} polls)`, "color:#CC0000;font-weight:bold");
  throw new Error(`Timeout for job ${jobId}`);
}

// ─── USER HELPERS ─────────────────────────────────────────────────────────────

/**
 * Extract the account email from a message ID.
 * This is CRITICAL for multi-account support:
 * - Gets the message's folder
 * - Finds which account owns that folder
 * - Returns that account's email (NOT the first account)
 * 
 * This ensures that operations on messages from Account B use Account B's email,
 * not always defaulting to Account A.
 */
async function getAccountEmailFromMessage(messageId) {
  try {
    const msg = await browser.messages.get(messageId);
    if (!msg || !msg.folder) {
      console.warn(`[MultiAccount] Message ${messageId} has no folder`);
      return null;
    }
    
    const allAccounts = await browser.accounts.list();
    
    // Find the account that owns this message's folder
    for (const acc of allAccounts) {
      const owns = _accountOwnsFolders(msg.folder, acc.folders);
      if (owns) {
        const email = await getAccountEmail(acc.id);
        console.log(`[MultiAccount] ✅ Message ${messageId} belongs to account: ${email}`);
        return email;
      }
    }
    
    console.warn(`[MultiAccount] Could not find owning account for message ${messageId}`);
    return null;
  } catch (e) {
    console.error(`[MultiAccount] getAccountEmailFromMessage failed: ${e.message}`);
    return null;
  }
}

/**
 * Check if an account's folders recursively contain a target folder
 */
function _accountOwnsFolders(targetFolder, accountFolders) {
  if (!accountFolders) return false;
  for (const f of accountFolders) {
    if (f.id === targetFolder.id) return true;
    if (f.subFolders && _accountOwnsFolders(targetFolder, f.subFolders)) return true;
  }
  return false;
}

/**
 * Get user ID (email) from message context if available, otherwise use first account.
 * This is the context-aware version that respects multi-account setups.
 */
async function getUserId(messageId) {
  // If messageId provided, extract account email from that message context
  if (messageId) {
    const email = await getAccountEmailFromMessage(messageId);
    if (email) return email;
  }
  
  // Fallback: try all accounts and return first available
  try {
    const accounts = await browser.accounts.list();
    if (accounts.length > 0) {
      const ids = accounts[0].identities || [];
      if (ids.length > 0) return ids[0].email;
    }
  } catch (e) { console.error("getUserId:", e); }
  return "unknown@user.com";
}

async function getUserPreferences(userEmail) {
  // Fetch settings from backend (replaces removed _getSettings())
  const s = userEmail
    ? await _fetchSettingsFromBackend(userEmail)
    : Object.assign({}, DEFAULT_SETTINGS);
  return {
    name               : s.user_name     || "User",
    position           : s.user_position || "Professional",
    tone               : s.user_tone     || "professional",
    custom_instructions: s.system_prompt  || ""
  };
}

// ─── FLASK / PIPELINE APIs ─────────────────────────────────────────────────────────────

/**
 * Call Flask /chat endpoint
 */
async function callFlaskAPI(content, action) {
  const funcStartTime = performance.now();
  const backendUrl = await getBackendUrl();
  const apiEndpoint = `${backendUrl}/chat`;
  const prompt = action === "summarize" ? SUMMARIZE_PROMPT + content : content;
  
  console.log(`%c[callFlaskAPI] ▶️  ${action.toUpperCase()} request to ${apiEndpoint}`, "color:#FF6B00");
  console.log(`%c[callFlaskAPI]   Prompt length: ${prompt.length} chars`, "color:#FF6B00");
  
  try {
    const fetchStartTime = performance.now();
    const response = await fetch(apiEndpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt })
    });
    const fetchDuration = (performance.now() - fetchStartTime).toFixed(0);
    console.log(`%c[callFlaskAPI]   Response received: HTTP ${response.status} in ${fetchDuration}ms`, "color:#FF6B00");
    
    if (!response.ok) {
      throw new Error(`Flask API error: ${response.status}`);
    }
    
    const data = await response.json();
    if (data.error) throw new Error(`Flask API error: ${data.error}`);
    if (data.response) {
      const funcDuration = (performance.now() - funcStartTime).toFixed(0);
      console.log(`%c[callFlaskAPI] ✅ ${action} complete: ${data.response.length} chars in ${funcDuration}ms`, "color:#FF6B00;font-weight:bold");
      return data.response;
    }
    throw new Error("Unexpected API response format");
  } catch(e) {
    const funcDuration = (performance.now() - funcStartTime).toFixed(0);
    console.error(`%c[callFlaskAPI] ❌ ${action} failed after ${funcDuration}ms: ${e.message}`, "color:#CC0000");
    throw e;
  }
}

const SUMMARIZE_PROMPT =
`You are an expert enterprise communication analyst.
Analyze ALL emails and produce a chronological, structured summary.

### Instructions
1. Read every email.
2. Identify true chronological order.
3. Merge replies and forwards (no repetition).
4. Ignore greetings/signatures/disclaimers.
5. Focus on decisions, requests, approvals, blockers, commitments.

---

#### 1\uFE0F\u20E3 Conversation Overview
- **Topic:** <one-line summary>
- **Participants:** <key people and roles>
- **Time Range:** <first \u2192 last email date>

---

#### 2\uFE0F\u20E3 Chronological Timeline

**Step 1 \u2013 <Short Title>**
- What happened: <concise line>
- Outcome / Decision: <if any>
- Expectation / Ask: <what was requested next>

(Repeat for all major events)

---

#### 3\uFE0F\u20E3 Current Status
- **Current State:** <Awaiting approval / In progress / Blocked / Completed>
- **Owner:** <person responsible>
- **Pending Actions:** <bullet list>

---

#### 4\uFE0F\u20E3 Open Questions / Pending Requests
- <question> (<who responds>)

---

#### 5\uFE0F\u20E3 Final Ask / Next Expected Action
- **Action Required:** <clear action>
- **From Whom:** <person/team>
- **Deadline:** <date or "Not specified">

### Rules: Factual, neutral, no invented info, professional, concise.

Email Thread:
`;

async function callPipelineAPI(requestData) {
  const backendUrl = await getBackendUrl();
  const resp = await fetch(`${backendUrl}/api/draft-with-attachments`, {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify(requestData)
  });
  if (!resp.ok) { const t=await resp.text(); throw new Error(`Pipeline API (${resp.status}): ${t}`); }
  const ct = resp.headers.get("content-type")||""; 
  if (ct.includes("text/html")) throw new Error("Server returned HTML. Is the backend running?");
  const data = await resp.json();
  if (data.error) throw new Error("Pipeline: "+data.error);
  if (data.job_id) return _pollJobStatus(data.job_id);
  return data;
}
  



