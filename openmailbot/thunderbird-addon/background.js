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

const DEFAULT_FLASK_URL  = "http://43.204.98.38:5050";
let   ALLOWED_EXTENSIONS = [".pdf", ".csv", ".pptx", ".ppt", ".xlsx", ".xls", ".docx", ".doc"];

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

// ─── ADDON CONFIG (addon_config.json — addon-side only, never sent to server) ─

let _addonConfig = null;

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
  backend_url        : DEFAULT_FLASK_URL,
  mode               : "inbuilt",
  llm_provider       : "inbuilt",
  llm_api_key        : "",
  llm_model          : "gpt-4o-mini",
  llm_base_url       : "",
  embedding_provider : "inbuilt",
  embedding_api_key  : "",
  embedding_model    : "text-embedding-3-small",
  vector_provider    : "inbuilt",
  vector_url         : "",
  vector_api_key     : "",
  user_name          : "",
  user_position      : "",
  user_tone          : "professional",
  system_prompt      : ""
};

/* keep a reference so other functions below can use DEFAULT_FLASK_SERVER_URL */
const DEFAULT_FLASK_SERVER_URL = DEFAULT_FLASK_URL;

// ─── SETTINGS HELPERS ──────────────────────────────────────────────────────────

async function _getSettings() {
  const r = await browser.storage.local.get("user_settings");
  return Object.assign({}, DEFAULT_SETTINGS, r.user_settings || {});
}

async function getBackendUrl() {
  try {
    // addon_config.json backend_url is authoritative — always prefer it over stored settings
    const [s, cfg] = await Promise.all([_getSettings(), getAddonConfig()]);
    const url = (cfg.backend_url || s.backend_url || DEFAULT_FLASK_URL).replace(/\/$/,"");
    return url;
  } catch (e) {
    return DEFAULT_FLASK_URL;
  }
}

// ─── SETTINGS HANDLERS ─────────────────────────────────────────────────────────

async function handleLoadSettings() {
  return { success: true, settings: await _getSettings() };
}

async function handleSaveSettings({ settings }) {
  const merged = Object.assign({}, DEFAULT_SETTINGS, settings);
  await browser.storage.local.set({ user_settings: merged });
  try { await _syncSettingsToBackend(merged); } catch (e) { console.warn("Sync failed:", e.message); }
  return { success: true, settings: merged };
}

async function handleResetSettings() {
  await browser.storage.local.set({ user_settings: DEFAULT_SETTINGS });
  return { success: true, settings: DEFAULT_SETTINGS };
}

async function handleSyncSettings(data) {
  const settings = (data && data.settings) ? data.settings : await _getSettings();
  await _syncSettingsToBackend(settings);
  return { success: true };
}

async function _syncSettingsToBackend(settings) {
  const base   = (settings.backend_url || DEFAULT_FLASK_URL).replace(/\/$/,"");
  const userId = await getUserId();
  const resp   = await fetch(`${base}/api/settings`, {
    method : "POST",
    headers: { "Content-Type": "application/json" },
    body   : JSON.stringify({ user_id: userId, settings })
  });
  if (!resp.ok) throw new Error(`Backend ${resp.status}: ${await resp.text()}`);
  return resp.json();
}

// ─── DOMAIN FILTER HANDLERS ───────────────────────────────────────────────────────

/**
 * Returns both user-saved filters AND the config-file defaults (merged, deduplicated).
 * The UI always shows the merged list so users know what's actually active.
 */
async function handleGetDomainFilters() {
  const filters = await _getMergedDomainFilters();
  return { success: true, filters };
}

async function handleSaveDomainFilters({ filters }) {
  // Save only the user-defined filters; config-file defaults are always merged at read time
  const unique = [...new Set((filters||[]).map(f=>f.toLowerCase().trim()).filter(Boolean))];
  await browser.storage.local.set({ domain_filters: unique });
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

async function handleSaveProcessMonths({ months }) {
  await browser.storage.local.set({ process_last_n_months: months||"3" });
  return { success: true };
}

async function handleGetProcessMonths() {
  const r = await browser.storage.local.get("process_last_n_months");
  return { success: true, months: r.process_last_n_months||"3" };
}

async function handleGetBulkJobStatus() {
  const r = await browser.storage.local.get(["bulk_job_state","bulk_job_abort"]);
  return { success: true, state: r.bulk_job_state||null, aborted: r.bulk_job_abort===true };
}

async function handleCancelBulkJob() {
  await browser.storage.local.set({ bulk_job_abort: true });
  return { success: true };
}

async function handleRunBulkProcess({ months }) {
  console.log("\n\n");
  console.log("🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴");
  console.log("🔴 BULK INDEX EMAIL BUTTON CLICKED!");
  console.log("🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴\n");
  
  const cfg = await getAddonConfig();
  const n      = parseInt(months || String((cfg.bulk_processing && cfg.bulk_processing.default_months) || 3), 10);
  const before = new Date();
  const after  = new Date();
  after.setMonth(after.getMonth() - n);
  
  console.log(`[OpenMailBot][BulkStart] Processing last ${n} months`);
  console.log(`[OpenMailBot][BulkStart] Date range: ${after.toLocaleDateString()} → ${before.toLocaleDateString()}`);
  console.log(`[OpenMailBot][BulkStart] Backend URL: ${await getBackendUrl()}`);
  console.log(`[OpenMailBot][BulkStart] User ID: ${await getUserId()}`);
  console.log(`[OpenMailBot][BulkStart] Config: ${JSON.stringify(cfg, null, 2)}\n`);
  
  const state = {
    n, months: String(n),
    afterStr : after.toLocaleDateString(),
    beforeStr: before.toLocaleDateString(),
    status   : "running",
    offset   : 0,
    stats    : { threadsScanned:0, messagesFound:0, labeled:0, skipped:0, filtered:0, errors:0 }
  };
  await browser.storage.local.set({ bulk_job_state: state, bulk_job_abort: false });
  _runBulkAsync(n, after, before, state).catch(e => {
    console.error("\n[OpenMailBot] 274c BULK PROCESS ERROR:", e.message);
    console.error("[OpenMailBot] Stack:", e.stack);
    browser.storage.local.set({ bulk_job_state: Object.assign({}, state, { status:"error", error:e.message }) });
  });
  return { success: true, state };
}

async function _runBulkAsync(n, after, before, state) {
  const cfg        = await getAddonConfig();
  const bp         = cfg.bulk_processing || {};
  const BATCH      = bp.batch_size           || 10;
  const MAX_MSGS   = bp.max_messages_per_run || 2000;
  const DELAY_MS   = bp.request_delay_ms     || 200;

  const userId     = await getUserId();
  const backendUrl = await getBackendUrl();
  const filters    = await _getMergedDomainFilters();   // addon-side filter list (storage + config)

  console.log(`[OpenMailBot][BulkIndex] ▶ Starting bulk index | user=${userId} | backendUrl=${backendUrl} | months=${n} | dateRange=${after.toLocaleDateString()} → ${before.toLocaleDateString()} | BATCH=${BATCH} | MAX_MSGS=${MAX_MSGS} | domainFilters=${filters.length}`);

  let totalProcessed = 0;

  const accounts = await browser.accounts.list();
  console.log(`[OpenMailBot][BulkIndex] Found ${accounts.length} mail account(s)`);
  
  for (const acc of accounts) {
    if (totalProcessed >= MAX_MSGS) break;

    console.log(`[OpenMailBot][BulkIndex] Processing account: ${acc.name||acc.id}`);
    
    // Search ALL folders, not just inbox, to catch Sent/other folders
    const allFolders = _collectAllFolders(acc.folders);
    console.log(`[OpenMailBot][BulkIndex] Found ${allFolders.length} folder(s) to scan`);
    
    for (const folder of allFolders) {
      if (totalProcessed >= MAX_MSGS) break;

      console.log(`[OpenMailBot][BulkIndex] 📂 Scanning folder: "${folder.name}" (type=${folder.type||"unknown"})`);

      let page;
      try {
        page = await browser.messages.list(folder);
      } catch(e) {
        console.warn("[OpenMailBot] Cannot list folder:", folder.name, e.message);
        continue;
      }

      while (page) {
        // Abort check
        const ac = await browser.storage.local.get("bulk_job_abort");
        if (ac.bulk_job_abort) {
          console.log(`[OpenMailBot][BulkIndex] 🛑 Abort detected`);
          await browser.storage.local.set({ bulk_job_state: Object.assign({}, state, { status:"cancelled" }) });
          return;
        }

        const rawMsgs = page.messages || [];
        console.log(`[OpenMailBot][BulkIndex] Page has ${rawMsgs.length} message(s)`);
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

          const ac2 = await browser.storage.local.get("bulk_job_abort");
          if (ac2.bulk_job_abort) {
            console.log(`[OpenMailBot][BulkIndex] 🛑 Abort detected in batch loop`);
            await browser.storage.local.set({ bulk_job_state: Object.assign({}, state, { status:"cancelled" }) });
            return;
          }

          console.log(`[OpenMailBot][BulkIndex] Processing batch ${Math.floor(i/BATCH)+1} (${Math.min(BATCH, msgs.length-i)} messages)`);

          for (const msg of msgs.slice(i, i + BATCH)) {
            if (totalProcessed >= MAX_MSGS) break;
            try {
              const full = await browser.messages.getFull(msg.id);
              const tid  = msg.headerMessageId || String(msg.id);
              // Store attachments FIRST so label-email's CheckAndStoreAttachmentsPipeline can find them on disk
              const atts = await _getAttachments(msg.id);
              if (atts.length) {
                const storeAttsUrl = `${backendUrl}/api/store-attachments`;
                console.log(`[OpenMailBot][BulkIndex] POST ${storeAttsUrl} | thread_id=${tid} | msg_id=${msg.id} | attachments=${atts.length} [${atts.map(a=>a.filename).join(", ")}]`);
                await _storeAtts(backendUrl, userId, tid, String(msg.id), atts);
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
              console.log(`[OpenMailBot][BulkIndex] ║ payload: ${JSON.stringify({ user_id:userId, thread_id:tid, messages: [msgData] }, null, 2)}`);
              console.log(`[OpenMailBot][BulkIndex] ╚════════════════════════════════════════`);
              const labelResult = await _labelEmailOnServer(backendUrl, userId, tid, [msgData]);
              const assignedLabel = labelResult && (labelResult.label || labelResult.category);
              console.log(`[OpenMailBot][BulkIndex] ✓ label-email OK | thread_id=${tid} | label=${assignedLabel||"(none)"}`);

              // ── Apply the label as a Thunderbird tag on the actual message ──
              if (assignedLabel) {
                await _applyThunderbirdTag(msg.id, assignedLabel);
              }

              state.stats.labeled++;
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
          await browser.storage.local.set({ bulk_job_state: state });
        }

        if (page.id) {
          try { page = await browser.messages.continueList(page.id); }
          catch(e) { console.warn("[OpenMailBot] continueList:", e.message); break; }
        } else {
          break;
        }
      }
    }
  }

  const finalStatus = totalProcessed >= MAX_MSGS ? "done_limit" : "done";
  console.log(`[OpenMailBot][BulkIndex] ■ Finished | status=${finalStatus} | totalProcessed=${totalProcessed} | labeled=${state.stats.labeled} | errors=${state.stats.errors} | filtered=${state.stats.filtered}`);
  await browser.storage.local.set({ bulk_job_state: Object.assign({}, state, { status: finalStatus }) });
}

// ─── THUNDERBIRD TAG APPLICATION ─────────────────────────────────────────────

/**
 * Ensure a tag exists in Thunderbird and apply it to a message.
 * Creates the tag with the configured colour if it doesn't exist yet.
 * Preserves any existing tags on the message (additive, not replace-all).
 *
 * @param {number} messageId  - Thunderbird internal message id
 * @param {string} labelName  - Raw label string returned by /api/label-email
 *                              e.g. "meeting", "Response", "Awaiting reply"
 */
async function _applyThunderbirdTag(messageId, labelName) {
  if (!labelName) return;
  // Thunderbird tag keys must be lowercase; spaces replaced with underscores
  const key     = labelName.toLowerCase().replace(/\s+/g, "_");
  const display = labelName.charAt(0).toUpperCase() + labelName.slice(1);
  const color   = (THUNDERBIRD_LABEL_COLORS[labelName.toLowerCase()] ||
                   THUNDERBIRD_LABEL_COLORS[key] || "#888888").toUpperCase();

  console.log(`[OpenMailBot][Tag] Applying tag | msgId=${messageId} | label="${labelName}" | key="${key}" | color=${color}`);

  // ── Step 1: Ensure the tag exists — messenger.messages.tags API (TB 121+) ──
  try {
    const existingTags = await messenger.messages.tags.list();
    console.log(`[OpenMailBot][Tag] Existing tags: ${JSON.stringify(existingTags.map(t => t.key))}`);
    const tagExists = existingTags.some(t => t.key === key);
    if (!tagExists) {
      await messenger.messages.tags.create(key, display, color);
      console.log(`[OpenMailBot][Tag] ✅ Created tag: key="${key}" display="${display}" color=${color}`);
    } else {
      console.log(`[OpenMailBot][Tag] Tag "${key}" already exists`);
    }
  } catch (e) {
    console.error(`[OpenMailBot][Tag] ❌ Step 1 (tags.create/list) failed:`, e.message, e);
  }

  // ── Step 2: Get current message tags, merge, and update ──
  try {
    const msgMeta     = await messenger.messages.get(messageId);
    const currentTags = (msgMeta && Array.isArray(msgMeta.tags)) ? msgMeta.tags : [];
    console.log(`[OpenMailBot][Tag] Current msg tags: ${JSON.stringify(currentTags)}`);
    if (!currentTags.includes(key)) {
      const updatedTags = [...currentTags, key];
      await messenger.messages.update(messageId, { tags: updatedTags });
      console.log(`[OpenMailBot][Tag] ✅ Applied tag "${key}" to msg ${messageId} | tags now: ${JSON.stringify(updatedTags)}`);
    } else {
      console.log(`[OpenMailBot][Tag] Tag "${key}" already set on msg ${messageId}`);
    }
  } catch (e) {
    console.error(`[OpenMailBot][Tag] ❌ Step 2 (messages.update tags) failed:`, e.message, e);
  }
}

/**
 * Collect all leaf folders from a folder tree (recursively).
 * Prioritises inbox, then sent, then others — to avoid processing spam/trash.
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

  // Seed user_settings if not yet stored, or update backend_url / llm defaults on every reinstall/update
  const r = await browser.storage.local.get(["user_settings", "domain_filters"]);
  if (!r.user_settings) {
    // Fresh install — write full defaults from config
    const defaults = Object.assign({}, DEFAULT_SETTINGS);
    if (cfg.backend_url) defaults.backend_url = cfg.backend_url;
    if (cfg.llm_defaults && cfg.llm_defaults.model)            defaults.llm_model       = cfg.llm_defaults.model;
    if (cfg.llm_defaults && cfg.llm_defaults.embedding_model)  defaults.embedding_model = cfg.llm_defaults.embedding_model;
    await browser.storage.local.set({ user_settings: defaults });
    console.log("[OpenMailBot] user_settings seeded from addon_config.json");
  } else {
    // Reinstall / update — always apply backend_url and llm_defaults from addon_config.json
    // so changing the config file takes effect without the user having to reset settings
    const patch = {};
    if (cfg.backend_url) patch.backend_url = cfg.backend_url;
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
});

// ─── MESSAGE ROUTER ──────────────────────────────────────────────────────────

browser.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log("Background received action:", message.action);

  const handlers = {
    summarizeThread      : () => handleSummarizeThread(message.data),
    draftWithAttachments : () => handleDraftWithAttachments(message.data),
    createDraft          : () => handleCreateDraft(message.data),
    chatWithThread       : () => handleChatWithThread(message.data),
    loadSettings         : () => handleLoadSettings(),
    saveSettings         : () => handleSaveSettings(message.data),
    resetSettings        : () => handleResetSettings(),
    syncSettings         : () => handleSyncSettings(message.data),
    getDomainFilters     : () => handleGetDomainFilters(),
    saveDomainFilters    : () => handleSaveDomainFilters(message.data),
    testDomainFilters    : () => handleTestDomainFilters(message.data),
    runBulkProcess       : () => handleRunBulkProcess(message.data),
    getBulkJobStatus     : () => handleGetBulkJobStatus(),
    cancelBulkJob        : () => handleCancelBulkJob(),
    saveProcessMonths    : () => handleSaveProcessMonths(message.data),
    getProcessMonths     : () => handleGetProcessMonths()
  };

  const fn = handlers[message.action];
  if (!fn) { sendResponse({ error: "Unknown action: " + message.action }); return false; }
  fn().then(sendResponse).catch(e => sendResponse({ error: e.message }));
  return true;
});

// ─── THREAD HELPERS ──────────────────────────────────────────────────────────────────

/**
 * Get all messages in the same thread (subject-based, full thread).
 * Returns array of { meta, full } objects sorted oldest-first.
 */
async function getThreadMessages(messageId) {
  try {
    const msg    = await browser.messages.get(messageId);
    const folder = msg.folder;
    if (!folder) {
      return [{ meta: msg, full: await browser.messages.getFull(messageId) }];
    }
    let allMsgs = [];
    let page = await browser.messages.list(folder);
    while (page) {
      allMsgs = allMsgs.concat(page.messages || []);
      if (page.id) { page = await browser.messages.continueList(page.id); } else break;
    }
    const norm = s => (s||"").replace(/^(Re|Fwd?|AW|WG):\s*/gi,"").trim().toLowerCase();
    const base = norm(msg.subject);
    const thread = allMsgs
      .filter(m => m.id===messageId || norm(m.subject)===base)
      .sort((a,b) => new Date(a.date)-new Date(b.date))
      .slice(0,30);
    const results = await Promise.all(thread.map(async m => {
      try { return { meta: m, full: await browser.messages.getFull(m.id) }; }
      catch(e) { console.warn("getFull failed:",m.id,e.message); return null; }
    }));
    return results.filter(Boolean);
  } catch(e) {
    console.error("getThreadMessages:",e);
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

async function handleSummarizeThread({ messageId }) {
  const userId     = await getUserId();
  const backendUrl = await getBackendUrl();
  const items      = await getThreadMessages(messageId);
  const threadText = buildThreadText(items);
  const firstMeta  = items[0].meta;
  const threadId   = firstMeta.headerMessageId || String(firstMeta.id);

  try { await _logEmailsToServer(backendUrl, userId, threadId, items.map(({meta,full})=>_fmtMsg(meta,full))); }
  catch(e) { console.warn("logEmail:", e.message); }
  for (const {meta} of items) {
    try { const a=await _getAttachments(meta.id); if(a.length) await _storeAtts(backendUrl,userId,threadId,String(meta.id),a); }
    catch(e) { console.warn("storeAtts:",e.message); }
  }
  const summary = await callFlaskAPI(threadText, "summarize");
  return { success: true, summary, threadId, messageId };
}

async function handleCreateDraft({ messageId, summary }) {
  const prefs  = await getUserPreferences();
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

async function handleDraftWithAttachments({ messageId }) {
  const userId     = await getUserId();
  const backendUrl = await getBackendUrl();
  const items      = await getThreadMessages(messageId);
  const firstMeta  = items[0].meta;
  const threadId   = firstMeta.headerMessageId || String(firstMeta.id);

  try { await _logEmailsToServer(backendUrl,userId,threadId,items.map(({meta,full})=>_fmtMsg(meta,full))); }
  catch(e) { console.warn("logEmail:",e.message); }

  let totalAtts = 0;
  for (const {meta} of items) {
    try { const a=await _getAttachments(meta.id); if(a.length){ totalAtts+=a.length; await _storeAtts(backendUrl,userId,threadId,String(meta.id),a); } }
    catch(e) { console.warn("storeAtts:",e.message); }
  }

  const prefs  = await getUserPreferences();
  const result = await callPipelineAPI({ user_id:userId, thread_id:threadId, message_id:String(messageId), user_preferences:prefs });

  const draftContent   = result.draft_content || result.response || "No draft content received";
  const processingInfo = result.processing_info || {};
  const lastMeta       = items[items.length-1].meta;
  const subject        = lastMeta.subject.match(/^Re:/i) ? lastMeta.subject : `Re: ${lastMeta.subject}`;

  await browser.compose.beginNew({ to:[lastMeta.author], subject, plainTextBody:draftContent, isPlainText:true });
  return { success:true, draftContent, processingInfo, attachmentCount:totalAtts };
}

async function handleChatWithThread({ messageId, question }) {
  const userId     = await getUserId();
  const backendUrl = await getBackendUrl();
  const items      = await getThreadMessages(messageId);
  const firstMeta  = items[0].meta;
  const threadId   = firstMeta.headerMessageId || String(firstMeta.id);

  try { await _logEmailsToServer(backendUrl,userId,threadId,items.map(({meta,full})=>_fmtMsg(meta,full))); }
  catch(e) { console.warn("logEmail:",e.message); }
  for (const {meta} of items) {
    try { const a=await _getAttachments(meta.id); if(a.length) await _storeAtts(backendUrl,userId,threadId,String(meta.id),a); }
    catch(e) { console.warn("storeAtts:",e.message); }
  }

  const resp = await fetch(`${backendUrl}/api/chat-with-thread`, {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({ user_id:userId, thread_id:threadId, question })
  });
  if (!resp.ok) { const t=await resp.text(); throw new Error(`Chat API (${resp.status}): ${t}`); }
  const initial = await resp.json();
  const result  = initial.job_id ? await _pollJobStatus(initial.job_id) : initial;
  if (!result.success) throw new Error(result.error||"Unknown server error");
  return { success:true, answer:result.answer, processingInfo:result.processing_info||{} };
}





// ─── SERVER COMMUNICATION ───────────────────────────────────────────────────────────

async function _logEmailsToServer(backendUrl, userId, threadId, messages) {
  const resp = await fetch(`${backendUrl}/api/log-email`, {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({ user_id:userId, thread_id:threadId, messages })
  });
  if (!resp.ok) throw new Error(`log-email: server ${resp.status}: ${await resp.text()}`);
  return resp.text();
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
  const fullUrl = `${backendUrl}/api/store-attachments`;
  const payload = { user_id:userId, thread_id:threadId, message_id:messageId, attachments };
  const payloadStr = JSON.stringify(payload);
  
  console.log(`[OpenMailBot][API] 📤 REQUEST (store-attachments)`);
  console.log(`[OpenMailBot][API] URL: ${fullUrl}`);
  console.log(`[OpenMailBot][API] Method: POST`);
  console.log(`[OpenMailBot][API] Attachments count: ${attachments.length}`);
  console.log(`[OpenMailBot][API] Payload size: ${payloadStr.length} bytes`);
  
  try {
    const resp = await fetch(fullUrl, {
      method:"POST", 
      headers:{"Content-Type":"application/json"},
      body: payloadStr
    });
    
    console.log(`[OpenMailBot][API] 📥 RESPONSE (store-attachments)`);
    console.log(`[OpenMailBot][API] Status: ${resp.status} ${resp.statusText}`);
    console.log(`[OpenMailBot][API] OK: ${resp.ok}`);
    
    const respText = await resp.text();
    console.log(`[OpenMailBot][API] Body: ${respText.substring(0, 500)}`);
    
    if (!resp.ok) {
      throw new Error(`store-attachments: server ${resp.status}: ${respText}`);
    }
    return respText;
  } catch (err) {
    console.error(`[OpenMailBot][API] ❌ FETCH ERROR (store-attachments): ${err.message}`);
    throw err;
  }
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
  try {
    const atts = await browser.messages.listAttachments(messageId);
    const result = [];
    for (const att of atts) {
      const name = (att.name||"").toLowerCase();
      if (!ALLOWED_EXTENSIONS.some(ext => name.endsWith(ext))) continue;
      try {
        const file = await browser.messages.getAttachmentFile(messageId, att.partName);
        const buf  = await file.arrayBuffer();
        result.push({ filename:att.name, content:_ab2b64(buf), mime_type:att.contentType||"application/octet-stream" });
      } catch(e) { console.warn("Att error:",att.name,e.message); }
    }
    return result;
  } catch(e) { console.error("listAttachments:",e); return []; }
}

function _ab2b64(buffer) {
  let bin=""; const bytes=new Uint8Array(buffer);
  for (let i=0;i<bytes.byteLength;i++) bin+=String.fromCharCode(bytes[i]);
  return btoa(bin);
}

async function _pollJobStatus(jobId, maxMs=120000) {
  const backendUrl = await getBackendUrl();
  let waited = 0;
  while (waited < maxMs) {
    await new Promise(r=>setTimeout(r,3000)); waited+=3000;
    try {
      const resp = await fetch(`${backendUrl}/api/job-status/${jobId}`);
      if (resp.ok) {
        const d = await resp.json();
        if (d.status==="done")  return d.result;
        if (d.status==="error") throw new Error("Job error: "+d.error);
      }
    } catch(e) { console.warn("Poll:",e.message); }
  }
  throw new Error(`Timeout for job ${jobId}`);
}

// ─── USER HELPERS ─────────────────────────────────────────────────────────────
    
async function getUserId() {
  try {
    const accounts = await browser.accounts.list();
    if (accounts.length > 0) {
      const ids = accounts[0].identities || [];
      if (ids.length > 0) return ids[0].email;
    }
  } catch (e) { console.error("getUserId:", e); }
  return "unknown@user.com";
}

async function getUserPreferences() {
  const s = await _getSettings();
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
  const backendUrl = await getBackendUrl();
  const apiEndpoint = `${backendUrl}/chat`;
  const prompt = action === "summarize" ? SUMMARIZE_PROMPT + content : content;
  const response = await fetch(apiEndpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt })
  });
  if (!response.ok) throw new Error(`Flask API error: ${response.status}`);
  const data = await response.json();
  if (data.error) throw new Error(`Flask API error: ${data.error}`);
  if (data.response) return data.response;
  throw new Error("Unexpected API response format");
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
  



