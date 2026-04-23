/**
 * Options / Settings script for OpenMailBot
 * Two-page onboarding flow:
 *   Page 1 — Mode + Agent URL (+ Connect handshake for non-Manotr)
 *   Page 2 — LLM / Embedding / Vector / Profile / Advanced + Save & Verify
 */

const MANOTR_AGENT_URL = "http://omb.manotr.com";
const DEFAULT_BACKEND_URL = MANOTR_AGENT_URL;

// ─── Handshake state ─────────────────────────────────────────────────────────
let _handshakeOk = false;

// ─── Static model catalogues (curated, fallback if API fetch fails) ─────────
const MODELS = {
  llm: {
    openai: [
      "gpt-4o", "gpt-4o-mini",
      "gpt-4-turbo", "gpt-4",
      "gpt-3.5-turbo",
      "o1", "o1-mini", "o1-preview"
    ],
    anthropic: [
      "claude-3-5-sonnet-20241022",
      "claude-3-5-haiku-20241022",
      "claude-3-opus-20240229",
      "claude-3-sonnet-20240229",
      "claude-3-haiku-20240307"
    ],
    groq: [
      "llama-3.3-70b-versatile",
      "llama-3.1-8b-instant",
      "llama-3.1-70b-versatile",
      "mixtral-8x7b-32768",
      "gemma2-9b-it",
      "gemma-7b-it"
    ],
    // Ollama: popular models — augmented dynamically after "Fetch Ollama Models"
    ollama: [
      "llama3.3", "llama3.2", "llama3.1",
      "mistral", "mixtral",
      "phi4", "phi3",
      "qwen2.5", "qwen2",
      "deepseek-r1", "deepseek-coder-v2",
      "gemma2", "gemma",
      "codellama", "llava"
    ]
  },
  embedding: {
    openai: [
      "text-embedding-3-small",
      "text-embedding-3-large",
      "text-embedding-ada-002"
    ],
    ollama: [
      "nomic-embed-text",
      "mxbai-embed-large",
      "snowflake-arctic-embed",
      "bge-large",
      "all-minilm"
    ]
  }
};

// ─── Helpers ──────────────────────────────────────────────────────────────────
async function getAgentUrl() {
  try {
    const r = await browser.storage.local.get("user_settings");
    return (r.user_settings && (r.user_settings.agent_url || r.user_settings.backend_url))
           || DEFAULT_BACKEND_URL;
  } catch (e) { return DEFAULT_BACKEND_URL; }
}

// Alias kept for compatibility
async function getBackendUrl() { return getAgentUrl(); }

/** Populate a <select> with an array of model id strings */
function populateModelSelect(selectEl, models, currentValue) {
  selectEl.innerHTML = "";
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "— Select a model —";
  selectEl.appendChild(placeholder);

  for (const m of models) {
    const opt = document.createElement("option");
    opt.value = m;
    opt.textContent = m;
    selectEl.appendChild(opt);
  }
  if (currentValue) selectEl.value = currentValue;
}

/** Set status text + CSS class for a status span */
function setStatus(spanId, msg, type) {
  const el = document.getElementById(spanId);
  if (!el) return;
  el.textContent = msg;
  el.className = "connect-status" + (type ? " connect-status--" + type : "");
}

// Default settings (page-2 values)
const DEFAULT_SETTINGS = {
  agent_url: MANOTR_AGENT_URL,
  mode: "",
  llm_provider: "manotr",
  llm_api_key: "",
  llm_model: "gpt-4o-mini",
  llm_base_url: "",
  llm_ollama_api_key: "",
  embedding_provider: "manotr",
  embedding_api_key: "",
  embedding_model: "text-embedding-3-small",
  embedding_base_url: "",
  embedding_ollama_api_key: "",
  vector_provider: "manotr",
  vector_url: "",
  vector_api_key: "",
  user_name: "",
  user_position: "",
  user_tone: "professional",
  system_prompt: ""
};

// Load the bundled addon_config.json
async function getAddonConfig() {
  try {
    const url  = browser.runtime.getURL("addon_config.json");
    const resp = await fetch(url);
    if (resp.ok) return await resp.json();
  } catch (e) { console.warn("addon_config.json not loaded:", e.message); }
  return {};
}

// ─── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  await detectAndDisplayEmail();
  await loadSettings();
  setupEventListeners();
});

// ─── Email detection ──────────────────────────────────────────────────────────
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

// ─── Page navigation ──────────────────────────────────────────────────────────
function showPage(n) {
  document.getElementById("page-1").classList.toggle("hidden", n !== 1);
  document.getElementById("page-2").classList.toggle("hidden", n !== 2);
}

// ─── Mode field logic ─────────────────────────────────────────────────────────
function updateModeFields() {
  const mode          = document.getElementById("mode").value;
  const agentUrlGroup = document.getElementById("agent-url-group");
  const urlDisplay    = document.getElementById("agent-url-display");
  const urlInput      = document.getElementById("agent_url");
  const urlHint       = document.getElementById("agent-url-hint");
  const connectRow    = document.getElementById("connect-row");
  const nextBtn       = document.getElementById("next-btn");
  const urlStar       = document.getElementById("agent-url-star");

  _handshakeOk = false;
  setConnectStatus("", "");

  if (mode === "manotr") {
    agentUrlGroup.classList.remove("hidden");
    urlDisplay.classList.remove("hidden");
    urlInput.classList.add("hidden");
    urlInput.value = MANOTR_AGENT_URL;
    urlInput.disabled = true;
    connectRow.classList.add("hidden");
    if (urlStar) urlStar.classList.add("hidden");
    urlHint.innerHTML = "<em>Hosted by Manotr — no configuration needed.</em>";
    nextBtn.disabled = false;

  } else if (mode) {
    agentUrlGroup.classList.remove("hidden");
    urlDisplay.classList.add("hidden");
    urlInput.classList.remove("hidden");
    urlInput.disabled = false;  // Ensure field is enabled
    urlInput.removeAttribute("disabled");  // Remove disabled attribute if present
    connectRow.classList.remove("hidden");
    if (urlStar) urlStar.classList.remove("hidden");
    urlHint.innerHTML = "<em>Enter the URL where your agent server is running, then click <strong>Connect</strong>.</em>";
    nextBtn.disabled = true;
    evaluateNextBtn();

  } else {
    agentUrlGroup.classList.add("hidden");
    urlInput.value = "";
    urlInput.disabled = true;
    connectRow.classList.add("hidden");
    nextBtn.disabled = true;
  }
}

function evaluateNextBtn() {
  const mode = document.getElementById("mode").value;
  if (mode === "manotr") return;
  const url = document.getElementById("agent_url").value.trim();
  document.getElementById("next-btn").disabled = !(url && _handshakeOk);
}

// ─── Connect / Handshake ──────────────────────────────────────────────────────
function setConnectStatus(msg, type) {
  const el = document.getElementById("connect-status");
  el.textContent = msg;
  el.className = "connect-status" + (type ? " connect-status--" + type : "");
}

async function handleConnect() {
  const rawUrl = document.getElementById("agent_url").value.trim();
  if (!rawUrl) {
    setConnectStatus("Please enter an agent URL first.", "error");
    return;
  }

  const baseUrl = rawUrl.replace(/\/+$/, "");
  const btn = document.getElementById("connect-btn");
  btn.disabled = true;
  setConnectStatus("Connecting…", "");

  try {
    const resp = await fetch(`${baseUrl}/handshake`, {
      method: "GET",
      headers: { "Accept": "application/json" },
      signal: AbortSignal.timeout(8000),
    });

    if (resp.ok) {
      const data = await resp.json().catch(() => ({}));
      if (data.handshake === true || data.status === "ok") {
        _handshakeOk = true;
        setConnectStatus("✅ Connected — agent is running!", "success");
        evaluateNextBtn();
      } else {
        throw new Error("Unexpected response from agent.");
      }
    } else {
      throw new Error(`Agent returned HTTP ${resp.status}.`);
    }
  } catch (err) {
    _handshakeOk = false;
    evaluateNextBtn();
    const msg = err.name === "TimeoutError"
      ? "Connection timed out. Is the server running?"
      : `Could not connect: ${err.message}`;
    setConnectStatus("❌ " + msg, "error");
  } finally {
    btn.disabled = false;
  }
}

// ─── Provider sub-field visibility + model population ────────────────────────

function updateLLMFields(preserveModel) {
  const provider      = document.getElementById("llm_provider").value;
  const apiKeyGroup   = document.getElementById("llm-api-key-group");
  const modelGroup    = document.getElementById("llm-model-group");
  const baseUrlGroup  = document.getElementById("llm-base-url-group");
  const ollamaKeyGrp  = document.getElementById("llm-ollama-api-key-group");
  const ollamaFetch   = document.getElementById("llm-ollama-fetch-group");
  const testGroup     = document.getElementById("llm-test-group");

  const isCloud  = ["openai", "anthropic", "groq"].includes(provider);
  const isOllama = provider === "ollama";
  const isActive = provider !== "manotr";

  apiKeyGroup.classList.toggle("hidden",  !isCloud);
  baseUrlGroup.classList.toggle("hidden",  !isOllama);
  ollamaKeyGrp.classList.toggle("hidden",  !isOllama);
  ollamaFetch.classList.toggle("hidden",   !isOllama);
  modelGroup.classList.toggle("hidden",    !isActive);
  testGroup.classList.toggle("hidden",     !isActive);

  // Populate model dropdown for static providers
  if (isActive) {
    const select   = document.getElementById("llm_model");
    const current  = preserveModel || select.value;
    const list     = MODELS.llm[provider] || [];
    populateModelSelect(select, list, current);
  }

  setStatus("llm-test-status", "", "");
}

function updateEmbeddingFields(preserveModel) {
  const provider      = document.getElementById("embedding_provider").value;
  const apiKeyGroup   = document.getElementById("embedding-api-key-group");
  const modelGroup    = document.getElementById("embedding-model-group");
  const ollamaUrlGrp  = document.getElementById("embedding-ollama-url-group");
  const ollamaKeyGrp  = document.getElementById("embedding-ollama-api-key-group");
  const ollamaFetch   = document.getElementById("embedding-ollama-fetch-group");
  const testGroup     = document.getElementById("embedding-test-group");

  const isOpenAI = provider === "openai";
  const isOllama = provider === "ollama";
  const isActive = provider !== "manotr";

  apiKeyGroup.classList.toggle("hidden",   !isOpenAI);
  ollamaUrlGrp.classList.toggle("hidden",  !isOllama);
  ollamaKeyGrp.classList.toggle("hidden",  !isOllama);
  ollamaFetch.classList.toggle("hidden",   !isOllama);
  modelGroup.classList.toggle("hidden",    !isActive);
  testGroup.classList.toggle("hidden",     !isActive);

  if (isActive) {
    const select  = document.getElementById("embedding_model");
    const current = preserveModel || select.value;
    const list    = MODELS.embedding[provider] || [];
    populateModelSelect(select, list, current);
  }

  setStatus("embedding-test-status", "", "");
}

function updateVectorFields() {
  const provider    = document.getElementById("vector_provider").value;
  const urlGroup    = document.getElementById("vector-url-group");
  const apiKeyGroup = document.getElementById("vector-api-key-group");
  const testGroup   = document.getElementById("vector-test-group");

  const needsConfig = provider !== "manotr";
  urlGroup.classList.toggle("hidden",    !needsConfig);
  apiKeyGroup.classList.toggle("hidden", !needsConfig);
  testGroup.classList.toggle("hidden",   !needsConfig);
  setStatus("vector-test-status", "", "");
}

// ─── Ollama model fetch (via agent validate-provider proxy) ───────────────────
async function handleFetchOllamaModels(section) {
  // section = "llm" | "embedding"
  const urlFieldId    = section === "llm" ? "llm_base_url"        : "embedding_base_url";
  const keyFieldId    = section === "llm" ? "llm_ollama_api_key"  : "embedding_ollama_api_key";
  const statusSpanId  = section + "-fetch-status";
  const modelSelectId = section + "_model";
  const fetchBtn      = document.getElementById(`${section}-fetch-models-btn`);

  const ollama_url = (document.getElementById(urlFieldId)?.value || "").trim() || "http://localhost:11434";
  const ollama_key = (document.getElementById(keyFieldId)?.value || "").trim();

  fetchBtn.disabled = true;
  setStatus(statusSpanId, "Fetching models…", "");

  try {
    const agentUrl = await getAgentUrl();
    const resp = await fetch(`${agentUrl}/api/validate-provider`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        provider_type: section,
        provider: "ollama",
        base_url: ollama_url,
        api_key: ollama_key
      }),
      signal: AbortSignal.timeout(15000)
    });

    const data = await resp.json();
    if (data.valid && data.models && data.models.length > 0) {
      const select  = document.getElementById(modelSelectId);
      const current = select.value;
      populateModelSelect(select, data.models, current);
      setStatus(statusSpanId, `✅ ${data.models.length} model(s) loaded`, "success");
    } else if (data.valid) {
      setStatus(statusSpanId, "⚠️ Ollama reachable but no models installed. Run 'ollama pull <model>'.", "error");
    } else {
      setStatus(statusSpanId, "❌ " + (data.message || "Could not reach Ollama"), "error");
    }
  } catch (err) {
    const msg = err.name === "TimeoutError" ? "Timed out" : err.message;
    setStatus(statusSpanId, "❌ " + msg, "error");
  } finally {
    fetchBtn.disabled = false;
  }
}

// ─── Provider API validation (called on Test buttons + on Save) ───────────────
/**
 * Validate a provider section by calling the agent's /api/validate-provider
 * Returns { valid, message }
 */
async function validateProvider(providerType, provider, apiKey, baseUrl, model) {
  const agentUrl = await getAgentUrl();
  try {
    const resp = await fetch(`${agentUrl}/api/validate-provider`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        provider_type: providerType,
        provider,
        api_key:  apiKey  || "",
        base_url: baseUrl || "",
        model:    model   || ""
      }),
      signal: AbortSignal.timeout(20000)
    });
    return await resp.json();
  } catch (err) {
    return { valid: false, message: err.message };
  }
}

async function handleTestProvider(section) {
  // section = "llm" | "embedding" | "vector"
  const statusId = section + "-test-status";
  const btn      = document.getElementById(section + "-test-btn");

  let provider, apiKey, baseUrl, model;

  if (section === "llm") {
    provider = document.getElementById("llm_provider").value;
    apiKey   = document.getElementById("llm_api_key")?.value || "";
    baseUrl  = document.getElementById("llm_base_url")?.value
               || document.getElementById("llm_ollama_api_key")?.value || "";
    // For Ollama the base_url is llm_base_url; api_key comes from llm_ollama_api_key
    if (provider === "ollama") {
      apiKey  = document.getElementById("llm_ollama_api_key")?.value || "";
      baseUrl = document.getElementById("llm_base_url")?.value || "";
    }
    model = document.getElementById("llm_model")?.value || "";

  } else if (section === "embedding") {
    provider = document.getElementById("embedding_provider").value;
    apiKey   = document.getElementById("embedding_api_key")?.value || "";
    baseUrl  = "";
    if (provider === "ollama") {
      apiKey  = document.getElementById("embedding_ollama_api_key")?.value || "";
      baseUrl = document.getElementById("embedding_base_url")?.value || "";
    }
    model = document.getElementById("embedding_model")?.value || "";

  } else { // vector
    provider = document.getElementById("vector_provider").value;
    apiKey   = document.getElementById("vector_api_key")?.value || "";
    baseUrl  = document.getElementById("vector_url")?.value || "";
    model    = "";
  }

  if (provider === "manotr") {
    setStatus(statusId, "✅ Manotr (built-in) — no validation needed", "success");
    return { valid: true };
  }

  btn.disabled = true;
  setStatus(statusId, "Testing…", "");

  const result = await validateProvider(section, provider, apiKey, baseUrl, model);
  setStatus(statusId, (result.valid ? "✅ " : "❌ ") + result.message, result.valid ? "success" : "error");

  // Auto-populate models if validation succeeded and models were returned
  if (result.valid && result.models && result.models.length > 0) {
    const modelSelectId = section + "_model";
    const modelSelect   = document.getElementById(modelSelectId);
    if (modelSelect && section !== "vector") {
      const currentValue = modelSelect.value;
      populateModelSelect(modelSelect, result.models, currentValue);
      console.log(`✓ Auto-populated ${result.models.length} models for ${section}/${provider}`);
    }
  }

  btn.disabled = false;
  return result;
}

// ─── Event listeners ──────────────────────────────────────────────────────────
function setupEventListeners() {
  // Page 1
  document.getElementById("mode").addEventListener("change", updateModeFields);
  document.getElementById("agent_url").addEventListener("input", () => {
    _handshakeOk = false;
    setConnectStatus("", "");
    evaluateNextBtn();
  });
  document.getElementById("connect-btn").addEventListener("click", handleConnect);
  document.getElementById("next-btn").addEventListener("click", () => {
    const mode = document.getElementById("mode").value;
    if (!mode) { showPage1Status("Please select a mode.", "error"); return; }
    if (mode !== "manotr" && !_handshakeOk) {
      showPage1Status("Please connect to your agent URL before continuing.", "error");
      return;
    }
    showPage(2);
  });

  // Page 2
  document.getElementById("back-btn").addEventListener("click", () => showPage(1));
  document.getElementById("settings-form").addEventListener("submit", handleSave);
  document.getElementById("reset-btn").addEventListener("click", handleReset);

  document.getElementById("llm_provider").addEventListener("change", () => updateLLMFields());
  document.getElementById("embedding_provider").addEventListener("change", () => updateEmbeddingFields());
  document.getElementById("vector_provider").addEventListener("change", updateVectorFields);

  // Test buttons
  document.getElementById("llm-test-btn")?.addEventListener("click", () => handleTestProvider("llm"));
  document.getElementById("embedding-test-btn")?.addEventListener("click", () => handleTestProvider("embedding"));
  document.getElementById("vector-test-btn")?.addEventListener("click", () => handleTestProvider("vector"));

  // Ollama fetch buttons
  document.getElementById("llm-fetch-models-btn")?.addEventListener("click", () => handleFetchOllamaModels("llm"));
  document.getElementById("embedding-fetch-models-btn")?.addEventListener("click", () => handleFetchOllamaModels("embedding"));
}

function showPage1Status(msg, type) {
  const el = document.getElementById("page1-status");
  el.textContent = msg;
  el.className = `status-message ${type}`;
  el.classList.remove("hidden");
  setTimeout(() => el.classList.add("hidden"), 5000);
}

// ─── Load settings ────────────────────────────────────────────────────────────
async function loadSettings() {
  try {
    const result = await browser.storage.local.get(
      ["user_settings", "domain_filters", "process_last_n_months"]
    );
    const rawSettings = result.user_settings || DEFAULT_SETTINGS;

    // Normalise legacy field names
    const s = Object.assign({}, rawSettings);
    if (s.backend_url && !s.agent_url) s.agent_url = s.backend_url;
    for (const key of ["mode", "llm_provider", "embedding_provider", "vector_provider"]) {
      if (s[key] === "inbuilt") s[key] = "manotr";
    }

    // Populate page-1 fields
    const modeEl = document.getElementById("mode");
    if (modeEl && s.mode) modeEl.value = s.mode;

    const urlInput = document.getElementById("agent_url");
    if (urlInput && s.agent_url) urlInput.value = s.agent_url;

    // Populate page-2 plain text/password inputs (skip selects — handled below)
    const skipSelects = ["mode", "agent_url", "llm_provider", "embedding_provider", "vector_provider",
                         "llm_model", "embedding_model", "user_tone"];
    Object.keys(s).forEach(key => {
      if (skipSelects.includes(key)) return;
      const el = document.getElementById(key);
      if (el) el.value = s[key] || "";
    });

    // Populate provider selects + model dropdowns (order matters)
    const llmProvEl = document.getElementById("llm_provider");
    if (llmProvEl && s.llm_provider) llmProvEl.value = s.llm_provider;
    updateLLMFields(s.llm_model);

    const embProvEl = document.getElementById("embedding_provider");
    if (embProvEl && s.embedding_provider) embProvEl.value = s.embedding_provider;
    updateEmbeddingFields(s.embedding_model);

    const vecProvEl = document.getElementById("vector_provider");
    if (vecProvEl && s.vector_provider) vecProvEl.value = s.vector_provider;
    updateVectorFields();

    // Tone select
    const toneEl = document.getElementById("user_tone");
    if (toneEl && s.user_tone) toneEl.value = s.user_tone;

    // Domain filters
    const filtersEl = document.getElementById("domain_filters");
    if (filtersEl) {
      const stored   = result.domain_filters || [];
      const cfg      = await getAddonConfig();
      const cfgDoms  = (cfg.domain_filters && cfg.domain_filters.blocked_domains)  || [];
      const cfgAddrs = (cfg.domain_filters && cfg.domain_filters.blocked_addresses) || [];
      filtersEl.value = [...new Set([...stored, ...cfgDoms, ...cfgAddrs])].join("\n");
    }

    // Process months
    const monthsEl = document.getElementById("process_months");
    if (monthsEl) monthsEl.value = result.process_last_n_months || "3";

    // Apply visibility rules
    updateModeFields();

    // Page routing for returning users
    const savedMode = s.mode || "";
    if (savedMode === "manotr") {
      showPage(2);
    } else if (savedMode && s.agent_url) {
      showPage(1);
    }

    console.log("Settings loaded successfully.");
  } catch (error) {
    console.error("Error loading settings:", error);
    showStatus("Error loading settings: " + error.message, "error");
  }
}

// ─── Save settings ────────────────────────────────────────────────────────────
async function handleSave(event) {
  event.preventDefault();

  const saveBtn = document.getElementById("save-btn");
  if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = "💾 Saving…"; }

  try {
    const form     = document.getElementById("settings-form");
    const formData = new FormData(form);
    const settings = {};
    for (const [key, value] of formData.entries()) {
      settings[key] = value;
    }

    // Inject page-1 values
    settings.mode      = document.getElementById("mode").value;
    settings.agent_url = document.getElementById("agent_url").value.trim() || MANOTR_AGENT_URL;

    // Domain filters (stored separately)
    const filtersRaw = settings.domain_filters || "";
    delete settings.domain_filters;
    const filters = filtersRaw.split(/\n|,/).map(f => f.trim().toLowerCase()).filter(Boolean);
    await browser.storage.local.set({ domain_filters: filters });

    // Process months (stored separately)
    const monthsVal = settings.process_months || "3";
    delete settings.process_months;
    await browser.storage.local.set({ process_last_n_months: monthsVal });

    await browser.storage.local.set({ user_settings: settings });

    // ── Validate each configured provider after saving ──────────────────────
    if (saveBtn) saveBtn.textContent = "🔍 Verifying providers…";

    const validationResults = {};

    const llmProv = settings.llm_provider || "manotr";
    if (llmProv !== "manotr") {
      const llmApiKey  = llmProv === "ollama" ? (settings.llm_ollama_api_key || "") : (settings.llm_api_key || "");
      const llmBaseUrl = settings.llm_base_url || "";
      validationResults.llm = await validateProvider("llm", llmProv, llmApiKey, llmBaseUrl, settings.llm_model || "");
      setStatus("llm-test-status",
        (validationResults.llm.valid ? "✅ " : "❌ ") + validationResults.llm.message,
        validationResults.llm.valid ? "success" : "error");
      
      // Auto-populate models if returned
      if (validationResults.llm.valid && validationResults.llm.models && validationResults.llm.models.length > 0) {
        const llmSelect = document.getElementById("llm_model");
        if (llmSelect) populateModelSelect(llmSelect, validationResults.llm.models, settings.llm_model || "");
      }
    }

    const embProv = settings.embedding_provider || "manotr";
    if (embProv !== "manotr") {
      const embApiKey  = embProv === "ollama" ? (settings.embedding_ollama_api_key || "") : (settings.embedding_api_key || "");
      const embBaseUrl = settings.embedding_base_url || "";
      validationResults.embedding = await validateProvider("embedding", embProv, embApiKey, embBaseUrl, settings.embedding_model || "");
      setStatus("embedding-test-status",
        (validationResults.embedding.valid ? "✅ " : "❌ ") + validationResults.embedding.message,
        validationResults.embedding.valid ? "success" : "error");
      
      // Auto-populate models if returned
      if (validationResults.embedding.valid && validationResults.embedding.models && validationResults.embedding.models.length > 0) {
        const embSelect = document.getElementById("embedding_model");
        if (embSelect) populateModelSelect(embSelect, validationResults.embedding.models, settings.embedding_model || "");
      }
    }

    const vecProv = settings.vector_provider || "manotr";
    if (vecProv !== "manotr") {
      validationResults.vector = await validateProvider("vector", vecProv, settings.vector_api_key || "", settings.vector_url || "", "");
      setStatus("vector-test-status",
        (validationResults.vector.valid ? "✅ " : "❌ ") + validationResults.vector.message,
        validationResults.vector.valid ? "success" : "error");
    }

    // Sync to backend (best-effort)
    try {
      await syncSettingsToBackend(settings);
    } catch (syncErr) {
      console.log("Settings sync to backend failed:", syncErr.message);
    }

    // Determine overall status
    const anyFailed = Object.values(validationResults).some(r => !r.valid);
    if (anyFailed) {
      showStatus("⚠️ Settings saved, but some providers failed validation — check the highlighted sections.", "error");
    } else {
      showStatus("✅ Settings saved and all providers verified!", "success");
    }

  } catch (error) {
    console.error("Error saving settings:", error);
    showStatus("❌ Error saving settings: " + error.message, "error");
  } finally {
    if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = "💾 Save & Verify"; }
  }
}

// ─── Reset settings ───────────────────────────────────────────────────────────
async function handleReset() {
  if (!confirm("Are you sure you want to reset all settings to defaults?")) return;
  try {
    await browser.storage.local.remove(
      ["user_settings", "domain_filters", "process_last_n_months"]
    );

    document.getElementById("mode").value = "";
    document.getElementById("agent_url").value = "";
    _handshakeOk = false;
    setConnectStatus("", "");
    updateModeFields();

    Object.keys(DEFAULT_SETTINGS).forEach(key => {
      if (["mode", "agent_url", "llm_provider", "embedding_provider", "vector_provider",
           "llm_model", "embedding_model", "user_tone"].includes(key)) return;
      const el = document.getElementById(key);
      if (el) el.value = DEFAULT_SETTINGS[key] || "";
    });

    const filtersEl = document.getElementById("domain_filters");
    if (filtersEl) filtersEl.value = "";
    const monthsEl = document.getElementById("process_months");
    if (monthsEl) monthsEl.value = "3";

    document.getElementById("llm_provider").value = "manotr";
    document.getElementById("embedding_provider").value = "manotr";
    document.getElementById("vector_provider").value = "manotr";
    document.getElementById("user_tone").value = "professional";

    updateLLMFields();
    updateEmbeddingFields();
    updateVectorFields();

    showPage(1);
    showStatus("🔄 Settings reset to defaults!", "success");
  } catch (error) {
    console.error("Error resetting settings:", error);
    showStatus("❌ Error resetting settings: " + error.message, "error");
  }
}

// ─── Sync to backend ──────────────────────────────────────────────────────────
async function syncSettingsToBackend(settings) {
  const userId     = await getUserId();
  const backendUrl = await getBackendUrl();
  const endpoint   = `${backendUrl}/api/settings`;

  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, settings }),
  });

  if (!response.ok) {
    throw new Error(`Backend returned error: ${response.status} - ${await response.text()}`);
  }
  return response.json();
}

// ─── User ID ──────────────────────────────────────────────────────────────────
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

// ─── Status message ───────────────────────────────────────────────────────────
function showStatus(message, type) {
  const statusEl = document.getElementById("status-message");
  statusEl.textContent = message;
  statusEl.className = `status-message ${type}`;
  statusEl.classList.remove("hidden");
  setTimeout(() => statusEl.classList.add("hidden"), 7000);
}