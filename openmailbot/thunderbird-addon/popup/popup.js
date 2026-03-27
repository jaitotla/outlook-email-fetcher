/**
 * OpenMailBot — popup.js
 * Full feature parity with gmail_summariser.gs
 */

"use strict";

// ── STATE ──────────────────────────────────────────────
let currentMessageId = null;
let currentSummary    = "";
let chatHistory       = [];
let localFilters      = [];        // working copy edited before save

const ALL_VIEWS = [
  "main-menu", "loading", "summary-view", "draft-view",
  "chat-view", "error-view", "settings-view", "advanced-view", "bulk-status-view"
];

// ── INIT ───────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  try {
    const tabs = await browser.tabs.query({ active: true, currentWindow: true });
    const msg  = await browser.messageDisplay.getDisplayedMessage(tabs[0].id);
    if (msg) {
      currentMessageId = msg.id;
    } else {
      showError("No email selected. Please open an email first.");
      return;
    }
    bindEvents();
  } catch (e) {
    showError("Failed to initialise: " + e.message);
  }
});

// ── EVENT BINDING ──────────────────────────────────────
function bindEvents() {
  // Main menu
  on("summarize-btn", "click", handleSummarize);
  on("chat-btn",      "click", handleShowChat);
  on("draft-btn",     "click", handleDraftWithAttachments);
  on("settings-btn",  "click", handleOpenSettings);
  on("advanced-btn",  "click", handleOpenAdvanced);

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

  // Settings view
  on("save-settings-btn",    "click", handleSaveSettings);
  on("sync-settings-btn",    "click", handleSyncSettings);
  on("reset-settings-btn",   "click", handleResetSettings);
  on("back-from-settings-btn","click", showMainMenu);

  // Advanced view
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
  on("back-from-bulk-btn",   "click", showView.bind(null, "advanced-view"));
}

function on(id, event, fn) {
  const el = document.getElementById(id);
  if (el) el.addEventListener(event, fn);
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
    const resp = await send("summarizeThread", { messageId: currentMessageId });
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
    const resp = await send("createDraft", { messageId: currentMessageId, summary: currentSummary });
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

// ── DRAFT WITH ATTACHMENTS ─────────────────────────────
async function handleDraftWithAttachments() {
  try {
    showLoading("Creating draft + indexing attachments…");
    const resp = await send("draftWithAttachments", { messageId: currentMessageId });
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
    const resp = await send("chatWithThread", { messageId: currentMessageId, question: q });
    chatHistory.push({ role: "assistant", content: resp.answer || "(no answer)" });
    renderChat();
    showView("chat-view");
  } catch (e) {
    chatHistory.pop();
    showError("Chat error: " + e.message);
  }
}

// ── SETTINGS ───────────────────────────────────────────
async function handleOpenSettings() {
  try {
    showLoading("Loading settings…");
    const resp = await send("loadSettings");
    const s = resp.settings || {};
    setVal("s-backend-url",  s.backend_url        || "http://43.204.98.38:5050");
    setVal("s-mode",         s.mode               || "inbuilt");
    setVal("s-llm-provider", s.llm_provider        || "inbuilt");
    setVal("s-llm-api-key",  s.llm_api_key         || "");
    setVal("s-llm-model",    s.llm_model           || "gpt-4o-mini");
    setVal("s-llm-base-url", s.llm_base_url        || "");
    setVal("s-emb-provider", s.embedding_provider  || "inbuilt");
    setVal("s-emb-api-key",  s.embedding_api_key   || "");
    setVal("s-emb-model",    s.embedding_model     || "text-embedding-3-small");
    setVal("s-vec-provider", s.vector_provider     || "inbuilt");
    setVal("s-vec-url",      s.vector_url          || "");
    setVal("s-vec-api-key",  s.vector_api_key      || "");
    setVal("s-user-name",    s.user_name           || "");
    setVal("s-user-position",s.user_position       || "");
    setVal("s-user-tone",    s.user_tone           || "professional");
    setVal("s-system-prompt",s.system_prompt       || "");
    hideStatus("settings-status");
    showView("settings-view");
  } catch (e) {
    showError("Could not load settings: " + e.message);
  }
}

async function handleSaveSettings() {
  const settings = {
    backend_url       : getVal("s-backend-url"),
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
    await send("saveSettings", { settings });
    setStatus("settings-status", "✅ Settings saved.", false);
  } catch (e) {
    setStatus("settings-status", "❌ Save failed: " + e.message, true);
  }
}

async function handleSyncSettings() {
  try {
    await send("syncSettings", {});
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

// ── ADVANCED ───────────────────────────────────────────
async function handleOpenAdvanced() {
  try {
    showLoading("Loading advanced settings…");
    const [filtersResp, monthsResp] = await Promise.all([
      send("getDomainFilters"),
      send("getProcessMonths")
    ]);
    localFilters = filtersResp.filters || [];
    renderFilterList();
    setVal("adv-months", monthsResp.months || "3");
    hideStatus("adv-filter-result");
    showView("advanced-view");
  } catch (e) {
    showError("Could not load advanced settings: " + e.message);
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
    await send("saveDomainFilters", { filters: localFilters });
    await send("saveProcessMonths", { months: getVal("adv-months") });
    setStatus("adv-filter-result", "✅ Filters & months saved.", false);
  } catch (e) {
    setStatus("adv-filter-result", "❌ Save failed: " + e.message, true);
  }
}

async function handleTestFilters() {
  try {
    setStatus("adv-filter-result", "Testing…", false);
    const resp = await send("testDomainFilters");
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
  const monthLabel = months === "1" ? "1 month" :
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
  try {
    // Save months & filters first
    await send("saveProcessMonths", { months });
    await send("saveDomainFilters", { filters: localFilters });
    showLoading("Starting bulk indexing…");
    await send("runBulkProcess", { months });
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
  try {
    const resp = await send("getBulkJobStatus");
    const state = resp.state;
    if (!state) {
      setText("bs-status",   "No job running");
      setText("bs-range",    "—");
      setText("bs-labeled",  "—");
      setText("bs-skipped",  "—");
      setText("bs-filtered", "—");
      setText("bs-errors",   "—");
      return;
    }
    const st = state.stats || {};
    let statusTxt = state.status || "unknown";
    if (statusTxt === "running")     statusTxt = "⏳ Running\u2026";
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
  } catch (e) {
    console.error("Bulk status error:", e);
  }
}

async function handleCancelBulk() {
  try {
    await send("cancelBulkJob");
    setTimeout(handleRefreshBulkStatus, 800);
  } catch (e) {
    console.error("Cancel error:", e);
  }
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


