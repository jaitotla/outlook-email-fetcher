/**
 * Runs automatically when a user installs the add-on.
 * Show onboarding immediately on install.
 */
function onInstall(e) {
  Logger.log("📦 onInstall triggered");

  // ── Create all labels with colors ─────────────────────────────────
  Logger.log("🏷️  Creating OpenMailBot labels...");
  try {
    createOpenMailBotLabels();
    Logger.log("✅ Labels created successfully");
  } catch (labelErr) {
    Logger.log("⚠️  Label creation failed (non-fatal): " + labelErr.message);
    // Non-fatal: continue with installation even if label creation fails
  }

  var isOnboarded = PropertiesService.getUserProperties().getProperty("onboarding_complete") === "true";

  if (isOnboarded) {
    // ── REINSTALL: onboarding was already done — force-recreate the trigger ──
    // ensureMonitorRunning() only adds a trigger if none exists, but reinstalls
    // delete all previous triggers, so we must use setupEmailMonitor() which
    // deletes stale triggers and creates a guaranteed fresh one.
    Logger.log("🔄 Reinstall detected (onboarding already complete) — force-installing monitor trigger...");
    try {
      setupEmailMonitor();
      Logger.log("✅ Monitor trigger force-installed on reinstall");
    } catch (err) {
      Logger.log("❌ onInstall monitor error: " + err.message);
    }
  } else {
    // ── FRESH INSTALL: wait until onboarding finishes before touching triggers ──
    Logger.log("🆕 Fresh install — trigger will be installed after onboarding completes");
  }

  onOpen(e);
}

/**
 * Create all OpenMailBot labels with colors.
 * Labels are created in Gmail's label list with predefined colors.
 * This matches the label definitions in the Python agent (main.py: _GMAIL_LABEL_COLORS).
 * 
 * NOTE: This function requires the Gmail Advanced Service to be enabled:
 *   Resources → Advanced Google Services → Gmail API: ON
 * 
 * Color palette reference (Gmail API official):
 * https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.labels
 */
function createOpenMailBotLabels() {
  // Label definitions matching Python agent (_GMAIL_LABEL_COLORS)
  var LABEL_DEFINITIONS = [
    { name: "Response",       bgColor: "#4a86e8", textColor: "#ffffff" },  // blue
    { name: "Fyi",            bgColor: "#16a766", textColor: "#ffffff" },  // green
    { name: "Notification",   bgColor: "#e7e7e7", textColor: "#000000" },  // light gray
    { name: "Meeting",        bgColor: "#653e9b", textColor: "#ffffff" },  // purple
    { name: "Awaiting Reply", bgColor: "#fad165", textColor: "#000000" },  // yellow
    { name: "Escalation",     bgColor: "#cc3a21", textColor: "#ffffff" },  // dark red
    { name: "Hotels",         bgColor: "#ffad47", textColor: "#000000" },  // orange
    { name: "Airline",        bgColor: "#7a4706", textColor: "#ffffff" },  // brown
    { name: "Airlines",       bgColor: "#7a4706", textColor: "#ffffff" },  // brown (alternate)
    { name: "Travel",         bgColor: "#149e60", textColor: "#ffffff" },  // green
    { name: "Restaurant",     bgColor: "#ffbc6b", textColor: "#000000" },  // light orange
    { name: "Booking",        bgColor: "#4a86e8", textColor: "#ffffff" },  // blue
    { name: "Bank",           bgColor: "#2da2bb", textColor: "#ffffff" },  // teal
    { name: "Recruitment",    bgColor: "#8e63ce", textColor: "#ffffff" }   // purple
  ];

  Logger.log("📋 Creating " + LABEL_DEFINITIONS.length + " labels...");

  // Get all existing labels (to avoid duplicates)
  var existingLabels = {};
  try {
    var response = Gmail.Users.Labels.list("me");
    if (response.labels) {
      for (var i = 0; i < response.labels.length; i++) {
        existingLabels[response.labels[i].name.toLowerCase()] = response.labels[i];
      }
    }
  } catch (e) {
    Logger.log("⚠️  Could not fetch existing labels (using Gmail Advanced Service): " + e.message);
    Logger.log("   Make sure Gmail API is enabled in Resources → Advanced Google Services");
    throw e;
  }

  // Create or update each label
  var created = 0;
  var updated = 0;
  var skipped = 0;

  for (var i = 0; i < LABEL_DEFINITIONS.length; i++) {
    var labelDef = LABEL_DEFINITIONS[i];
    var labelNameLower = labelDef.name.toLowerCase();

    try {
      if (existingLabels[labelNameLower]) {
        // Label exists — update color if different
        var existingLabel = existingLabels[labelNameLower];
        var needsUpdate = false;

        // Check if color is different
        if (!existingLabel.color ||
            existingLabel.color.backgroundColor !== labelDef.bgColor ||
            existingLabel.color.textColor !== labelDef.textColor) {
          needsUpdate = true;
        }

        if (needsUpdate) {
          Logger.log("🔄 Updating label: " + labelDef.name + " (color: " + labelDef.bgColor + ")");
          
          var updateLabel = {
            color: {
              backgroundColor: labelDef.bgColor,
              textColor: labelDef.textColor
            }
          };
          
          Gmail.Users.Labels.patch(updateLabel, "me", existingLabel.id);
          updated++;
        } else {
          Logger.log("⏭️  Skipping existing label: " + labelDef.name);
          skipped++;
        }
      } else {
        // Label doesn't exist — create it
        Logger.log("➕ Creating label: " + labelDef.name + " (color: " + labelDef.bgColor + ")");
        
        var newLabel = {
          name: labelDef.name,
          labelListVisibility: "labelShow",
          messageListVisibility: "show",
          color: {
            backgroundColor: labelDef.bgColor,
            textColor: labelDef.textColor
          }
        };
        
        Gmail.Users.Labels.create(newLabel, "me");
        created++;
      }
    } catch (labelErr) {
      Logger.log("❌ Failed to process label '" + labelDef.name + "': " + labelErr.message);
      // Continue with other labels even if one fails
    }
  }

  Logger.log("");
  Logger.log("✅ Label creation complete:");
  Logger.log("   Created: " + created);
  Logger.log("   Updated: " + updated);
  Logger.log("   Skipped: " + skipped);
  Logger.log("   Total:   " + LABEL_DEFINITIONS.length);
}

/**
 * Runs when the add-on is opened (legacy hook, kept for compatibility).
 */
function onOpen(e) {
  // Nothing special needed here; the trigger functions handle routing.
}

/**
 * Returns true if the user has completed the first-time onboarding.
 */
function isOnboardingComplete() {
  return PropertiesService.getUserProperties().getProperty("onboarding_complete") === "true";
}

/**
 * Contextual trigger — fires when the user opens a Gmail message.
 * This is the main entry point declared in appsscript.json.
 * On first use (before onboarding) it shows the onboarding wizard.
 * Afterwards it shows the normal home card.
 */
function onGmailMessageOpen(e) {
  if (!isOnboardingComplete()) {
    return [showOnboardingStep1(e)];
  }
  return [buildHomeCard()];
}

/**
 * Homepage trigger — fires when the user opens the add-on without any
 * message selected (e.g. from the Gmail sidebar icon or the Add-ons menu).
 * Declared in appsscript.json under addOns.gmail.homepageTrigger.
 * 
 * NO AUTO-SYNC HERE - emails are sent by background trigger instead.
 */
function onGmailHomepage(e) {
  console.log("📧 onGmailHomepage: Gmail sidebar opened");
  Logger.log("📧 onGmailHomepage: Gmail sidebar opened");
  
  // NO auto-sync here - background trigger handles it automatically
  
  if (!isOnboardingComplete()) {
    return [showOnboardingStep1(e)];
  }
  return [buildHomeCard()];
}

/**
 * Ensure the monitorEmails background trigger is installed.
 * Only creates a new trigger if none exists — safe to call multiple times.
 * GUARD: will not install the trigger until onboarding is complete (settings saved).
 */
function ensureMonitorRunning() {
  Logger.log("🔍 ensureMonitorRunning: checking trigger setup...");
  
  // Do not start the monitor before settings have been saved
  if (PropertiesService.getUserProperties().getProperty("onboarding_complete") !== "true") {
    Logger.log("⏸️  ensureMonitorRunning: onboarding not complete — trigger installation skipped.");
    return;
  }

  var triggers = ScriptApp.getProjectTriggers();
  Logger.log("📋 Current triggers count: " + triggers.length);
  
  for (var i = 0; i < triggers.length; i++) {
    Logger.log("  - Trigger " + i + ": " + triggers[i].getHandlerFunction());
    if (triggers[i].getHandlerFunction() === 'monitorEmails') {
      Logger.log("✅ monitorEmails trigger already exists — skipping creation");
      return; // already installed
    }
  }
  
  // Not found — create it
  Logger.log("🔧 Creating monitorEmails trigger (every 1 hour)...");
  try {
    ScriptApp.newTrigger('monitorEmails')
      .timeBased()
      .everyMinutes(1)
      .create();
    Logger.log("✅ monitorEmails trigger installed successfully!");
  } catch (triggerErr) {
    Logger.log("❌ Failed to create trigger: " + triggerErr.message);
    throw triggerErr;
  }
}



/**
 * Entry point for Gmail Add-on — checks onboarding then shows home card.
 * Called directly by navigation actions (e.g. "🏠 Go to Home" button).
 * Returns a single Card (not an array) since it is used inside card navigation.
 */
function buildAddOn(e) {
  // First-time users must complete onboarding before accessing the main UI
  if (!isOnboardingComplete()) {
    return showOnboardingStep1(e);
  }
  return buildHomeCard();
}

/**
 * The main home card (only shown after onboarding is complete)
 */
function buildHomeCard() {
  return CardService.newCardBuilder()
    .setHeader(
      CardService.newCardHeader()
        .setTitle("OpenMailBot")
        .setSubtitle("Your AI-Powered Email Assistant")
    )
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newDecoratedText()
            .setTopLabel("✦  POWERED BY Manotr  ✦")
            .setText("<b>Welcome to OpenMailBot</b>")
            .setBottomLabel("Summarize · Chat · Draft")
            .setWrapText(true)
        )
    )
    .addSection(
      CardService.newCardSection()
        .setHeader("Core Features")
        .addWidget(
          CardService.newDecoratedText()
            .setText("<b>📝  Summarize Thread</b>")
            .setBottomLabel("Thread summary")
            .setWrapText(true)
            .setButton(
              CardService.newTextButton()
                .setText("Run")
                .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
                .setBackgroundColor("#4285F4")
                .setOnClickAction(CardService.newAction().setFunctionName("summarizeThread"))
            )
        )
        .addWidget(CardService.newDivider())
        .addWidget(
          CardService.newDecoratedText()
            .setText("<b>💬  Chat with Thread</b>")
            .setBottomLabel("Ask about emails & attachments")
            .setWrapText(true)
            .setButton(
              CardService.newTextButton()
                .setText("Open")
                .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
                .setBackgroundColor("#7C4DFF")
                .setOnClickAction(CardService.newAction().setFunctionName("showChatInterface"))
            )
        )
        .addWidget(CardService.newDivider())
        .addWidget(
          CardService.newDecoratedText()
            .setText("<b>✍️  Generate Draft</b>")
            .setBottomLabel("Quick AI reply")
            .setWrapText(true)
            .setButton(
              CardService.newTextButton()
                .setText("Draft")
                .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
                .setBackgroundColor("#F4B400")
                .setOnClickAction(CardService.newAction().setFunctionName("generateDraft"))
            )
        )
        .addWidget(CardService.newDivider())
        .addWidget(
          CardService.newDecoratedText()
            .setText("<b>📎  Draft with Attachments</b>")
            .setBottomLabel("Draft with attachments")
            .setWrapText(true)
            .setButton(
              CardService.newTextButton()
                .setText("Draft")
                .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
                .setBackgroundColor("#0F9D58")
                .setOnClickAction(CardService.newAction().setFunctionName("draftWithAttachments"))
            )
        )
    )
    .addSection(
      CardService.newCardSection()
        .addWidget(CardService.newDivider())
        .addWidget(
          CardService.newTextButton()
            .setText("⚙️  Settings & Configuration")
            .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
            .setBackgroundColor("#5F6368")
            .setOnClickAction(CardService.newAction().setFunctionName("showSettingsCard"))
        )
    )
    .build();
}

// NOTE: A shorter version of draftWithAttachments existed here and was removed.
// The active implementation is further below.

// ============================================================================
// CANONICAL THREAD ID
// ============================================================================

/**
 * Returns the bare RFC Message-ID of the thread's first (root) message,
 * without angle brackets — matching the format stored by Thunderbird.
 *
 * Gmail's thread.getId() returns a Gmail-internal hex ID that IMAP clients
 * never see, so it cannot be used as a cross-client ChromaDB key.
 *
 * @param {GmailThread} thread
 * @returns {string} e.g. "86.B7.46200.5C7CDD96@mta.example.com"
 */
function getCanonicalThreadId(thread) {
  try {
    var rootMsgId = thread.getMessages()[0].getHeader('Message-ID');
    if (rootMsgId && rootMsgId.trim()) {
      // Strip RFC angle bracket wrappers: <local@domain> → local@domain
      return rootMsgId.trim().replace(/^<|>$/g, '');
    }
  } catch (e) {
    Logger.log('getCanonicalThreadId fallback to thread.getId(): ' + e.message);
  }
  return thread.getId();
}

// ============================================================================
// ONBOARDING WIZARD — shown only to first-time users, cannot be skipped
// ============================================================================

/**
 * Internal card builder for Onboarding Step 1.
 * Reads transient UI state from UserProperties (ob_prefill / ob_status_* / ob_connect_*)
 * and clears per-render state after reading so values are consumed once.
 *
 * Thunderbird parity features implemented here:
 *   • "Fill Settings from Server" button → handleFetchSettingsForOnboarding
 *   • Status/error message banner after fetch or validation failure
 *   • "Connect & Verify Server" button → handleVerifyAgentConnection
 *   • Connection status message shown beneath Agent URL
 *   • All dropdowns pre-selected from prefill data
 *   • All text inputs pre-filled from prefill data
 */
function _buildOnboardingStep1Card() {
  var userProps = PropertiesService.getUserProperties();

  // ── Read transient UI state ──────────────────────────────────────────
  var prefillJson = userProps.getProperty("ob_prefill")      || "{}";
  var statusMsg   = userProps.getProperty("ob_status_msg")   || "";
  var statusIsErr = userProps.getProperty("ob_status_error") === "true";
  var connectMsg  = userProps.getProperty("ob_connect_msg")  || "";
  var connectOk   = userProps.getProperty("ob_connect_ok")   === "true";

  // Clear per-render state (keep ob_prefill — it survives until saveOnboardingStep1 clears it)
  userProps.deleteProperty("ob_status_msg");
  userProps.deleteProperty("ob_status_error");
  userProps.deleteProperty("ob_connect_msg");
  userProps.deleteProperty("ob_connect_ok");

  var p = {};
  try { p = JSON.parse(prefillJson); } catch (ex) {}

  // Helper: pick pre-filled value or fall back to default
  var pv = function(key, def) {
    var val = p[key];
    return (val !== undefined && val !== null && String(val).trim() !== "") ? String(val) : (def || "");
  };

  // Detect selected option values for dropdown/radio pre-selection
  var modeVal  = pv("mode",               "manotr");
  var llmProv  = pv("llm_provider",       "manotr");
  var embProv  = pv("embedding_provider", "manotr");
  var vecProv  = pv("vector_provider",    "manotr");
  var toneVal  = pv("user_tone",          "professional");

  // ── Read + clear LLM/Embedding transient state for onboarding ─────────
  var obLlmMsg  = userProps.getProperty("ob_llm_msg")  || "";
  var obLlmOk   = userProps.getProperty("ob_llm_ok")   === "true";
  var obEmbMsg  = userProps.getProperty("ob_emb_msg")  || "";
  var obEmbOk   = userProps.getProperty("ob_emb_ok")   === "true";
  var obLlmModels = [];
  var obEmbModels = [];
  try { obLlmModels = JSON.parse(userProps.getProperty("ob_llm_models_" + llmProv)  || "[]"); } catch (ex) {}
  try { obEmbModels = JSON.parse(userProps.getProperty("ob_emb_models_" + embProv) || "[]"); } catch (ex) {}
  userProps.deleteProperty("ob_llm_msg");
  userProps.deleteProperty("ob_llm_ok");
  userProps.deleteProperty("ob_emb_msg");
  userProps.deleteProperty("ob_emb_ok");

  // Static curated model catalogues — shown before any API fetch
  var OB_STATIC_LLM = {
    openai:    ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo", "o1", "o1-mini"],
    anthropic: ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022",
                "claude-3-opus-20240229", "claude-3-haiku-20240307"],
    groq:      ["llama-3.3-70b-versatile", "llama-3.1-8b-instant",
                "llama-3.1-70b-versatile", "mixtral-8x7b-32768", "gemma2-9b-it"],
    ollama:    ["llama3.3", "llama3.2", "llama3.1", "mistral", "phi4",
                "qwen2.5", "deepseek-r1", "gemma2", "codellama"]
  };
  var OB_STATIC_EMB = {
    openai: ["text-embedding-3-small", "text-embedding-3-large", "text-embedding-ada-002"],
    ollama: ["nomic-embed-text", "mxbai-embed-large", "snowflake-arctic-embed", "bge-large", "all-minilm"]
  };

  var isObLlmCloud  = (["openai", "anthropic", "groq"].indexOf(llmProv) !== -1);
  var isObLlmOllama = (llmProv === "ollama");
  var isObEmbCloud  = (embProv === "openai");
  var isObEmbOllama = (embProv === "ollama");

  var card = CardService.newCardBuilder()
    .setHeader(
      CardService.newCardHeader()
        .setTitle("👋  Welcome to OpenMailBot")
        .setSubtitle("Step 1 of 2 — Your Profile & AI Setup")
    );

  // ── Intro ──────────────────────────────────────────────────────────────
  card.addSection(
    CardService.newCardSection()
      .addWidget(
        CardService.newTextParagraph()
          .setText(
            "<b>Let's get you set up in 2 quick steps.</b>\n\n" +
            "Tell us about yourself and choose how OpenMailBot should work. " +
            "You can always change these later in Settings."
          )
      )
  );

  // ── Fill Settings from Server (Thunderbird: ob-fetch-backend-btn) ─────
  var fetchSection = CardService.newCardSection()
    .setHeader("🔍  EXISTING SETTINGS")
    .addWidget(
      CardService.newTextParagraph()
        .setText(
          "Already set up on another device? Load your settings from the server to skip manual entry."
        )
    )
    .addWidget(
      CardService.newTextButton()
        .setText("🔍  Fill Settings from Server")
        .setOnClickAction(
          CardService.newAction().setFunctionName("handleFetchSettingsForOnboarding")
        )
    );
  if (statusMsg) {
    fetchSection.addWidget(
      CardService.newTextParagraph()
        .setText(statusIsErr ? "❌  " + statusMsg : "✅  " + statusMsg)
    );
  }
  card.addSection(fetchSection);

  // ── Configuration Mode ─────────────────────────────────────────────────
  card.addSection(
    CardService.newCardSection()
      .setHeader("🔧  CONFIGURATION MODE")
      .addWidget(
        CardService.newTextParagraph()
          .setText(
            "✨ <b>Manotr</b> — Zero config. OpenMailBot hosted AI, no API keys needed.\n" +
            "🖥️ <b>Local</b> — Use locally hosted services like Ollama.\n" +
            "⚡ <b>External API</b> — Bring your own API keys (OpenAI, Anthropic, Groq)."
          )
      )
      .addWidget(
        CardService.newSelectionInput()
          .setType(CardService.SelectionInputType.RADIO_BUTTON)
          .setFieldName("mode")
          .setTitle("Select Mode *")
          .addItem("✨  Manotr (Zero Configuration — Recommended)", "manotr", modeVal === "manotr")
          .addItem("🖥️  Local (Ollama / Self-hosted)",              "local",   modeVal === "local")
          .addItem("⚡  External API (Your Own API Keys)",           "external", modeVal === "external")
      )
  );

  // ── Agent URL (Thunderbird: ob-agent-url-group + ob-connect-btn) ───────
  var agentSection = CardService.newCardSection()
    .setHeader("🌐  AGENT URL")
    .addWidget(
      CardService.newTextParagraph()
        .setText(
          "Manotr mode: use <b>http://omb.manotr.com</b> (pre-filled).\n" +
          "Local/External: enter the URL where your OpenMailBot agent server is running.\n" +
          "💡 Tip: If server shows 0.0.0.0:5051, use localhost:5051 instead."
        )
    )
    .addWidget(
      CardService.newTextInput()
        .setFieldName("agent_url")
        .setTitle("Agent Server URL")
        .setValue(pv("agent_url", "http://omb.manotr.com"))
        .setHint("http://localhost:5051  ·  https://your-server.com  ·  http://omb.manotr.com")
    )
    .addWidget(
      CardService.newTextButton()
        .setText("🔗  Connect & Verify Server")
        .setOnClickAction(
          CardService.newAction().setFunctionName("handleVerifyAgentConnection")
        )
    );
  if (connectMsg) {
    agentSection.addWidget(
      CardService.newTextParagraph()
        .setText(connectOk ? "✅  " + connectMsg : "❌  " + connectMsg)
    );
  }
  card.addSection(agentSection);

  // ── User Profile (required) ────────────────────────────────────────────
  card.addSection(
    CardService.newCardSection()
      .setHeader("👤  YOUR PROFILE  (required)")
      .addWidget(
        CardService.newTextInput()
          .setFieldName("user_name")
          .setTitle("Full Name *")
          .setValue(pv("user_name", ""))
          .setHint("e.g., Alex Johnson")
      )
      .addWidget(
        CardService.newTextInput()
          .setFieldName("user_position")
          .setTitle("Job Title / Role *")
          .setValue(pv("user_position", ""))
          .setHint("e.g., Product Manager · CEO · Developer")
      )
      .addWidget(
        CardService.newTextInput()
          .setFieldName("imap_app_password")
          .setTitle("📧  Gmail App Password (for IMAP fetching)")
          .setValue(pv("imap_app_password", ""))
          .setHint("16-char password from Account settings")
      )
      .addWidget(
        CardService.newSelectionInput()
          .setType(CardService.SelectionInputType.DROPDOWN)
          .setFieldName("user_tone")
          .setTitle("Preferred Writing Tone")
          .addItem("🎯  Professional (Default)", "professional", toneVal === "professional")
          .addItem("📋  Formal & Structured",    "formal",       toneVal === "formal")
          .addItem("😊  Friendly & Warm",        "friendly",     toneVal === "friendly")
          .addItem("💬  Concise",                "concise",      toneVal === "concise")
      )
      .addWidget(
        CardService.newTextInput()
          .setFieldName("system_prompt")
          .setTitle("🧠  Custom AI Instructions (optional)")
          .setValue(pv("system_prompt", ""))
          .setHint("AI instructions for drafts & summaries")
          .setMultiline(true)
      )
  );

  // ── LLM Configuration (collapsible) ────────────────────────────────────
  var obLlmSection = CardService.newCardSection()
    .setHeader("🤖  AI LANGUAGE MODEL")
    .setCollapsible(true)
    .setNumUncollapsibleWidgets(0)
    .addWidget(
      CardService.newSelectionInput()
        .setType(CardService.SelectionInputType.DROPDOWN)
        .setFieldName("llm_provider")
        .setTitle("LLM Provider")
        .addItem("✨  Manotr (Default — no key needed)",         "manotr",    llmProv === "manotr")
        .addItem("🌐  OpenAI (GPT-4o, GPT-3.5)",                "openai",    llmProv === "openai")
        .addItem("🤖  Anthropic (Claude 3.5)",                   "anthropic", llmProv === "anthropic")
        .addItem("⚡  Groq (Llama, Mixtral — fast & free)",      "groq",      llmProv === "groq")
        .addItem("🖥️  Ollama (Local · Remote · Cloud)",          "ollama",    llmProv === "ollama")
        .setOnChangeAction(CardService.newAction().setFunctionName("handleOBLLMProviderChange"))
    );

  // Cloud providers: API key + "Validate API & Fetch Models" button
  if (isObLlmCloud) {
    obLlmSection
      .addWidget(
        CardService.newTextInput()
          .setFieldName("llm_api_key")
          .setTitle("🔑 API Key")
          .setValue(pv("llm_api_key", ""))
          .setHint(llmProv === "openai"    ? "sk-... (OpenAI key)" :
                   llmProv === "anthropic" ? "sk-ant-... (Anthropic key)" :
                                             "gsk_... (Groq key)")
      )
      .addWidget(
        CardService.newTextButton()
          .setText("✅  Validate API & Fetch Models")
          .setOnClickAction(CardService.newAction().setFunctionName("handleOBFetchLLMModels"))
      );
    if (obLlmMsg) {
      obLlmSection.addWidget(
        CardService.newTextParagraph().setText(obLlmOk ? "✅  " + obLlmMsg : "❌  " + obLlmMsg)
      );
    }
  }

  // Ollama: URL + Bearer token + 3-case explanation + "Connect & Fetch"
  if (isObLlmOllama) {
    obLlmSection
      .addWidget(
        CardService.newTextParagraph()
          .setText(
            "ℹ️  Ollama works in 3 ways:\n" +
            "  1️⃣  Local — http://localhost:11434  (no auth needed)\n" +
            "  2️⃣  Remote public — your server URL via PageKite / ngrok\n" +
            "  3️⃣  Remote secured — public URL + Bearer token"
          )
      )
      .addWidget(
        CardService.newTextInput()
          .setFieldName("llm_base_url")
          .setTitle("🔗 Ollama URL")
          .setValue(pv("llm_base_url", "http://localhost:11434"))
          .setHint("Local: http://localhost:11434  ·  Remote: https://your-ollama.com")
      )
      .addWidget(
        CardService.newTextInput()
          .setFieldName("llm_ollama_api_key")
          .setTitle("🔑 Bearer Token (optional)")
          .setValue(pv("llm_ollama_api_key", ""))
          .setHint("Only needed if your Ollama server requires authentication")
      )
      .addWidget(
        CardService.newTextButton()
          .setText("✅  Connect & Fetch Ollama Models")
          .setOnClickAction(CardService.newAction().setFunctionName("handleOBFetchLLMOllamaModels"))
      );
    if (obLlmMsg) {
      obLlmSection.addWidget(
        CardService.newTextParagraph().setText(obLlmOk ? "✅  " + obLlmMsg : "❌  " + obLlmMsg)
      );
    }
  }

  // Model selection: live fetched → static catalogue → text input fallback
  if (llmProv !== "manotr") {
    var obLlmModelList  = (obLlmModels.length > 0) ? obLlmModels : (OB_STATIC_LLM[llmProv] || []);
    var obLlmModelSaved = pv("llm_model", obLlmModelList.length > 0 ? obLlmModelList[0] : "");
    if (obLlmModelList.length > 0) {
      var obLlmModelSel = CardService.newSelectionInput()
        .setType(CardService.SelectionInputType.DROPDOWN)
        .setFieldName("llm_model")
        .setTitle("📦  Model" +
          (obLlmModels.length > 0 ? " (live — fetched from API)" : " (curated — click Validate to refresh)"));
      for (var oli = 0; oli < obLlmModelList.length; oli++) {
        var olm = obLlmModelList[oli];
        obLlmModelSel.addItem(olm, olm, olm === obLlmModelSaved);
      }
      if (obLlmModelSaved && obLlmModelList.indexOf(obLlmModelSaved) === -1) {
        obLlmModelSel.addItem("📌 " + obLlmModelSaved + " (saved)", obLlmModelSaved, true);
      }
      obLlmSection.addWidget(obLlmModelSel);
    } else {
      obLlmSection.addWidget(
        CardService.newTextInput()
          .setFieldName("llm_model")
          .setTitle("📦  Model Name")
          .setValue(obLlmModelSaved)
          .setHint("Click 'Validate & Fetch Models' above to populate this dropdown")
      );
    }
  }
  card.addSection(obLlmSection);

  // ── Embedding Configuration (collapsible) ──────────────────────────────
  var obEmbSection = CardService.newCardSection()
    .setHeader("📊  EMBEDDING ENGINE")
    .setCollapsible(true)
    .setNumUncollapsibleWidgets(0)
    .addWidget(
      CardService.newSelectionInput()
        .setType(CardService.SelectionInputType.DROPDOWN)
        .setFieldName("embedding_provider")
        .setTitle("Embedding Provider")
        .addItem("✨  Manotr (Default — no key needed)", "manotr", embProv === "manotr")
        .addItem("🌐  OpenAI Embeddings",                "openai", embProv === "openai")
        .addItem("🖥️  Ollama (Local · Remote · Cloud)",  "ollama", embProv === "ollama")
        .setOnChangeAction(CardService.newAction().setFunctionName("handleOBEmbProviderChange"))
    );

  if (isObEmbCloud) {
    obEmbSection
      .addWidget(
        CardService.newTextInput()
          .setFieldName("embedding_api_key")
          .setTitle("🔑 API Key")
          .setValue(pv("embedding_api_key", ""))
          .setHint("sk-... (OpenAI key)")
      )
      .addWidget(
        CardService.newTextButton()
          .setText("✅  Validate API & Fetch Models")
          .setOnClickAction(CardService.newAction().setFunctionName("handleOBFetchEmbeddingModels"))
      );
    if (obEmbMsg) {
      obEmbSection.addWidget(
        CardService.newTextParagraph().setText(obEmbOk ? "✅  " + obEmbMsg : "❌  " + obEmbMsg)
      );
    }
  }

  if (isObEmbOllama) {
    obEmbSection
      .addWidget(
        CardService.newTextParagraph()
          .setText(
            "ℹ️  Ollama works in 3 ways:\n" +
            "  1️⃣  Local — http://localhost:11434  (no auth needed)\n" +
            "  2️⃣  Remote public — your server URL via PageKite / ngrok\n" +
            "  3️⃣  Remote secured — public URL + Bearer token"
          )
      )
      .addWidget(
        CardService.newTextInput()
          .setFieldName("embedding_base_url")
          .setTitle("🔗 Ollama URL")
          .setValue(pv("embedding_base_url", "http://localhost:11434"))
          .setHint("Local: http://localhost:11434  ·  Remote: https://your-ollama.com")
      )
      .addWidget(
        CardService.newTextInput()
          .setFieldName("embedding_ollama_api_key")
          .setTitle("🔑 Bearer Token (optional)")
          .setValue(pv("embedding_ollama_api_key", ""))
          .setHint("Only needed if your Ollama server requires authentication")
      )
      .addWidget(
        CardService.newTextButton()
          .setText("✅  Connect & Fetch Ollama Models")
          .setOnClickAction(CardService.newAction().setFunctionName("handleOBFetchEmbeddingOllamaModels"))
      );
    if (obEmbMsg) {
      obEmbSection.addWidget(
        CardService.newTextParagraph().setText(obEmbOk ? "✅  " + obEmbMsg : "❌  " + obEmbMsg)
      );
    }
  }

  if (embProv !== "manotr") {
    var obEmbModelList  = (obEmbModels.length > 0) ? obEmbModels : (OB_STATIC_EMB[embProv] || []);
    var obEmbModelSaved = pv("embedding_model", obEmbModelList.length > 0 ? obEmbModelList[0] : "text-embedding-3-small");
    if (obEmbModelList.length > 0) {
      var obEmbModelSel = CardService.newSelectionInput()
        .setType(CardService.SelectionInputType.DROPDOWN)
        .setFieldName("embedding_model")
        .setTitle("📦  Model" +
          (obEmbModels.length > 0 ? " (live — fetched from API)" : " (curated — click Validate to refresh)"));
      for (var oei = 0; oei < obEmbModelList.length; oei++) {
        var oem = obEmbModelList[oei];
        obEmbModelSel.addItem(oem, oem, oem === obEmbModelSaved);
      }
      if (obEmbModelSaved && obEmbModelList.indexOf(obEmbModelSaved) === -1) {
        obEmbModelSel.addItem("📌 " + obEmbModelSaved + " (saved)", obEmbModelSaved, true);
      }
      obEmbSection.addWidget(obEmbModelSel);
    } else {
      obEmbSection.addWidget(
        CardService.newTextInput()
          .setFieldName("embedding_model")
          .setTitle("📦  Embedding Model")
          .setValue(obEmbModelSaved)
          .setHint("Click 'Validate & Fetch Models' above to populate this dropdown")
      );
    }
  }
  card.addSection(obEmbSection);

  // ── Vector DB Configuration (collapsible) ─────────────────────────────
  card.addSection(
    CardService.newCardSection()
      .setHeader("🗄️  VECTOR DATABASE")
      .setCollapsible(true)
      .setNumUncollapsibleWidgets(0)
      .addWidget(
        CardService.newSelectionInput()
          .setType(CardService.SelectionInputType.DROPDOWN)
          .setFieldName("vector_provider")
          .setTitle("Vector DB Provider")
          .addItem("✨  Manotr (Default)",              "manotr",   vecProv === "manotr")
          .addItem("📁  Local (ChromaDB on server)",    "local",    vecProv === "local")
          .addItem("🌲  Pinecone (Cloud)",              "pinecone", vecProv === "pinecone")
          .addItem("🎯  Qdrant (Cloud / Self-hosted)",  "qdrant",   vecProv === "qdrant")
      )
      .addWidget(
        CardService.newTextParagraph()
          .setText("💡 <b>Local:</b> Stores embeddings in agent/data/{user_id}/vector_db/ on your server.")
      )
      .addWidget(
        CardService.newTextInput()
          .setFieldName("vector_url")
          .setTitle("🔗 Server URL")
          .setValue(pv("vector_url", ""))
          .setHint("https://your-index.pinecone.io  ·  https://your-qdrant.com")
      )
      .addWidget(
        CardService.newTextInput()
          .setFieldName("vector_api_key")
          .setTitle("🔑 Vector DB API Key")
          .setValue(pv("vector_api_key", ""))
          .setHint("Leave empty for Manotr or Local ChromaDB")
      )
  );

  // ── Submit ─────────────────────────────────────────────────────────────
  card.addSection(
    CardService.newCardSection()
      .addWidget(
        CardService.newTextButton()
          .setText("Next: Email Context Setup →")
          .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
          .setBackgroundColor("#4285F4")
          .setOnClickAction(
            CardService.newAction().setFunctionName("saveOnboardingStep1")
          )
      )
  );

  return card.build();
}

/**
 * Step 1 entry point — delegates to _buildOnboardingStep1Card().
 * Called from buildAddOn (returns Card) and from the "← Back" button on step 2.
 */
function showOnboardingStep1(e) {
  return _buildOnboardingStep1Card();
}

/**
 * "Fill Settings from Server" handler.
 * Equivalent of Thunderbird's ob-fetch-backend-btn + ob-use-backend-btn flow.
 * Tries the agent_url already typed in the form, then falls back to saved settings.
 * On success: stores fetched settings as ob_prefill and re-renders the form pre-filled.
 * On failure: shows an inline error message.
 */
function handleFetchSettingsForOnboarding(e) {
  var userProps = PropertiesService.getUserProperties();
  var f = (e && e.formInput) ? e.formInput : {};

  // Resolve server URL: form value → Script Properties → saved user_settings
  var agentUrl = (f.agent_url || "").trim();
  if (!agentUrl) {
    agentUrl = PropertiesService.getScriptProperties().getProperty("FLASK_SERVER_URL") || "";
  }
  if (!agentUrl) {
    try {
      var ex = JSON.parse(userProps.getProperty("user_settings") || "{}");
      agentUrl = ex.agent_url || "";
    } catch (ex2) {}
  }

  if (!agentUrl) {
    userProps.setProperty("ob_status_msg",   "No server URL available. Enter the Agent URL first, then retry.");
    userProps.setProperty("ob_status_error", "true");
    return CardService.newActionResponseBuilder()
      .setNavigation(CardService.newNavigation().updateCard(_buildOnboardingStep1Card()))
      .build();
  }

  try {
    var userId   = Session.getEffectiveUser().getEmail();
    var baseUrl  = agentUrl.replace(/\/+$/, "");
    var endpoint = baseUrl + "/api/settings?user_id=" + encodeURIComponent(userId);

    var resp = UrlFetchApp.fetch(endpoint, { method: "get", muteHttpExceptions: true });
    var code = resp.getResponseCode();

    if (code === 200) {
      var data = {};
      try { data = JSON.parse(resp.getContentText()); } catch (je) {}
      var fetched = data.settings || (typeof data === "object" ? data : null);

      if (fetched && typeof fetched === "object" && Object.keys(fetched).length > 0) {
        if (!fetched.agent_url) fetched.agent_url = agentUrl;
        userProps.setProperty("ob_prefill",      JSON.stringify(fetched));
        userProps.setProperty("ob_status_msg",   "Settings loaded from server! Form is pre-filled below.");
        userProps.setProperty("ob_status_error", "false");
      } else {
        userProps.setProperty("ob_status_msg",   "No saved settings found on server. Configure manually below.");
        userProps.setProperty("ob_status_error", "false");
      }
    } else {
      userProps.setProperty("ob_status_msg",   "Server returned HTTP " + code + ". Check the URL and try again.");
      userProps.setProperty("ob_status_error", "true");
    }
  } catch (err) {
    userProps.setProperty("ob_status_msg",   "Cannot reach server: " + err.message.substring(0, 120));
    userProps.setProperty("ob_status_error", "true");
  }

  return CardService.newActionResponseBuilder()
    .setNavigation(CardService.newNavigation().updateCard(_buildOnboardingStep1Card()))
    .build();
}

/**
 * "Connect & Verify Server" handler.
 * Equivalent of Thunderbird's ob-connect-btn flow.
 * Reads agent_url (and all other form values) from e.formInput, pings /handshake,
 * and re-renders the form with a connection status message near the Agent URL section.
 * On success: also writes FLASK_SERVER_URL to Script Properties immediately.
 */
function handleVerifyAgentConnection(e) {
  var userProps = PropertiesService.getUserProperties();
  var f = (e && e.formInput) ? e.formInput : {};
  var agentUrl = (f.agent_url || "").trim();

  // Preserve all current form values as prefill so the user doesn't lose what they typed
  userProps.setProperty("ob_prefill", JSON.stringify({
    mode:                     f.mode                     || "manotr",
    agent_url:                agentUrl,
    user_name:                f.user_name                || "",
    user_position:            f.user_position            || "",
    imap_app_password:        f.imap_app_password        || "",
    user_tone:                f.user_tone                || "professional",
    system_prompt:            f.system_prompt            || "",
    llm_provider:             f.llm_provider             || "manotr",
    llm_api_key:              f.llm_api_key              || "",
    llm_model:                f.llm_model                || "",
    llm_base_url:             f.llm_base_url             || "",
    llm_ollama_api_key:       f.llm_ollama_api_key       || "",
    embedding_provider:       f.embedding_provider       || "manotr",
    embedding_api_key:        f.embedding_api_key        || "",
    embedding_model:          f.embedding_model          || "",
    embedding_base_url:       f.embedding_base_url       || "",
    embedding_ollama_api_key: f.embedding_ollama_api_key || "",
    vector_provider:          f.vector_provider          || "manotr",
    vector_url:               f.vector_url               || "",
    vector_api_key:           f.vector_api_key           || ""
  }));

  if (!agentUrl) {
    userProps.setProperty("ob_connect_msg", "Enter an Agent URL above before verifying.");
    userProps.setProperty("ob_connect_ok",  "false");
    return CardService.newActionResponseBuilder()
      .setNavigation(CardService.newNavigation().updateCard(_buildOnboardingStep1Card()))
      .build();
  }

  try {
    var baseUrl = agentUrl.replace(/\/+$/, "");
    var resp    = UrlFetchApp.fetch(baseUrl + "/handshake", {
      method: "get",
      muteHttpExceptions: true
    });
    var code = resp.getResponseCode();
    var body = {};
    try { body = JSON.parse(resp.getContentText()); } catch (je) {}

    if (code === 200 &&
        (body.handshake === true || body.status === "ok" || body.status === "healthy")) {
      userProps.setProperty("ob_connect_msg", "Server connected and verified! (" + baseUrl + ")");
      userProps.setProperty("ob_connect_ok",  "true");
      // Persist the verified URL right away
      PropertiesService.getScriptProperties().setProperty("FLASK_SERVER_URL", baseUrl);
    } else {
      userProps.setProperty("ob_connect_msg", "Server responded with HTTP " + code + ". Check URL or server status.");
      userProps.setProperty("ob_connect_ok",  "false");
    }
  } catch (err) {
    userProps.setProperty("ob_connect_msg", "Cannot reach server: " + err.message.substring(0, 120));
    userProps.setProperty("ob_connect_ok",  "false");
  }

  return CardService.newActionResponseBuilder()
    .setNavigation(CardService.newNavigation().updateCard(_buildOnboardingStep1Card()))
    .build();
}

// ============================================================================
// ONBOARDING — PROVIDER VALIDATION & MODEL FETCH HANDLERS
// ============================================================================

/**
 * Saves all current onboarding form values to ob_prefill so they survive card re-renders.
 */
function _saveOBFormState(f) {
  PropertiesService.getUserProperties().setProperty("ob_prefill", JSON.stringify({
    mode:                     f.mode                     || "manotr",
    agent_url:                f.agent_url                || "",
    user_name:                f.user_name                || "",
    user_position:            f.user_position            || "",
    imap_app_password:        f.imap_app_password        || "",
    user_tone:                f.user_tone                || "professional",
    system_prompt:            f.system_prompt            || "",
    llm_provider:             f.llm_provider             || "manotr",
    llm_api_key:              f.llm_api_key              || "",
    llm_model:                f.llm_model                || "",
    llm_base_url:             f.llm_base_url             || "",
    llm_ollama_api_key:       f.llm_ollama_api_key       || "",
    embedding_provider:       f.embedding_provider       || "manotr",
    embedding_api_key:        f.embedding_api_key        || "",
    embedding_model:          f.embedding_model          || "",
    embedding_base_url:       f.embedding_base_url       || "",
    embedding_ollama_api_key: f.embedding_ollama_api_key || "",
    vector_provider:          f.vector_provider          || "manotr",
    vector_url:               f.vector_url               || "",
    vector_api_key:           f.vector_api_key           || ""
  }));
}

/**
 * "Validate API & Fetch Models" for cloud LLM providers during Onboarding.
 * Industry-standard: GET /v1/models — 0 tokens consumed, validates key + returns model list.
 */
function handleOBFetchLLMModels(e) {
  var f = (e && e.formInput) ? e.formInput : {};
  _saveOBFormState(f);
  var userProps = PropertiesService.getUserProperties();
  var provider  = f.llm_provider || "openai";
  var apiKey    = (f.llm_api_key || "").trim();
  if (!apiKey) {
    userProps.setProperty("ob_llm_msg", "Enter your " + provider.toUpperCase() + " API key first.");
    userProps.setProperty("ob_llm_ok",  "false");
  } else {
    var agentUrl = (f.agent_url || "").trim()
                   || PropertiesService.getScriptProperties().getProperty("FLASK_SERVER_URL")
                   || "http://omb.manotr.com";
    var result = _validateViaEndpoint(agentUrl, "llm", provider, apiKey, "");
    userProps.setProperty("ob_llm_msg", result.message || "");
    userProps.setProperty("ob_llm_ok",  result.valid ? "true" : "false");
    if (result.valid && result.models && result.models.length > 0) {
      userProps.setProperty("ob_llm_models_" + provider, JSON.stringify(result.models));
    }
  }
  return CardService.newActionResponseBuilder()
    .setNavigation(CardService.newNavigation().updateCard(_buildOnboardingStep1Card()))
    .build();
}

/**
 * "Connect & Fetch Ollama Models" for LLM during Onboarding.
 * Supports all 3 Ollama deployment cases:
 *   1. Local   — http://localhost:11434  (no auth)
 *   2. Remote  — any public URL via PageKite / ngrok
 *   3. Secured — public URL + Bearer token
 */
function handleOBFetchLLMOllamaModels(e) {
  var f = (e && e.formInput) ? e.formInput : {};
  _saveOBFormState(f);
  var userProps = PropertiesService.getUserProperties();
  var ollamaUrl = (f.llm_base_url      || "http://localhost:11434").trim();
  var apiKey    = (f.llm_ollama_api_key || "").trim();
  var agentUrl  = (f.agent_url || "").trim()
                  || PropertiesService.getScriptProperties().getProperty("FLASK_SERVER_URL")
                  || "http://omb.manotr.com";
  var result = _validateViaEndpoint(agentUrl, "llm", "ollama", apiKey, ollamaUrl);
  userProps.setProperty("ob_llm_msg", result.message || "");
  userProps.setProperty("ob_llm_ok",  result.valid ? "true" : "false");
  if (result.valid && result.models && result.models.length > 0) {
    userProps.setProperty("ob_llm_models_ollama", JSON.stringify(result.models));
  }
  return CardService.newActionResponseBuilder()
    .setNavigation(CardService.newNavigation().updateCard(_buildOnboardingStep1Card()))
    .build();
}

/**
 * "Validate API & Fetch Models" for cloud Embedding providers during Onboarding.
 */
function handleOBFetchEmbeddingModels(e) {
  var f = (e && e.formInput) ? e.formInput : {};
  _saveOBFormState(f);
  var userProps = PropertiesService.getUserProperties();
  var provider  = f.embedding_provider || "openai";
  var apiKey    = (f.embedding_api_key || "").trim();
  if (!apiKey) {
    userProps.setProperty("ob_emb_msg", "Enter your " + provider.toUpperCase() + " API key first.");
    userProps.setProperty("ob_emb_ok",  "false");
  } else {
    var agentUrl = (f.agent_url || "").trim()
                   || PropertiesService.getScriptProperties().getProperty("FLASK_SERVER_URL")
                   || "http://omb.manotr.com";
    var result = _validateViaEndpoint(agentUrl, "embedding", provider, apiKey, "");
    userProps.setProperty("ob_emb_msg", result.message || "");
    userProps.setProperty("ob_emb_ok",  result.valid ? "true" : "false");
    if (result.valid && result.models && result.models.length > 0) {
      userProps.setProperty("ob_emb_models_" + provider, JSON.stringify(result.models));
    }
  }
  return CardService.newActionResponseBuilder()
    .setNavigation(CardService.newNavigation().updateCard(_buildOnboardingStep1Card()))
    .build();
}

/**
 * "Connect & Fetch Ollama Models" for Embedding during Onboarding.
 * Same 3-case Ollama support as handleOBFetchLLMOllamaModels.
 */
function handleOBFetchEmbeddingOllamaModels(e) {
  var f = (e && e.formInput) ? e.formInput : {};
  _saveOBFormState(f);
  var userProps = PropertiesService.getUserProperties();
  var ollamaUrl = (f.embedding_base_url      || "http://localhost:11434").trim();
  var apiKey    = (f.embedding_ollama_api_key || "").trim();
  var agentUrl  = (f.agent_url || "").trim()
                  || PropertiesService.getScriptProperties().getProperty("FLASK_SERVER_URL")
                  || "http://omb.manotr.com";
  var result = _validateViaEndpoint(agentUrl, "embedding", "ollama", apiKey, ollamaUrl);
  userProps.setProperty("ob_emb_msg", result.message || "");
  userProps.setProperty("ob_emb_ok",  result.valid ? "true" : "false");
  if (result.valid && result.models && result.models.length > 0) {
    userProps.setProperty("ob_emb_models_ollama", JSON.stringify(result.models));
  }
  return CardService.newActionResponseBuilder()
    .setNavigation(CardService.newNavigation().updateCard(_buildOnboardingStep1Card()))
    .build();
}

/**
 * Save step 1 data then show step 2.
 * Validates required fields (Name + Position) — shows inline error on the step 1 card
 * with form values preserved (equivalent to Thunderbird's ob-user-name-error display).
 */
function saveOnboardingStep1(e) {
  var f = e.formInput || {};
  var userProps = PropertiesService.getUserProperties();

  // Normalise mode — map legacy "inbuilt" → "manotr", "custom" → "external"
  var mode = f.mode || "manotr";
  if (mode === "inbuilt") mode = "manotr";
  if (mode === "custom")  mode = "external";

  // Auto-set agent URL for Manotr mode
  var agentUrl = (f.agent_url || "").trim();
  if (mode === "manotr" && !agentUrl) agentUrl = "http://omb.manotr.com";

  // Normalise provider names — map legacy "inbuilt" → "manotr"
  var mapProvider = function(v) { return (v === "inbuilt") ? "manotr" : (v || "manotr"); };

  // ── Validate required profile fields (Thunderbird parity) ─────────────
  var userName     = (f.user_name     || "").trim();
  var userPosition = (f.user_position || "").trim();
  if (!userName || !userPosition) {
    var errMsg = (!userName && !userPosition)
      ? "⚠️  Full Name and Job Title / Role are both required."
      : (!userName ? "⚠️  Full Name is required." : "⚠️  Job Title / Role is required.");

    // Preserve current form values so the user doesn't have to re-enter everything
    userProps.setProperty("ob_prefill", JSON.stringify({
      mode: mode, agent_url: agentUrl,
      user_name: userName, user_position: userPosition,
      imap_app_password: f.imap_app_password || "",
      user_tone: f.user_tone || "professional", system_prompt: f.system_prompt || "",
      llm_provider: f.llm_provider || "manotr", llm_api_key: f.llm_api_key || "",
      llm_model: f.llm_model || "", llm_base_url: f.llm_base_url || "",
      llm_ollama_api_key: f.llm_ollama_api_key || "",
      embedding_provider: f.embedding_provider || "manotr",
      embedding_api_key: f.embedding_api_key || "", embedding_model: f.embedding_model || "",
      embedding_base_url: f.embedding_base_url || "",
      embedding_ollama_api_key: f.embedding_ollama_api_key || "",
      vector_provider: f.vector_provider || "manotr",
      vector_url: f.vector_url || "", vector_api_key: f.vector_api_key || ""
    }));
    userProps.setProperty("ob_status_msg",   errMsg);
    userProps.setProperty("ob_status_error", "true");
    return CardService.newActionResponseBuilder()
      .setNavigation(CardService.newNavigation().updateCard(_buildOnboardingStep1Card()))
      .build();
  }

  var settings = {
    mode:                     mode,
    agent_url:                agentUrl,
    llm_provider:             mapProvider(f.llm_provider),
    llm_api_key:              f.llm_api_key              || "",
    llm_model:                f.llm_model                || "gpt-4o-mini",
    llm_base_url:             f.llm_base_url             || "",
    llm_ollama_api_key:       f.llm_ollama_api_key       || "",
    embedding_provider:       mapProvider(f.embedding_provider),
    embedding_api_key:        f.embedding_api_key        || "",
    embedding_model:          f.embedding_model          || "text-embedding-3-small",
    embedding_base_url:       f.embedding_base_url       || "",
    embedding_ollama_api_key: f.embedding_ollama_api_key || "",
    vector_provider:          mapProvider(f.vector_provider),
    vector_url:               f.vector_url               || "",
    vector_api_key:           f.vector_api_key           || "",
    user_name:                userName,
    user_position:            userPosition,
    imap_app_password:        f.imap_app_password        || "",
    run_imap_server:          (f.imap_app_password && f.imap_app_password.trim() !== "") ? true : false,
    imap_email:               Session.getEffectiveUser().getEmail(),
    user_tone:                f.user_tone                || "professional",
    system_prompt:            f.system_prompt            || ""
  };

  // Apply provider-specific model defaults if user left model empty
  if (!settings.llm_model || settings.llm_model.trim() === "") {
    if      (settings.llm_provider === "openai")    settings.llm_model = "gpt-4o-mini";
    else if (settings.llm_provider === "anthropic") settings.llm_model = "claude-3-5-sonnet-20241022";
    else if (settings.llm_provider === "groq")      settings.llm_model = "llama-3.3-70b-versatile";
    else if (settings.llm_provider === "ollama")    settings.llm_model = "llama3.3";
    else                                             settings.llm_model = "gpt-4o-mini";
  }
  if (!settings.embedding_model || settings.embedding_model.trim() === "") {
    if      (settings.embedding_provider === "openai") settings.embedding_model = "text-embedding-3-small";
    else if (settings.embedding_provider === "ollama") settings.embedding_model = "nomic-embed-text";
    else                                                settings.embedding_model = "text-embedding-3-small";
  }

  userProps.setProperty("user_settings",        JSON.stringify(settings));
  userProps.setProperty("onboarding_page1_done", "true");
  userProps.deleteProperty("ob_prefill"); // clear temp prefill on successful save

  // Save agent URL to Script Properties so all API calls use it as FLASK_SERVER_URL
  if (agentUrl) {
    PropertiesService.getScriptProperties().setProperty("FLASK_SERVER_URL", agentUrl);
  }

  return showOnboardingStep2();
}

/**
 * Step 2 of 2: Choose how much email history to index
 */
function showOnboardingStep2() {
  return CardService.newCardBuilder()
    .setHeader(
      CardService.newCardHeader()
        .setTitle("📧  Email Context Setup")
        .setSubtitle("Step 2 of 2 — Build your AI knowledge base")
    )
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newTextParagraph()
            .setText(
              "<b>How far back should OpenMailBot learn from your emails?</b>\n\n" +
              "The AI will index your past emails to understand your projects, communication style, and key contacts. " +
              "The more history you include, the more accurate the AI becomes.\n\n" +
              "<b>This step is optional.</b> You can skip it and start historical indexing later from Settings."
            )
        )
    )
    .addSection(
      CardService.newCardSection()
        .setHeader("📅  EMAIL HISTORY TO INDEX  (optional)")
        .addWidget(
          CardService.newSelectionInput()
            .setType(CardService.SelectionInputType.RADIO_BUTTON)
            .setFieldName("onboarding_months")
            .setTitle("How many months of email history?")
            .addItem("🗓️  10 days  (Minimal — very fast ~ 2-5 min)", "10d", false)
            .addItem("⚡  1 month  (Quick start ~ 5-10 min)", "1", false)
            .addItem("📅  2 months  (Good balance ~ 15-25 min)", "2", false)
            .addItem("📅  3 months  (Recommended ~ 20-40 min)", "3", true)
            .addItem("📁  6 months  (Rich context ~ 45-90 min)", "6", false)
            .addItem("🗂️  12 months  (Full year)", "12", false)
        )
        .addWidget(
          CardService.newTextParagraph()
            .setText(
              "ℹ️  Processing runs securely in the background — you can use Gmail normally while it runs.\n" +
              "✅  Features work immediately; AI improves as indexing completes."
            )
        )
    )
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newButtonSet()
            .addButton(
              CardService.newTextButton()
                .setText("← Back")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("showOnboardingStep1")
                )
            )
            .addButton(
              CardService.newTextButton()
                .setText("✅  Complete Setup & Start Indexing")
                .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
                .setBackgroundColor("#0F9D58")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("completeOnboarding")
                )
            )
            .addButton(
              CardService.newTextButton()
                .setText("⏭️  Skip — Start Monitor Only")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("skipOnboardingHistoricalIndexing")
                )
            )
        )
    )
    .build();
}

/**
 * Skip historical indexing during onboarding — mark complete, start monitor, go home
 */
function skipOnboardingHistoricalIndexing(e) {
  // Create/verify labels before completing onboarding
  Logger.log("🏷️  Creating/verifying OpenMailBot labels...");
  try {
    createOpenMailBotLabels();
    Logger.log("✅ Labels verified during onboarding skip");
  } catch (labelErr) {
    Logger.log("⚠️  Label creation failed (non-fatal): " + labelErr.message);
  }
  
  // Mark onboarding complete so monitor can run
  var userProps = PropertiesService.getUserProperties();
  userProps.setProperty("onboarding_complete", "true");
  PropertiesService.getScriptProperties().setProperty("background_monitor_enabled", "true");
  // Sync settings to backend
  try {
    syncSettingsToBackend(loadUserSettings());
  } catch (syncErr) {
    Logger.log("⚠️ Skip onboarding: settings sync failed — " + syncErr.message);
  }
  // Start the monitor trigger
  var monitorInstalled = false;
  var monitorErrorMsg = "";
  try {
    setupEmailMonitor();
    monitorInstalled = true;
    Logger.log("✅ Monitor trigger installed on onboarding skip");
  } catch (monErr) {
    monitorErrorMsg = monErr.message || String(monErr);
    Logger.log("❌ Monitor trigger failed on onboarding skip — " + monitorErrorMsg);
  }
  var skipCard = CardService.newCardBuilder()
    .setHeader(
      CardService.newCardHeader()
        .setTitle("✅  Setup Complete")
        .setSubtitle("Email monitor is active — historical indexing skipped")
    )
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newDecoratedText()
            .setTopLabel(monitorInstalled ? "● MONITOR ACTIVE" : "● MONITOR INACTIVE")
            .setText(
              "<b>" +
              (monitorInstalled ? "✅  Email monitor running every hour." : "⚠️  Monitor trigger install failed.") +
              "</b>"
            )
            .setBottomLabel(monitorInstalled ? "New emails will be processed and labelled automatically" : "Error: " + monitorErrorMsg)
            .setWrapText(true)
        )
        .addWidget(
          CardService.newTextParagraph()
            .setText(
              "You can start historical indexing anytime from:\n" +
              "⚙️  Settings → Index Email History\n\n" +
              "All features are available right now:\n" +
              "  • 📝  Summarize any email thread\n" +
              "  • 💬  Chat with your emails\n" +
              "  • 📎  Generate AI-powered draft replies"
            )
        )
    );

  // Show a retry button prominently when trigger install failed
  if (!monitorInstalled) {
    skipCard.addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newDecoratedText()
            .setTopLabel("⚠️  ACTION REQUIRED")
            .setText("<b>Monitor trigger not installed</b>")
            .setBottomLabel("Click install or restart add-on")
            .setWrapText(true)
        )
        .addWidget(
          CardService.newTextButton()
            .setText("🔧  Install Monitor Trigger Now")
            .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
            .setBackgroundColor("#EA4335")
            .setOnClickAction(
              CardService.newAction().setFunctionName("handleInstallMonitorTrigger")
            )
        )
    );
  }

  skipCard.addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newButtonSet()
            .addButton(
              CardService.newTextButton()
                .setText("🏠  Go to Home")
                .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
                .setBackgroundColor("#4285F4")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("buildAddOn")
                )
            )
            .addButton(
              CardService.newTextButton()
                .setText("📚  Index History Later")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("showSettingsCard")
                )
            )
        )
    );

  return skipCard.build();
}

/**
 * Final onboarding step: save months, start monitor, launch bulk job
 */
function completeOnboarding(e) {
  var formInputs = e.formInput || {};
  var months = formInputs.onboarding_months || "3";

  // Create/verify labels before completing onboarding
  Logger.log("🏷️  Creating/verifying OpenMailBot labels...");
  try {
    createOpenMailBotLabels();
    Logger.log("✅ Labels verified during onboarding completion");
  } catch (labelErr) {
    Logger.log("⚠️  Label creation failed (non-fatal): " + labelErr.message);
  }

  // Mark onboarding complete
  var userProps = PropertiesService.getUserProperties();
  userProps.setProperty("onboarding_complete", "true");
  Logger.log("✅ Onboarding marked complete");

  // Save months selection
  PropertiesService.getScriptProperties().setProperty("process_last_n_months", months);

  // Enable background monitoring by default
  PropertiesService.getScriptProperties().setProperty("background_monitor_enabled", "true");
  Logger.log("✅ Background monitoring enabled");

  // Sync settings to backend (best effort)
  try {
    var settings = loadUserSettings();
    syncSettingsToBackend(settings);
    Logger.log("✅ Settings synced to backend");
  } catch (syncErr) {
    Logger.log("⚠️ Onboarding: settings sync failed — " + syncErr.message);
  }

  // Install (or force-reinstall) the background monitor trigger immediately
  Logger.log("🔧 Installing background email monitor trigger...");
  var monitorInstalled = false;
  var monitorErrorMsg = "";
  try {
    setupEmailMonitor();  // deletes stale triggers + creates fresh 1-hour trigger
    monitorInstalled = true;
    Logger.log("✅ Background monitor trigger installed — will fire every hour");
  } catch (monErr) {
    monitorErrorMsg = monErr.message || String(monErr);
    Logger.log("❌ Onboarding: monitor trigger install FAILED — " + monitorErrorMsg);
  }

  // Install the auto-sync trigger (sends latest email every 1 minute)
  Logger.log("🔧 Installing auto-sync trigger...");
  try {
    ensureAutoSyncTriggerRunning();
    Logger.log("✅ Auto-sync trigger installed — will send latest email every 1 minute");
  } catch (autoSyncErr) {
    Logger.log("⚠️ Auto-sync trigger install warning: " + autoSyncErr.message);
  }

  // Launch historical email indexing in the background
  try {
    _launchBulkJobAsync(months);
  } catch (bulkErr) {
    Logger.log("Onboarding: bulk job launch failed — " + bulkErr.message);
  }

  var completeCard = CardService.newCardBuilder()
    .setHeader(
      CardService.newCardHeader()
        .setTitle("🎉  Setup Complete!")
        .setSubtitle("OpenMailBot is now active")
    )
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newDecoratedText()
            .setTopLabel(monitorInstalled ? "● ALL SET" : "● MONITOR INACTIVE")
            .setText("<b>" + (monitorInstalled ? "OpenMailBot is ready to use!" : "Setup done, but monitor trigger failed.") + "</b>")
            .setBottomLabel(
              monitorInstalled
                ? "Background monitor active  ·  Indexing last " + (months === "10d" ? "10 days" : months + " months") + " of email history"
                : "Error: " + monitorErrorMsg
            )
            .setWrapText(true)
        )
        .addWidget(
          CardService.newTextParagraph()
            .setText(
              (monitorInstalled
                ? "✅  Email monitor is ACTIVE — checking for new emails every hour.\n"
                : "⚠️  Monitor trigger install failed. Tap the button below to retry.\n") +
              "\n⏱️  Email indexing starts in ~1 hour and runs in the background.\n\n" +
              "You can start using all features right now:\n" +
              "  • 📝  Summarize any email thread\n" +
              "  • 💬  Chat with emails and attachments\n" +
              "  • 📎  Generate AI-powered draft replies\n\n" +
              "⚙️  Change any setting anytime via Settings."
            )
        )
    );

  // Retry button when trigger failed
  if (!monitorInstalled) {
    completeCard.addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newTextButton()
            .setText("🔧  Install Monitor Trigger Now")
            .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
            .setBackgroundColor("#EA4335")
            .setOnClickAction(
              CardService.newAction().setFunctionName("handleInstallMonitorTrigger")
            )
        )
    );
  }

  completeCard.addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newButtonSet()
            .addButton(
              CardService.newTextButton()
                .setText("🏠  Go to Home")
                .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
                .setBackgroundColor("#4285F4")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("buildAddOn")
                )
            )
            .addButton(
              CardService.newTextButton()
                .setText("📊  Indexing Progress")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("showBulkJobStatusCard")
                )
            )
        )
    );

  return completeCard.build();
}

/**
 * Generate Draft — simple draft with no attachment processing.
 * Parity with Thunderbird's "✍️ Generate Draft" button (handleSimpleDraft).
 * Calls POST /api/draft with { user_id, thread_id, user_preferences }.
 */
function generateDraft(e) {
  try {
    var messageId = e.gmail.messageId;
    var thread    = GmailApp.getMessageById(messageId).getThread();
    var messages  = thread.getMessages();
    var threadId  = getCanonicalThreadId(thread);
    var userId    = Session.getEffectiveUser().getEmail();

    // Step 1: Log email messages to server so the agent has context
    try {
      logEmailMessages(threadId, messages);
      Logger.log("generateDraft: emails logged for thread " + threadId);
    } catch (logErr) {
      Logger.log("generateDraft: email logging failed — " + logErr.message);
    }

    // Step 2: Call /api/draft (simple draft, no attachment indexing)
    var flaskUrl = PropertiesService.getScriptProperties().getProperty("FLASK_SERVER_URL");
    if (!flaskUrl) {
      throw new Error("Flask server URL not configured. Please set FLASK_SERVER_URL in Script Properties.");
    }

    var apiEndpoint = flaskUrl.replace(/\/$/, '') + '/api/draft';
    var payload = {
      user_id         : userId,
      thread_id       : threadId,
      user_preferences: getUserPreferences()
    };

    Logger.log("generateDraft: calling " + apiEndpoint);
    var response = UrlFetchApp.fetch(apiEndpoint, {
      method          : "post",
      contentType     : "application/json",
      payload         : JSON.stringify(payload),
      muteHttpExceptions: true
    });

    var responseCode = response.getResponseCode();
    var responseText = response.getContentText();
    Logger.log("generateDraft: response " + responseCode + " — " + responseText.substring(0, 300));

    if (responseCode !== 200) {
      throw new Error("Draft API error (" + responseCode + "): " + responseText.substring(0, 200));
    }

    var data;
    try { data = JSON.parse(responseText); } catch (pe) {
      throw new Error("Invalid JSON from draft API: " + responseText.substring(0, 200));
    }

    // If server returned a job_id, poll until done
    if (data.job_id) {
      data = pollJobStatus(data.job_id, 120000);
    }

    var draftContent = data.draft_content || data.response || "No draft content received";

    // Create draft reply in Gmail
    var lastMessage = messages[messages.length - 1];
    var subject     = lastMessage.getSubject();
    if (!subject.match(/^Re:/i)) { subject = "Re: " + subject; }

    try {
      thread.createDraftReply(draftContent);
    } catch (draftErr) {
      GmailApp.createDraft(lastMessage.getFrom(), subject, draftContent);
    }

    // Build result card
    var preview = draftContent.substring(0, 800) + (draftContent.length > 800 ? "\n\n<i>… (draft continues)</i>" : "");

    return CardService.newCardBuilder()
      .setHeader(
        CardService.newCardHeader()
          .setTitle("✍️  Draft Ready")
          .setSubtitle("Generated from email thread (no attachments)")
      )
      .addSection(
        CardService.newCardSection()
          .addWidget(
            CardService.newDecoratedText()
              .setText("<b>✅ Draft created successfully!</b>")
              .setBottomLabel("From email thread only")
              .setWrapText(true)
          )
      )
      .addSection(
        CardService.newCardSection()
          .setHeader("📧 Draft Preview")
          .setCollapsible(true)
          .setNumUncollapsibleWidgets(0)
          .addWidget(
            CardService.newTextParagraph().setText(preview)
          )
      )
      .addSection(
        CardService.newCardSection()
          .addWidget(
            CardService.newButtonSet()
              .addButton(
                CardService.newTextButton()
                  .setText("📬 View Drafts")
                  .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
                  .setBackgroundColor("#4285F4")
                  .setOpenLink(CardService.newOpenLink()
                    .setUrl("https://mail.google.com/mail/u/0/#drafts")
                    .setOpenAs(CardService.OpenAs.FULL_SIZE))
              )
              .addButton(
                CardService.newTextButton()
                  .setText("🏠 Home")
                  .setOnClickAction(CardService.newAction().setFunctionName("buildAddOn"))
              )
          )
      )
      .build();

  } catch (error) {
    Logger.log("generateDraft error: " + error.message);
    return showError("Error generating draft:\n\n" + error.message);
  }
}

/**
 * NEW: Draft with Attachments - Main handler
 * Processes attachments and generates AI draft with full context
 */
function draftWithAttachments(e) {
  try {
    var messageId = e.gmail.messageId;
    var thread = GmailApp.getMessageById(messageId).getThread();
    var messages = thread.getMessages();
    var threadId = getCanonicalThreadId(thread);
    
    // Get user ID (email address)
    var userId = Session.getEffectiveUser().getEmail();
    
    // First, send all email messages to server using logEmailMessages
    var attachmentCount = 0;
    try {
      logEmailMessages(threadId, messages);
      Logger.log("Email messages logged successfully for thread: " + threadId);
    } catch (logErr) {
      Logger.log("Email logging failed: " + logErr.message);
      // Continue anyway - we'll try with basic email data
    }
    
    // Second, upload all attachments to server (best-effort)
    try {
      messages.forEach(function(m) {
        var atts = m.getAttachments ? m.getAttachments() : [];
        if (atts && atts.length > 0) {
          attachmentCount += atts.length;
          storeMessageAttachments(threadId, m);
        }
      });
      Logger.log("Uploaded " + attachmentCount + " attachments");
    } catch (attErr) {
      Logger.log("Attachment upload failed: " + attErr.message);
      // Continue anyway - attachments are optional
    }
    
    // Call pipeline API with required data
    Logger.log("Calling pipeline API...");
    // Upload attachments and wait for confirmation
    var attachmentUploadSuccess = true;
    try {
      messages.forEach(function(m) {
        var atts = m.getAttachments ? m.getAttachments() : [];
        if (atts && atts.length > 0) {
          attachmentCount += atts.length;
          var result = storeMessageAttachments(threadId, m); // already sync
          Logger.log("Attachment upload result: " + result);
        }
      });
    } catch (attErr) {
      Logger.log("Attachment upload failed: " + attErr.message);
    }

    // Add a small delay to ensure server has written files to disk
    Utilities.sleep(2000); // 2 second buffer
    var draftResult;
    try {
      draftResult = callPipelineAPI({
        user_id: userId,
        thread_id: threadId,
        message_id: messageId,
        user_preferences: getUserPreferences()
      });
    } catch (apiError) {
      // Provide detailed error message
      var errorMsg = "Pipeline API Error:\n\n" + apiError.message + 
        "\n\n📋 Troubleshooting:\n" +
        "1. Check if the server is running\n" +
        "2. Verify FLASK_SERVER_URL in Script Properties\n" +
        "3. Check server logs\n" +
        "4. Test health endpoint: [SERVER_URL]/health";
      throw new Error(errorMsg);
    }
    
    // Create draft in Gmail
    var lastMessage = messages[messages.length - 1];
    var recipient = lastMessage.getFrom();
    var subject = lastMessage.getSubject();
    if (!subject.match(/^Re:/i)) {
      subject = "Re: " + subject;
    }
    
    var draftContent = draftResult.draft_content || draftResult.response || "No draft content received";
    var processingInfo = draftResult.processing_info || {};
    
    try {
      thread.createDraftReply(draftContent);
      var successMsg = "✅ Draft created successfully with attachment context!";
    } catch (draftError) {
      GmailApp.createDraft(recipient, subject, draftContent);
      var successMsg = "✅ Draft created (may not be threaded with original).";
    }
    
    // Build result card
    var draftPreview = draftContent.substring(0, 800);
    if (draftContent.length > 800) {
      draftPreview += "\n\n<i>... (draft continues)</i>";
    }
    
    // Processing info summary
    var processingMsg = "";
    if (processingInfo.attachments_found > 0) {
      processingMsg = "📊 Processing Summary:\n" +
        "• Attachments found: " + processingInfo.attachments_found + "\n" +
        "• Newly processed: " + processingInfo.attachments_processed + "\n" +
        "• Already cached: " + processingInfo.attachments_skipped;
    } else {
      processingMsg = "ℹ️ No attachments found in this thread.";
    }
    
    var card = CardService.newCardBuilder()
      .setHeader(
        CardService.newCardHeader()
          .setTitle("Draft Ready")
          .setSubtitle("Created with attachment context")
      )
      .addSection(
        CardService.newCardSection()
          .addWidget(
            CardService.newDecoratedText()
              .setText("<b>" + successMsg + "</b>")
              .setWrapText(true)
          )
      )
      .addSection(
        CardService.newCardSection()
          .setHeader("📊 Processing Info")
          .addWidget(
            CardService.newTextParagraph()
              .setText(processingMsg)
          )
      )
      .addSection(
        CardService.newCardSection()
          .setHeader("📧 Draft Preview")
          .setCollapsible(true)
          .setNumUncollapsibleWidgets(0)
          .addWidget(
            CardService.newTextParagraph()
              .setText(draftPreview)
          )
      )
      .addSection(
        CardService.newCardSection()
          .addWidget(
            CardService.newButtonSet()
              .addButton(
                CardService.newTextButton()
                  .setText("📬 View Drafts")
                  .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
                  .setBackgroundColor("#4285F4")
                  .setOpenLink(CardService.newOpenLink()
                    .setUrl("https://mail.google.com/mail/u/0/#drafts")
                    .setOpenAs(CardService.OpenAs.FULL_SIZE))
              )
              .addButton(
                CardService.newTextButton()
                  .setText("🏠 Home")
                  .setOnClickAction(
                    CardService.newAction().setFunctionName("buildAddOn")
                  )
              )
          )
      );
    
    return card.build();
    
  } catch (error) {
    Logger.log("draftWithAttachments error: " + error.message);
    return showError("Error creating draft with attachments:\n\n" + error.message);
  }
}

/**
 * Poll job status endpoint until done or error, then return result.
 * @param {string} jobId - The job ID returned by the pipeline endpoint
 * @param {number} maxWaitMs - Maximum time to wait in milliseconds (default 120000)
 * @returns {Object} The result from the completed job
 */
function pollJobStatus(jobId, maxWaitMs) {
  maxWaitMs = maxWaitMs || 120000;
  var flaskUrl = PropertiesService.getScriptProperties().getProperty("FLASK_SERVER_URL");
  var baseUrl = flaskUrl.replace(/\/$/, '').replace(/\/api$/, '');
  var statusUrl = baseUrl + '/api/job-status/' + jobId;
  var waited = 0;
  var interval = 3000;

  while (waited < maxWaitMs) {
    var resp = UrlFetchApp.fetch(statusUrl, { method: "get", muteHttpExceptions: true });
    if (resp.getResponseCode() === 200) {
      var data = JSON.parse(resp.getContentText());
      if (data.status === "done") return data.result;
      if (data.status === "error") throw new Error("Server error: " + data.error);
    }
    Utilities.sleep(interval);
    waited += interval;
  }
  throw new Error("Timeout waiting for job " + jobId + " after " + (maxWaitMs / 1000) + "s");
}

/**
 * NEW: Call Pipeline API for draft generation with attachments
 * No longer sends email_data - server will fetch from stored messages
 */
function callPipelineAPI(requestData) {
  var flaskUrl = PropertiesService.getScriptProperties()
    .getProperty("FLASK_SERVER_URL");
  
  if (!flaskUrl) {
    throw new Error("Flask server URL not configured. Please set FLASK_SERVER_URL in Script Properties.");
  }
  
  var apiEndpoint = flaskUrl.replace(/\/$/, '') + '/api/draft-with-attachments';
  
  var options = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(requestData),
    muteHttpExceptions: true
  };
  
  try {
    Logger.log("Calling pipeline API: " + apiEndpoint);
    var response = UrlFetchApp.fetch(apiEndpoint, options);
    var responseCode = response.getResponseCode();
    var responseText = response.getContentText();
    
    Logger.log("Response code: " + responseCode);
    Logger.log("Response text: " + responseText.substring(0, 500));
    
    // Check if response is HTML (error page)
    if (responseText.indexOf("<html") !== -1 || responseText.indexOf("<!DOCTYPE") !== -1) {
      throw new Error("Server returned HTML instead of JSON. Check if the server is running at: " + apiEndpoint);
    }
    
    // Check response code
    if (responseCode !== 200) {
      throw new Error("Server error (" + responseCode + "): " + responseText.substring(0, 200));
    }
    
    // Try to parse JSON
    var data;
    try {
      data = JSON.parse(responseText);
    } catch (parseError) {
      throw new Error("Invalid JSON response from server. Got: " + responseText.substring(0, 200));
    }
    
    if (data.error) {
      throw new Error("Pipeline API error: " + data.error);
    }

    // If server returned a job_id, poll until done
    if (data.job_id) {
      return pollJobStatus(data.job_id, 120000);
    }
    
    return data;
    
  } catch (error) {
    Logger.log("Pipeline API error: " + error.message);
    if (error.message.indexOf("Timeout") !== -1) {
      throw new Error("Request timeout - the server took too long to respond.");
    }
    if (error.message.indexOf("DNS error") !== -1) {
      throw new Error("Cannot reach server. Check the URL: " + apiEndpoint);
    }
    throw error;
  }
}
/**
 * NEW: Get user preferences for draft generation
 */
function getUserPreferences() {
  var userProperties = PropertiesService.getUserProperties();
  
  return {
    name: userProperties.getProperty("user_name") || "User",
    position: userProperties.getProperty("user_position") || "Professional",
    tone: userProperties.getProperty("user_tone") || "professional and concise",
    custom_instructions: userProperties.getProperty("custom_instructions") || ""
  };
}

/**
 * NEW: Set user preferences (helper function for users to configure)
 */
function setUserPreferences(name, position, tone, customInstructions) {
  var userProperties = PropertiesService.getUserProperties();
  
  userProperties.setProperty("user_name", name);
  userProperties.setProperty("user_position", position);
  userProperties.setProperty("user_tone", tone);
  userProperties.setProperty("custom_instructions", customInstructions);
  
  Logger.log("User preferences saved successfully");
}

/**
 * Main handler: read Gmail thread → send to AI → show summary with draft button
 */
function summarizeThread(e) {
  try {
    Logger.log("═════════════════════════════════════════════════════════════");
    Logger.log("🚀 STARTING SUMMARIZETHREAD FUNCTION");
    Logger.log("═════════════════════════════════════════════════════════════");
    
    // Step 0: Validate inputs
    Logger.log("📝 Step 0: Validating inputs...");
    if (!e || !e.gmail || !e.gmail.messageId) {
      throw new Error("Invalid event object - missing e.gmail.messageId");
    }
    Logger.log("   ✓ Event object valid");
    
    var messageId = e.gmail.messageId;
    Logger.log("   Message ID: " + messageId);
    
    Logger.log("   Getting message from Gmail...");
    var msg = GmailApp.getMessageById(messageId);
    Logger.log("   ✓ Message retrieved");
    
    var thread = msg.getThread();
    Logger.log("   ✓ Thread retrieved");
    
    var messages = thread.getMessages();
    Logger.log("   ✓ Messages retrieved, count: " + messages.length);
    
    var threadId = getCanonicalThreadId(thread);
    Logger.log("   ✓ Thread ID obtained: " + threadId);
    
    var userId = Session.getEffectiveUser().getEmail();
    Logger.log("   ✓ User ID obtained: " + userId);
    
    Logger.log("✅ Step 0 complete - all inputs validated\n");
    
    // Show loading state
    var loadingCard = CardService.newCardBuilder()
      .setHeader(
        CardService.newCardHeader()
          .setTitle("📋 Analyzing Thread")
          .setSubtitle("AI is structuring your email conversation…")
      )
      .addSection(
        CardService.newCardSection()
          .addWidget(
            CardService.newDecoratedText()
              .setText("<b>⏳ Processing your email thread…</b>")
              .setBottomLabel("Processing… (3 steps)")
              .setWrapText(true)
          )
      )
      .build();
    
    // Step 1: Log email messages to server storage
    Logger.log("📧 Step 1: Logging email messages to backend...");
    try {
      Logger.log("   Calling logEmailMessages(" + threadId + ", " + messages.length + " messages)");
      logEmailMessages(threadId, messages);
      Logger.log("✅ Email messages logged successfully to backend\n");
    } catch (logErr) {
      Logger.log("⚠️ Email logging failed: " + logErr.message);
      Logger.log("   Stack: " + logErr.stack);
    }
    
    // Step 2: Store attachments found in messages (best-effort)
    var attachmentCount = 0;
    Logger.log("📎 Step 2: Processing attachments...");
    try {
      Logger.log("   Scanning " + messages.length + " messages for attachments...");
      messages.forEach(function(m, idx) {
        var atts = m.getAttachments ? m.getAttachments() : [];
        Logger.log("   Message " + (idx + 1) + ": " + atts.length + " attachments");
        if (atts && atts.length > 0) {
          try {
            Logger.log("      Calling storeMessageAttachments for message " + m.getId());
            storeMessageAttachments(threadId, m);
            attachmentCount += atts.length;
            Logger.log("      ✓ Stored " + atts.length + " attachments");
          } catch (attErr) {
            Logger.log("      ⚠️ storeMessageAttachments failed: " + attErr.message);
          }
        }
      });
      Logger.log("✅ Attachments processed: " + attachmentCount + " total\n");
    } catch (e) {
      Logger.log("⚠️ Attachment scan failed: " + e.message);
      Logger.log("   Stack: " + e.stack);
    }
    
    // Add a small delay to ensure server has written files
    Logger.log("⏱️  Waiting 1.5 seconds for backend to write files...");
    Utilities.sleep(1500);
    Logger.log("✓ Wait complete\n");
    
    // Step 3: Call the new /api/summarize-thread endpoint
    Logger.log("🤖 Step 3: Calling summarization API...");
    var flaskUrl = PropertiesService.getScriptProperties()
      .getProperty("FLASK_SERVER_URL");
    
    Logger.log("   Flask URL from properties: " + flaskUrl);
    if (!flaskUrl) {
      throw new Error("Flask server URL not configured. Please set FLASK_SERVER_URL in Script Properties.");
    }
    
    var summaryApiUrl = flaskUrl.replace(/\/$/, '') + '/api/summarize-thread';
    Logger.log("   Final API URL: " + summaryApiUrl);
    
    var userName = getUserPreferences().name || "User";
    
    var requestPayload = {
      user_id: userId,
      thread_id: threadId,
      user_name: userName
    };
    
    Logger.log("   Payload to send:");
    Logger.log("      user_id: " + userId);
    Logger.log("      thread_id: " + threadId);
    Logger.log("      user_name: " + userName);
    
    Logger.log("   Creating fetch options...");
    var options = {
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify(requestPayload),
      muteHttpExceptions: true
    };
    Logger.log("   ✓ Options created");
    
    Logger.log("   📤 Sending HTTP POST request to: " + summaryApiUrl);
    var response = UrlFetchApp.fetch(summaryApiUrl, options);
    var responseCode = response.getResponseCode();
    var responseText = response.getContentText();
    
    Logger.log("📨 API Response received:");
    Logger.log("   Response Code: " + responseCode);
    Logger.log("   Response Text (first 500 chars): " + responseText.substring(0, 500));
    
    // Check if response is HTML (error page)
    if (responseText.indexOf("<html") !== -1 || responseText.indexOf("<!DOCTYPE") !== -1) {
      Logger.log("❌ ERROR: Server returned HTML (not JSON)");
      Logger.log("   Full response: " + responseText.substring(0, 1000));
      throw new Error("Server returned HTML. Check if server is running at: " + summaryApiUrl);
    }
    
    if (responseCode !== 202 && responseCode !== 200) {
      Logger.log("❌ ERROR: Bad response code " + responseCode);
      throw new Error("Server error (" + responseCode + "): " + responseText.substring(0, 300));
    }
    
    Logger.log("   ✓ Response code valid (200/202)");
    Logger.log("   Attempting to parse JSON...");
    
    // Parse JSON response
    var data;
    try {
      data = JSON.parse(responseText);
      Logger.log("   ✓ JSON parsed successfully");
      Logger.log("   Data keys: " + Object.keys(data).join(", "));
    } catch (parseError) {
      Logger.log("❌ ERROR: Failed to parse JSON");
      Logger.log("   Error: " + parseError.message);
      Logger.log("   Response was: " + responseText.substring(0, 300));
      throw new Error("Invalid JSON response. Got: " + responseText.substring(0, 200));
    }
    
    if (data.error) {
      Logger.log("❌ ERROR: API returned error in JSON");
      Logger.log("   Error from API: " + data.error);
      throw new Error("API error: " + data.error);
    }
    
    var jobId = data.job_id;
    Logger.log("   Job ID from response: " + jobId);
    if (!jobId) {
      Logger.log("❌ ERROR: No job_id in response");
      throw new Error("No job_id in response: " + responseText);
    }
    
    Logger.log("✅ Step 3 complete - Job submitted successfully");
    Logger.log("   Job ID: " + jobId + "\n");
    
    Logger.log("🔄 Step 4: Polling for job results...");
    Logger.log("   Polling with 180 second timeout");
    
    // Step 4: Poll job status until complete
    var summaryResult = pollJobStatus(jobId, 180000); // 3 minute timeout
    
    Logger.log("   Poll complete");
    if (!summaryResult) {
      Logger.log("❌ ERROR: No result returned from polling");
      throw new Error("No result returned from job: " + jobId);
    }
    
    Logger.log("   Result keys: " + Object.keys(summaryResult).join(", "));
    Logger.log("   Result.success: " + summaryResult.success);
    
    // pollJobStatus() already returns data.result, so we check summaryResult.success directly
    if (!summaryResult.success) {
      Logger.log("❌ ERROR: Summarization failed");
      Logger.log("   Error from result: " + (summaryResult.error || "Unknown error"));
      throw new Error("Summarization failed: " + (summaryResult.error || "Unknown error"));
    }
    
    var summary = summaryResult.summary;
    var metadata = summaryResult.metadata || {};
    
    Logger.log("✅ Step 4 complete - Summary received");
    Logger.log("   Messages processed: " + metadata.messages_processed);
    Logger.log("   API time: " + metadata.api_call_time + "s");
    Logger.log("   Summary length: " + (summary ? summary.length : 0) + " chars\n");
    
    Logger.log("✅ Summary generated successfully!");
    Logger.log("   Messages processed: " + metadata.messages_processed);
    Logger.log("   API time: " + metadata.api_call_time + "s");
    
    // Step 5: Format and display summary
    var formattedSummary = formatMarkdownToHtml(summary);
    
    // Build card with formatted summary
    var summarySection = CardService.newCardSection()
      .setHeader("📊 AI-Generated Summary");
    
    // Split summary into sections for better display
    var sections = formattedSummary.split(/━━━━━━━━━━━━━━/);
    
    sections.forEach(function(section, idx) {
      if (section && section.trim().length > 0) {
        var sectionText = section.trim();
        
        // Clean up excessive line breaks
        sectionText = sectionText.replace(/(<br>){4,}/g, '<br><br>');
        
        summarySection.addWidget(
          CardService.newTextParagraph()
            .setText(sectionText)
        );
        
        // Add subtle divider between sections (except last)
        if (idx < sections.length - 1) {
          summarySection.addWidget(
            CardService.newDivider()
          );
        }
      }
    });
    
    // Build final card
    var card = CardService.newCardBuilder()
      .setHeader(
        CardService.newCardHeader()
          .setTitle("✅ Thread Summary Ready")
          .setSubtitle("AI Analysis · " + metadata.messages_processed + " messages · " + metadata.api_call_time.toFixed(1) + "s")
      )
      .addSection(summarySection);
    
    // Add metadata section
    card.addSection(
      CardService.newCardSection()
        .setHeader("📈 Processing Details")
        .addWidget(
          CardService.newDecoratedText()
            .setText("")
            .setBottomLabel(
              "Messages analyzed: " + metadata.messages_processed + "\n" +
              "Processing time: " + metadata.api_call_time.toFixed(2) + "s\n" +
              "Attachments stored: " + attachmentCount
            )
            .setWrapText(true)
        )
    );
    
    // Add action buttons
    card.addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newButtonSet()
            .addButton(
              CardService.newTextButton()
                .setText("✍️ Draft Response")
                .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
                .setBackgroundColor("#0F9D58")
                .setOnClickAction(
                  CardService.newAction()
                    .setFunctionName("createDraftResponse")
                    .setParameters({summary: summary, threadId: threadId})
                )
            )
            .addButton(
              CardService.newTextButton()
                .setText("💬 Chat")
                .setTextButtonStyle(CardService.TextButtonStyle.OUTLINED)
                .setBackgroundColor("#7C4DFF")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("showChatInterface")
                )
            )
            .addButton(
              CardService.newTextButton()
                .setText("🏠 Home")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("buildAddOn")
                )
            )
        )
    );
    
    return card.build();
    
  } catch (error) {
    Logger.log("═════════════════════════════════════════════════════════════");
    Logger.log("❌ FATAL ERROR IN SUMMARIZETHREAD");
    Logger.log("═════════════════════════════════════════════════════════════");
    Logger.log("Error Message: " + error.message);
    Logger.log("Error Stack: " + error.stack);
    Logger.log("Error Type: " + error.name);
    Logger.log("═════════════════════════════════════════════════════════════");
    return showError("Error generating summary:\n\n" + error.message);
  }
}

/**
 * Enhanced markdown to HTML formatter for structured summaries
 */
function formatMarkdownToHtml(text) {
  if (!text) return "";
  
  // Preserve original line breaks first
  text = text.replace(/\r\n/g, '\n');
  
  // Convert numbered list headers (1️⃣, 2️⃣, etc.) to bold headers
  text = text.replace(/(\d️⃣)\s+(.+?)$/gm, '<br><b>$1 $2</b><br>');
  
  // Convert markdown headers #### ### ## # to bold
  text = text.replace(/^#{1,4}\s+(.+?)$/gm, '<b>$1</b>');
  
  // Bold text between ** (non-greedy)
  text = text.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
  
  // Italic text between _ (non-greedy)
  text = text.replace(/_(.+?)_/g, '<i>$1</i>');
  
  // Convert markdown horizontal rules
  text = text.replace(/^---+$/gm, '━━━━━━━━━━━━━━━━━━');
  
  // Convert bullet points (-, *, •)
  text = text.replace(/^\s*[-*•]\s+(.+?)$/gm, '  • $1');
  
  // Convert numbered lists
  text = text.replace(/^\s*(\d+)\.\s+(.+?)$/gm, '$1. $2');
  
  // Convert line breaks to HTML
  text = text.replace(/\n/g, '<br>');
  
  // Clean up multiple consecutive <br> (more than 3)
  text = text.replace(/(<br>){4,}/g, '<br><br>');
  
  return text;
}

/**
 * Splits text into chunks of specified size
 */
function splitIntoChunks(text, maxLength) {
  if (text.length <= maxLength) {
    return [text];
  }
  
  var chunks = [];
  var lines = text.split('\n');
  var currentChunk = '';
  
  for (var i = 0; i < lines.length; i++) {
    var line = lines[i];
    if ((currentChunk + line + '\n').length > maxLength && currentChunk.length > 0) {
      chunks.push(currentChunk);
      currentChunk = line + '\n';
    } else {
      currentChunk += line + '\n';
    }
  }
  
  if (currentChunk.length > 0) {
    chunks.push(currentChunk);
  }
  
  return chunks;
}

/**
 * Helper: Display summary in a nicely formatted card
 * Extracts structured sections from summary text
 */
function buildSummaryCard(title, subtitle, summaryText, attachmentCount, metadata) {
  var card = CardService.newCardBuilder()
    .setHeader(
      CardService.newCardHeader()
        .setTitle(title)
        .setSubtitle(subtitle)
    );
  
  // Parse summary into sections
  var sections = summaryText.split(/[\n]{2,}/);
  var contentAdded = false;
  
  var summarySection = CardService.newCardSection()
    .setHeader("📊 AI Summary");
  
  sections.forEach(function(section, idx) {
    if (section && section.trim().length > 0) {
      var formattedSection = formatMarkdownToHtml(section.trim());
      
      // Limit section length for display
      if (formattedSection.length > 5000) {
        formattedSection = formattedSection.substring(0, 5000) + "<br><br><i>... (summary continues)</i>";
      }
      
      summarySection.addWidget(
        CardService.newTextParagraph()
          .setText(formattedSection)
      );
      
      // Add divider between major sections
      if (idx < sections.length - 1 && section.indexOf("---") === -1) {
        summarySection.addWidget(CardService.newDivider());
      }
      
      contentAdded = true;
    }
  });
  
  if (contentAdded) {
    card.addSection(summarySection);
  }
  
  // Add metadata
  card.addSection(
    CardService.newCardSection()
      .setHeader("📈 Analysis Summary")
      .addWidget(
        CardService.newDecoratedText()
          .setText("")
          .setBottomLabel(
            "Messages: " + metadata.messages_processed + " | " +
            "Processing time: " + metadata.api_call_time.toFixed(1) + "s" + (attachmentCount > 0 ? " | Attachments: " + attachmentCount : "")
          )
          .setWrapText(true)
      )
  );
  
  return card;
}

/**
 * Creates a draft email based on the summary
 */
function createDraftResponse(e) {
  try {
    var summary = e.parameters.summary;
    var threadId = e.parameters.threadId;
    
    // Show loading
    var loadingCard = CardService.newCardBuilder()
      .setHeader(
        CardService.newCardHeader()
          .setTitle("Drafting Response")
          .setSubtitle("Composing your AI-powered reply…")
      )
      .addSection(
        CardService.newCardSection()
          .addWidget(
            CardService.newDecoratedText()
              .setText("<b>✍️ Generating your draft…</b>")
              .setBottomLabel("Generating professional reply…")
              .setWrapText(true)
          )
      )
      .build();
    
    // NEW: Log draft prompt (we will log final prompt below after building it)
    // Generate draft email content using AI
    var draftPrompt = "### Draft Response Email (Based on Current State)\n\n" +
      "I am Puja from AcmeAI\n" +
      "Draft response from me\n\n" +
      "Write a professional, neutral email that:\n" +
      "- Acknowledges the current status\n" +
      "- Restates pending actions\n" +
      "- Requests the next expected step\n" +
      "- Does NOT introduce new information\n\n" +
      "Email format only. No explanations.\n\n" +
      "Summary:\n" + summary;
    
    // NEW: Log draft request to server (best-effort)
    try {
      logEmailData(threadId, draftPrompt, "draft");
    } catch (logErr) {
      Logger.log("logEmailData (draft) failed: " + logErr.message);
    }
    
    // NEW: Also store attachments from thread (best-effort)
    try {
      var thread = GmailApp.getThreadById(threadId);
      var msgs = thread.getMessages();
      msgs.forEach(function(m) {
        var atts = m.getAttachments ? m.getAttachments() : [];
        if (atts && atts.length > 0) {
          try {
            storeMessageAttachments(threadId, m);
          } catch (attErr) {
            Logger.log("storeMessageAttachments failed for message: " + (m.getId ? m.getId() : "unknown") + " - " + attErr.message);
          }
        }
      });
    } catch (attErrGlobal) {
      Logger.log("Attachment store (draft) failed: " + attErrGlobal.message);
    }
    
    var draftContent = callFlaskAPI(draftPrompt, "draft");
    
    // Get the thread and create draft using compose action
    var thread = GmailApp.getThreadById(threadId);
    var messages = thread.getMessages();
    var lastMessage = messages[messages.length - 1];
    
    // Get recipient and subject
    var recipient = lastMessage.getFrom();
    var subject = lastMessage.getSubject();
    if (!subject.match(/^Re:/i)) {
      subject = "Re: " + subject;
    }
    
    try {
      // Try to create reply draft
      thread.createDraftReply(draftContent);
      var successMsg = "✅ A draft response has been created in your Gmail drafts and is ready to send!";
    } catch (draftError) {
      // Fallback: create as new draft
      GmailApp.createDraft(recipient, subject, draftContent);
      var successMsg = "✅ A draft has been created. Note: It may not be threaded with the original email.";
    }
    
    // Format draft preview
    var draftPreview = draftContent.substring(0, 800);
    if (draftContent.length > 800) {
      draftPreview += "\n\n<i>... (draft continues)</i>";
    }
    
    // Show success message
    var card = CardService.newCardBuilder()
      .setHeader(
        CardService.newCardHeader()
          .setTitle("Draft Created")
          .setSubtitle("Ready to review and send")
      )
      .addSection(
        CardService.newCardSection()
          .addWidget(
            CardService.newDecoratedText()
              .setText("<b>" + successMsg + "</b>")
              .setWrapText(true)
          )
      )
      .addSection(
        CardService.newCardSection()
          .setHeader("📧 Draft Preview")
          .setCollapsible(true)
          .setNumUncollapsibleWidgets(0)
          .addWidget(
            CardService.newTextParagraph()
              .setText(draftPreview)
          )
      )
      .addSection(
        CardService.newCardSection()
          .addWidget(
            CardService.newButtonSet()
              .addButton(
                CardService.newTextButton()
                  .setText("📬 View Drafts")
                  .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
                  .setBackgroundColor("#4285F4")
                  .setOpenLink(CardService.newOpenLink()
                    .setUrl("https://mail.google.com/mail/u/0/#drafts")
                    .setOpenAs(CardService.OpenAs.FULL_SIZE))
              )
              .addButton(
                CardService.newTextButton()
                  .setText("🏠 Home")
                  .setOnClickAction(
                    CardService.newAction().setFunctionName("buildAddOn")
                  )
              )
          )
      );
    
    return card.build();
    
  } catch (error) {
    return showError("Error creating draft: " + error.message + "\n\nPlease ensure all permissions are granted.");
  }
}

/**
 * UPDATED: Chat interface - sends data to server, no local caching
 */
function showChatInterface(e) {
  try {
    var messageId = e.gmail.messageId;
    var thread = GmailApp.getMessageById(messageId).getThread();
    var threadId = getCanonicalThreadId(thread);
    var messages = thread.getMessages();
    
    // Send email data to server in new format
    try {
      logEmailMessages(threadId, messages);
      Logger.log("Email messages logged successfully for thread: " + threadId);
    } catch (logErr) {
      Logger.log("Failed to log email messages: " + logErr.message);
      // Continue anyway - logging failure shouldn't block chat
    }
    
    // Send attachments to server
    try {
      messages.forEach(function(m) {
        var atts = m.getAttachments ? m.getAttachments() : [];
        if (atts && atts.length > 0) {
          storeMessageAttachments(threadId, m);
        }
      });
      Logger.log("Attachments stored successfully for thread: " + threadId);
    } catch (attErr) {
      Logger.log("Failed to store attachments: " + attErr.message);
      // Continue anyway - attachment failure shouldn't block chat
    }
    
    // REMOVED: No longer caching thread text locally
    // The server already has all the data from logEmailMessages()
    
    // Clear previous chat history for this thread
    var cache = CacheService.getUserCache();
    cache.remove("chat_history_" + threadId);
    
    // Show chat interface
    return buildChatCardWithInfo(threadId, [], null);
    
  } catch (error) {
    return showError("Error opening chat: " + error.message);
  }
}

/**
 * NEW: Enhanced chat card builder with optional processing info
 */
function buildChatCardWithInfo(threadId, chatHistory, processingInfo) {
  var card = CardService.newCardBuilder()
    .setHeader(
      CardService.newCardHeader()
        .setTitle("Thread Chat")
        .setSubtitle("RAG-powered Q&A on emails & attachments")
    );
  
  // Intro hint when no history
  if (!chatHistory || chatHistory.length === 0) {
    card.addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newDecoratedText()
            .setText("<b>💬 Ask anything about this thread</b>")
            .setBottomLabel("Fully indexed · Ask anything")
            .setWrapText(true)
        )
    );
  }
  
  // Show processing info if provided
  if (processingInfo) {
    card.addSection(
      CardService.newCardSection()
        .setHeader("📊 Context Loaded")
        .setCollapsible(true)
        .setNumUncollapsibleWidgets(0)
        .addWidget(
          CardService.newTextParagraph()
            .setText(processingInfo)
        )
    );
  }
  
  // Show chat history
  if (chatHistory && chatHistory.length > 0) {
    var chatSection = CardService.newCardSection();
    
    chatHistory.forEach(function(msg, index) {
      if (msg.role === "user") {
        chatSection.addWidget(
          CardService.newTextParagraph()
            .setText('<b>You:</b><br>' + escapeHtml(msg.content))
        );
      } else {
        var formattedResponse = formatMarkdownToHtml(msg.content);
        chatSection.addWidget(
          CardService.newTextParagraph()
            .setText('<b>AI:</b><br>' + formattedResponse)
        );
      }
      
      if (index < chatHistory.length - 1) {
        chatSection.addWidget(CardService.newDivider());
      }
    });
    
    card.addSection(chatSection);
  } else {
    card.addSection(
      CardService.newCardSection()
        .setHeader("💡 Suggested Questions")
        .addWidget(
          CardService.newDecoratedText()
            .setText("Key points in attachments?")
            .setWrapText(true)
        )
        .addWidget(
          CardService.newDecoratedText()
            .setText("What decisions were made?")
            .setWrapText(true)
        )
        .addWidget(
          CardService.newDecoratedText()
            .setText("What does the PDF say about...?")
            .setWrapText(true)
        )
        .addWidget(
          CardService.newDecoratedText()
            .setText("Who approved what and when?")
            .setWrapText(true)
        )
    );
  }
  
  // Input section
  var inputSection = CardService.newCardSection()
    .addWidget(CardService.newDivider())
    .addWidget(
      CardService.newTextInput()
        .setFieldName("userQuestion")
        .setTitle("Your Question")
        .setHint("e.g. What decisions were made in this thread?")
        .setMultiline(true)
    )
    .addWidget(
      CardService.newButtonSet()
        .addButton(
          CardService.newTextButton()
            .setText("📤 Send")
            .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
            .setBackgroundColor("#7C4DFF")
            .setOnClickAction(
              CardService.newAction()
                .setFunctionName("chatWithThread")
                .setParameters({threadId: threadId})
            )
        )
        .addButton(
          CardService.newTextButton()
            .setText("🗑️ Clear")
            .setOnClickAction(
              CardService.newAction()
                .setFunctionName("clearChatHistory")
                .setParameters({threadId: threadId})
            )
        )
        .addButton(
          CardService.newTextButton()
            .setText("🏠 Home")
            .setOnClickAction(
              CardService.newAction().setFunctionName("buildAddOn")
            )
        )
    );
  
  card.addSection(inputSection);
  
  return card.build();
}


/**
 * NEW: Chat with thread using RAG (attachments + emails)
 * Handles user questions about the email thread with full context
 */
function chatWithThread(e) {
  try {
    var threadId = e.parameters.threadId;
    var userQuestion = e.formInput.userQuestion;
    
    if (!userQuestion || userQuestion.trim() === "") {
      return showError("Please enter a question.");
    }
    
    // Get user ID
    var userId = Session.getEffectiveUser().getEmail();
    
    // Show loading state
    Logger.log("Processing chat request for thread: " + threadId);
    
    // Call chat-with-thread API
    var flaskUrl = PropertiesService.getScriptProperties()
      .getProperty("FLASK_SERVER_URL");
    
    if (!flaskUrl) {
      throw new Error("Flask server URL not configured.");
    }
    
    // Normalize base URL: remove trailing slash and /api suffix to avoid double /api
    var baseUrl = flaskUrl.replace(/\/$/, '').replace(/\/api$/, '');
    var apiEndpoint = baseUrl + '/api/chat-with-thread';
    
    var payload = {
      user_id: userId,
      thread_id: threadId,
      question: userQuestion
    };
    
    var options = {
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    };
    
    Logger.log("Calling chat API: " + apiEndpoint);
    var response = UrlFetchApp.fetch(apiEndpoint, options);
    var responseCode = response.getResponseCode();
    var responseText = response.getContentText();
    
    Logger.log("Response code: " + responseCode);
    
    if (responseCode !== 200) {
      throw new Error("Server error (" + responseCode + "): " + responseText.substring(0, 200));
    }
    
    var initialData = JSON.parse(responseText);

    // If server returned a job_id, poll until done
    var result;
    if (initialData.job_id) {
      result = pollJobStatus(initialData.job_id, 120000);
    } else {
      result = initialData;
    }
    
    if (!result.success) {
      throw new Error(result.error || "Unknown error from server");
    }
    
    // Get chat history from cache
    var cache = CacheService.getUserCache();
    var chatHistoryJson = cache.get("chat_history_" + threadId) || "[]";
    var chatHistory = JSON.parse(chatHistoryJson);
    
    // Add new Q&A to history
    chatHistory.push({role: "user", content: userQuestion});
    chatHistory.push({role: "assistant", content: result.answer});
    
    // Keep only last 10 messages
    if (chatHistory.length > 10) {
      chatHistory = chatHistory.slice(-10);
    }
    
    // Save updated history
    cache.put("chat_history_" + threadId, JSON.stringify(chatHistory), 21600);
    
    // Build result card with processing info
    var processingInfo = result.processing_info || {};
    var emailInfo = processingInfo.emails || {};
    var attachmentInfo = processingInfo.attachments || {};
    
    var processingMsg = "📊 Processing Summary:\n";
    
    if (emailInfo.total_messages) {
      processingMsg += "• Total messages: " + emailInfo.total_messages + "\n" +
        "• Already processed: " + emailInfo.already_processed + "\n" +
        "• Newly processed: " + emailInfo.newly_processed + "\n";
    }
    
    if (attachmentInfo.attachments_found > 0) {
      processingMsg += "• Attachments found: " + attachmentInfo.attachments_found + "\n" +
        "• Attachments processed: " + attachmentInfo.attachments_processed + "\n" +
        "• Attachments cached: " + attachmentInfo.attachments_skipped;
    }
    
    // Show processing info if first message in conversation
    var showProcessing = chatHistory.length <= 2;
    
    // Rebuild chat card with updated history and optional processing info
    return buildChatCardWithInfo(threadId, chatHistory, showProcessing ? processingMsg : null);
    
  } catch (error) {
    Logger.log("chatWithThread error: " + error.message);
    return showError("Error in chat: " + error.message);
  }
}

/**
 * Clears chat history
 */
function clearChatHistory(e) {
  try {
    var threadId = e.parameters.threadId;
    var cache = CacheService.getUserCache();
    cache.remove("chat_history_" + threadId);
    
    return buildChatCard(threadId, []);
  } catch (error) {
    return showError("Error clearing chat: " + error.message);
  }
}

/**
 * Escapes HTML special characters
 */
function escapeHtml(text) {
  if (!text) return "";
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

/**
 * Calls Flask Server API (with Ollama/llama3.2 backend)
 */
function callFlaskAPI(content, action) {
  var flaskUrl = PropertiesService.getScriptProperties()
    .getProperty("FLASK_SERVER_URL");
  
  if (!flaskUrl) {
    throw new Error("Flask server URL not configured. Please set FLASK_SERVER_URL in Script Properties.");
  }
  
  var apiEndpoint = 'https://lsdiedb39c.pagekite.me/' + '/chat';
  
  // Build appropriate prompt based on action
  var prompt;
  if (action === "summarize") {
    prompt = "You are an expert enterprise communication analyst.\n" +
      "You will be given a batch of related email threads (20–30 emails) that belong to the same conversation.\n" +
      "Your task is to analyze ALL emails carefully and produce a **chronological, structured summary**.\n\n" +
      "### Instructions\n" +
      "1. Read every email in full.\n" +
      "2. Identify the **true chronological order** based on timestamps and context.\n" +
      "3. Merge replies and forwards logically (do not repeat content).\n" +
      "4. Ignore greetings, signatures, and disclaimers unless they add meaning.\n" +
      "5. Focus on decisions, requests, approvals, blockers, and commitments.\n\n" +
      "---\n\n" +
      "### Output Format (STRICT)\n\n" +
      "#### 1️⃣ Conversation Overview\n" +
      "- **Topic:** <one-line summary of what this email thread is about>\n" +
      "- **Participants:** <key people and their roles>\n" +
      "- **Time Range:** <first email date → last email date>\n\n" +
      "---\n\n" +
      "#### 2️⃣ Chronological Timeline of Events\n" +
      "(List in exact order — earliest to latest)\n\n" +
      "**Step 1 – <Short Title>**\n" +
      "- What happened: <one concise line>\n" +
      "- Outcome / Decision: <if any>\n" +
      "- Expectation / Ask at this stage: <what was requested or expected next>\n\n" +
      "**Step 2 – <Short Title>**\n" +
      "- What happened: <one concise line>\n" +
      "- Outcome / Decision: <if any>\n" +
      "- Expectation / Ask at this stage: <what was requested or expected next>\n\n" +
      "(Repeat for all major events. Use **2 lines only** if the event is large or critical.)\n\n" +
      "---\n\n" +
      "#### 3️⃣ Current Status (As of Last Email)\n" +
      "- **Current State:** <e.g., Awaiting approval / In progress / Blocked / Completed>\n" +
      "- **Owner:** <person responsible now>\n" +
      "- **Pending Actions:** <bullet list if multiple>\n\n" +
      "---\n\n" +
      "#### 4️⃣ Open Questions / Pending Requests\n" +
      "(List anything that is still unanswered or waiting)\n" +
      "- <Question or request>\n" +
      "- <Who needs to respond>\n\n" +
      "---\n\n" +
      "#### 5️⃣ Final Ask / Next Expected Action\n" +
      "(Clearly state what the sender expects next)\n" +
      "- **Action Required:** <clear action>\n" +
      "- **From Whom:** <person/team>\n" +
      "- **Deadline (if mentioned):** <date or \"Not specified\">\n\n" +
      "---\n\n" +
      "### Rules\n" +
      "- Be factual and neutral.\n" +
      "- Do NOT invent information.\n" +
      "- Do NOT summarize per email — summarize per **event**.\n" +
      "- Keep language professional and concise.\n" +
      "- Prefer clarity over verbosity.\n\n" +
      "Email Thread:\n" + content;
  } else {
    // For draft and chat, use content as-is (already contains instructions)
    prompt = content;
  }
  
  var payload = {
    prompt: prompt
  };
  
  var options = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };
  
  try {
    var response = UrlFetchApp.fetch(apiEndpoint, options);
    var data = JSON.parse(response.getContentText());
    
    if (data.error) {
      throw new Error("Flask API error: " + data.error);
    }
    
    if (data.response) {
      return data.response;
    }
    
    throw new Error("Unexpected API response format");
    
  } catch (error) {
    if (error.message.indexOf("Timeout") !== -1) {
      throw new Error("Request timeout - the server took too long to respond.");
    }
    throw error;
  }
}

/**
 * Shows a premium error card
 */
function showError(message) {
  return CardService.newCardBuilder()
    .setHeader(
      CardService.newCardHeader()
        .setTitle("Something went wrong")
        .setSubtitle("Please review the details below")
    )
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newDecoratedText()
            .setText("<b>❌ Error</b>")
            .setBottomLabel(message)
            .setWrapText(true)
        )
    )
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newButtonSet()
            .addButton(
              CardService.newTextButton()
                .setText("🏠 Back to Home")
                .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
                .setBackgroundColor("#4285F4")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("buildAddOn")
                )
            )
        )
    )
    .build();
}

/**
 * Setup function - run this once to configure your Flask server URL
 */
function setupFlaskUrl() {
  Logger.log("Go to Project Settings > Script Properties to add FLASK_SERVER_URL");
  Logger.log("Example: https://url-xyz/df");
}

/**
 * Test function - use this to verify your Flask API connection
 */
function testFlaskConnection() {
  try {
    var testPrompt = "Hello, this is a test message.";
    var result = callFlaskAPI(testPrompt, "chat");
    Logger.log("Success! API Response: " + result);
    return result;
  } catch (error) {
    Logger.log("Error testing Flask API: " + error.message);
    throw error;
  }
}
/** 
 * NEW: Log all email messages in a thread to server as single JSON file
 * Sends all messages in one API call
 */
function logEmailMessages(threadId, messages) {
  Logger.log("   [logEmailMessages] Starting...");
  var flaskUrl = PropertiesService.getScriptProperties()
    .getProperty("FLASK_SERVER_URL");
  
  Logger.log("   [logEmailMessages] Flask URL: " + flaskUrl);
  if (!flaskUrl) {
    throw new Error("FLASK_SERVER_URL not configured in Script Properties.");
  }
  
  // Normalize base URL: remove trailing slash and /api suffix to avoid double /api
  var baseUrl = flaskUrl.replace(/\/$/, '').replace(/\/api$/, '');
  var endpoint = baseUrl + '/api/log-email';
  Logger.log("   [logEmailMessages] Endpoint: " + endpoint);
  
  var userId = Session.getEffectiveUser().getEmail();
  Logger.log("   [logEmailMessages] User ID: " + userId);
  Logger.log("   [logEmailMessages] Processing " + messages.length + " messages...");
  
  // Convert all GmailMessages to array format
  var messageArray = messages.map(function (msg, idx) {
    try {
      Logger.log("      [Message " + (idx + 1) + "] Getting ID...");
      var msgId = msg.getId();
      Logger.log("      [Message " + (idx + 1) + "] ID: " + msgId);
      
      Logger.log("      [Message " + (idx + 1) + "] Getting from...");
      var fromStr = msg.getFrom() || "unknown";
      Logger.log("      [Message " + (idx + 1) + "] From: " + fromStr);
      
      Logger.log("      [Message " + (idx + 1) + "] Getting to...");
      var toStr = msg.getTo() || "";
      var toArray = toStr.length > 0 ? toStr.split(',').map(function (email) {
        return email.trim();
      }) : [];
      Logger.log("      [Message " + (idx + 1) + "] To: " + toArray.length + " recipients");
      
      Logger.log("      [Message " + (idx + 1) + "] Getting subject...");
      var subjectStr = msg.getSubject() || "";
      Logger.log("      [Message " + (idx + 1) + "] Subject: " + subjectStr);
      
      Logger.log("      [Message " + (idx + 1) + "] Getting date...");
      var date = msg.getDate();
      var timestamp = date ? Utilities.formatDate(date, Session.getScriptTimeZone(), "yyyy-MM-dd'T'HH:mm:ss'Z'") : new Date().toISOString();
      Logger.log("      [Message " + (idx + 1) + "] Date: " + timestamp);
      
      Logger.log("      [Message " + (idx + 1) + "] Getting body...");
      var bodyStr = msg.getPlainBody() || "";
      Logger.log("      [Message " + (idx + 1) + "] Body length: " + bodyStr.length + " chars");
      
      var result = {
        message_id: msgId,
        from_address: fromStr,
        to: toArray,
        subject: subjectStr,
        timestamp: timestamp,
        body: bodyStr
      };
      Logger.log("      [Message " + (idx + 1) + "] ✓ Complete");
      return result;
    } catch (e) {
      Logger.log("      [Message " + (idx + 1) + "] ❌ Error: " + e.message);
      return {
        message_id: msg.getId ? msg.getId() : "unknown",
        from_address: "unknown",
        to: [],
        subject: "[Error processing message]",
        timestamp: Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "yyyy-MM-dd'T'HH:mm:ss'Z'"),
        body: ""
      };
    }
  });

  Logger.log("   [logEmailMessages] Message array built: " + messageArray.length + " messages");

  // Build payload in required format
  var payload = {
    user_id: userId,
    thread_id: threadId,
    messages: messageArray
  };

  Logger.log("   [logEmailMessages] Building fetch options...");
  var options = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };
  Logger.log("   [logEmailMessages] ✓ Options built");

  try {
    Logger.log("   [logEmailMessages] Sending POST to: " + endpoint);
    var resp = UrlFetchApp.fetch(endpoint, options);
    var responseCode = resp.getResponseCode();
    Logger.log("   [logEmailMessages] Response code: " + responseCode);

    if (responseCode !== 200) {
      var errorText = resp.getContentText();
      Logger.log("   [logEmailMessages] ❌ Error response: " + errorText.substring(0, 300));
      throw new Error("Server returned " + responseCode + ": " + errorText);
    }

    Logger.log("   [logEmailMessages] ✓ Logged " + messageArray.length + " messages successfully");
    return resp.getContentText();

  } catch (err) {
    Logger.log("   [logEmailMessages] ❌ Failed: " + err.message);
    throw new Error("Failed to log email messages: " + err.message);
  }
}


/**
 * NEW: Store attachments of a given GmailMessage to your Flask server /store-attachments
 * Sends only allowed file types: PDF, CSV, PPTX, PPT
 */
function storeMessageAttachments(threadId, message) {
  Logger.log("      [storeMessageAttachments] Starting...");
  var flaskUrl = PropertiesService.getScriptProperties().getProperty("FLASK_SERVER_URL");
  if (!flaskUrl) {
    throw new Error("FLASK_SERVER_URL not configured.");
  }
  // Normalize base URL: remove trailing slash and /api suffix to avoid double /api
  var baseUrl = flaskUrl.replace(/\/$/, '').replace(/\/api$/, '');
  var endpoint = baseUrl + '/api/store-attachments';
  
  Logger.log("      [storeMessageAttachments] Endpoint: " + endpoint);
  
  // Allowed file extensions
  var ALLOWED_EXTENSIONS = ['.pdf', '.csv', '.pptx', '.ppt'];
  
  // message may be a GmailMessage; extract id and attachments
  var messageId = (message.getId && message.getId()) || "unknown";
  var blobs = (message.getAttachments && message.getAttachments()) || [];
  
  Logger.log("      [storeMessageAttachments] Message ID: " + messageId);
  Logger.log("      [storeMessageAttachments] Total blobs: " + blobs.length);
  
  if (!blobs || blobs.length === 0) {
    Logger.log("      [storeMessageAttachments] No attachments to process");
    return null;
  }
  
  // Filter out inline attachments AND filter by allowed extensions
  var filteredBlobs = blobs.filter(function(b) {
    var isInline = b.isInline ? b.isInline() : false;
    var filename = b.getName ? b.getName() : "";
    var filenameLower = filename.toLowerCase();
    
    // Check if file has an allowed extension
    var hasAllowedExtension = ALLOWED_EXTENSIONS.some(function(ext) {
      return filenameLower.endsWith(ext);
    });
    
    if (isInline) {
      Logger.log("      [storeMessageAttachments]   ⊘ " + filename + " - inline, skipping");
      return false;
    }
    
    if (!hasAllowedExtension) {
      Logger.log("      [storeMessageAttachments]   ⊘ " + filename + " - not an allowed file type, skipping");
      return false;
    }
    
    Logger.log("      [storeMessageAttachments]   ✓ " + filename + " - will upload");
    return true;
  });
  
  // If no valid attachments after filtering, return null
  if (filteredBlobs.length === 0) {
    Logger.log("      [storeMessageAttachments] No valid attachments to upload (after filtering inline and file types)");
    return null;
  }
  
  Logger.log("      [storeMessageAttachments] Processing " + filteredBlobs.length + " valid attachments...");
  var attachments = [];
  for (var i = 0; i < filteredBlobs.length; i++) {
    try {
      var b = filteredBlobs[i];
      Logger.log("      [storeMessageAttachments] Attachment " + (i + 1) + ": " + (b.getName ? b.getName() : "unknown"));
      
      var bytes = b.getBytes && b.getBytes();
      Logger.log("      [storeMessageAttachments]   Got bytes: " + (bytes ? bytes.length + " bytes" : "null"));
      
      if (!bytes || bytes.length === 0) {
        Logger.log("      [storeMessageAttachments]   ⚠️ Warning: Failed to get bytes from attachment: " + (b.getName ? b.getName() : "unknown"));
        continue;
      }
      
      Logger.log("      [storeMessageAttachments]   Encoding to base64...");
      var encoded = Utilities.base64Encode(bytes);
      Logger.log("      [storeMessageAttachments]   Encoded: " + (encoded ? encoded.length + " chars" : "null"));
      
      if (!encoded) {
        Logger.log("      [storeMessageAttachments]   ⚠️ Warning: Failed to encode attachment: " + (b.getName ? b.getName() : "unknown"));
        continue;
      }
      
      attachments.push({
        filename: b.getName ? b.getName() : "attachment",
        content: encoded,
        mime_type: b.getContentType ? b.getContentType() : "application/octet-stream"
      });
      Logger.log("      [storeMessageAttachments]   ✓ Added to payload");
    } catch (encodeErr) {
      Logger.log("      [storeMessageAttachments]   ⚠️ Error encoding attachment " + i + ": " + encodeErr.message);
    }
  }
  
  Logger.log("      [storeMessageAttachments] Final attachments count: " + attachments.length);
  var userId = Session.getEffectiveUser().getEmail();
  
  var payload = {
    user_id: userId,
    thread_id: threadId || "unknown",
    message_id: messageId,
    attachments: attachments
  };
  
  var options = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };
  
  Logger.log("      [storeMessageAttachments] 📤 Uploading " + attachments.length + " attachments to: " + endpoint);
  
  try {
    var resp = UrlFetchApp.fetch(endpoint, options);
    var responseCode = resp.getResponseCode();
    Logger.log("      [storeMessageAttachments] Upload response code: " + responseCode);
    if (responseCode !== 200) {
      Logger.log("      [storeMessageAttachments] ❌ Upload error: " + resp.getContentText());
    }
    return resp.getContentText();
  } catch (err) {
    Logger.log("      [storeMessageAttachments] ❌ Attachment upload error: " + err.message);
    throw new Error("Failed to store attachments: " + err.message);
  }
}

// ============================================================================
// SETTINGS UI - User Configuration for LLM, Embedding, and Vector Providers
// ============================================================================

/**
 * Show the settings card where users can configure their providers
 * Supports "Inbuilt" mode (zero-config) or "Custom" mode (user-supplied keys)
 */
// ============================================================================
// SETTINGS CARD — INTERNAL BUILDER WITH DYNAMIC MODEL FETCH
// ============================================================================

/**
 * Internal card builder for the Settings page.
 * Uses the same transient-state/re-render pattern as _buildOnboardingStep1Card().
 *
 * Transient state (UserProperties, cleared after each render):
 *   sett_llm_msg / sett_llm_ok          — LLM validation status message
 *   sett_emb_msg / sett_emb_ok          — Embedding validation status message
 *   sett_save_msg / sett_save_ok        — Save confirmation message
 *   sett_llm_models_{provider}          — JSON-serialized list of fetched LLM models
 *   sett_emb_models_{provider}          — JSON-serialized list of fetched embedding models
 */
function _buildSettingsCard() {
  var userProps       = PropertiesService.getUserProperties();
  var currentSettings = loadUserSettings();

  // ── Read + clear transient state ─────────────────────────────────────
  var llmMsg  = userProps.getProperty("sett_llm_msg")  || "";
  var llmOk   = userProps.getProperty("sett_llm_ok")   === "true";
  var embMsg  = userProps.getProperty("sett_emb_msg")  || "";
  var embOk   = userProps.getProperty("sett_emb_ok")   === "true";
  var saveMsg = userProps.getProperty("sett_save_msg") || "";
  var saveOk  = userProps.getProperty("sett_save_ok")  === "true";
  userProps.deleteProperty("sett_llm_msg");  userProps.deleteProperty("sett_llm_ok");
  userProps.deleteProperty("sett_emb_msg");  userProps.deleteProperty("sett_emb_ok");
  userProps.deleteProperty("sett_save_msg"); userProps.deleteProperty("sett_save_ok");

  // Support both old and new mode values
  var mode = currentSettings.mode || "manotr";
  if (mode === "inbuilt") mode = "manotr";
  if (mode === "custom")  mode = "external";

  var isManotr   = (mode === "manotr");
  var llmProv    = currentSettings.llm_provider       || "manotr";
  var embedProv  = currentSettings.embedding_provider || "manotr";
  var vectorProv = currentSettings.vector_provider    || "manotr";
  var llmModel   = currentSettings.llm_model          || "gpt-4o-mini";
  var embedModel = currentSettings.embedding_model    || "text-embedding-3-small";
  var userName   = currentSettings.user_name          || "Not set";
  var userPos    = currentSettings.user_position      || "Not set";
  var agentUrl   = currentSettings.agent_url          || "http://omb.manotr.com";
  var modeLabel  = isManotr ? "✨ Manotr Mode" : (mode === "local" ? "🖥️ Local Mode" : "⚡ External API Mode");

  // Read stored models (keyed by provider so they survive provider switches)
  var llmModels = [];
  var embModels = [];
  try { llmModels = JSON.parse(userProps.getProperty("sett_llm_models_" + llmProv)  || "[]"); } catch (ex) {}
  try { embModels = JSON.parse(userProps.getProperty("sett_emb_models_" + embedProv) || "[]"); } catch (ex) {}

  // Static curated model catalogues — fallback before any API fetch
  var STATIC_LLM = {
    openai:    ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo", "o1", "o1-mini"],
    anthropic: ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022",
                "claude-3-opus-20240229", "claude-3-haiku-20240307"],
    groq:      ["llama-3.3-70b-versatile", "llama-3.1-8b-instant",
                "llama-3.1-70b-versatile", "mixtral-8x7b-32768", "gemma2-9b-it"],
    ollama:    ["llama3.3", "llama3.2", "llama3.1", "mistral", "phi4",
                "qwen2.5", "deepseek-r1", "gemma2", "codellama"]
  };
  var STATIC_EMB = {
    openai: ["text-embedding-3-small", "text-embedding-3-large", "text-embedding-ada-002"],
    ollama: ["nomic-embed-text", "mxbai-embed-large", "snowflake-arctic-embed", "bge-large", "all-minilm"]
  };

  var isLlmCloud  = (["openai", "anthropic", "groq"].indexOf(llmProv) !== -1);
  var isLlmOllama = (llmProv === "ollama");
  var isEmbCloud  = (embedProv === "openai");
  var isEmbOllama = (embedProv === "ollama");

  var card = CardService.newCardBuilder()
    .setHeader(
      CardService.newCardHeader()
        .setTitle("⚙️  OpenMailBot Settings")
        .setSubtitle(modeLabel + " — Tap sections to expand")
    );

  // ── Save / validation status banner ────────────────────────────────────
  if (saveMsg) {
    card.addSection(
      CardService.newCardSection()
        .addWidget(CardService.newTextParagraph()
          .setText(saveOk ? "✅  " + saveMsg : "❌  " + saveMsg))
    );
  }

  // ── Active Config Status ───────────────────────────────────────────────
  card.addSection(
    CardService.newCardSection()
      .addWidget(
        CardService.newDecoratedText()
          .setTopLabel("● ACTIVE CONFIGURATION")
          .setText("<b>" + (isManotr
              ? "✨  Manotr Mode — Zero Configuration"
              : (mode === "local"
                  ? "🖥️  Local Mode — Self-hosted Services"
                  : "⚡  External API Mode — Your API Keys Active")) + "</b>")
          .setBottomLabel(
            "🤖 LLM: " + llmProv.toUpperCase() + "  ·  📊 Embed: " + embedProv.toUpperCase() +
            "  ·  🗄️ Vector: " + vectorProv.toUpperCase() + "  ·  👤 " + userName
          )
          .setWrapText(true)
      )
  );

  // ── Configuration Mode ─────────────────────────────────────────────────
  card.addSection(
    CardService.newCardSection()
      .setHeader("🔧  CONFIGURATION MODE")
      .addWidget(
        CardService.newTextParagraph()
          .setText(
            "✨ <b>Manotr</b> — No setup needed. Uses OpenMailBot hosted services.\n" +
            "🖥️ <b>Local</b> — Use locally hosted services like Ollama.\n" +
            "⚡ <b>External API</b> — Supply your own API keys for full control & privacy."
          )
      )
      .addWidget(
        CardService.newSelectionInput()
          .setType(CardService.SelectionInputType.RADIO_BUTTON)
          .setFieldName("mode")
          .setTitle("Select Mode")
          .addItem("✨  Manotr  (Zero Configuration — Recommended)", "manotr", isManotr)
          .addItem("🖥️  Local  (Ollama / Self-hosted)", "local", mode === "local")
          .addItem("⚡  External API  (Your Own API Keys)", "external", mode === "external")
      )
      .addWidget(
        CardService.newTextInput()
          .setFieldName("agent_url")
          .setTitle("🌐 Agent Server URL")
          .setValue(agentUrl)
          .setHint("http://omb.manotr.com  ·  http://localhost:5051  ·  https://your-server.com")
      )
  );

  // ── AI Language Model ──────────────────────────────────────────────────
  var llmSection = CardService.newCardSection()
    .setHeader("🤖  AI LANGUAGE MODEL")
    .setCollapsible(true)
    .setNumUncollapsibleWidgets(1)
    .addWidget(
      CardService.newDecoratedText()
        .setTopLabel("CURRENT")
        .setText("<b>" + llmProv.toUpperCase() + "</b>  ·  " + llmModel)
        .setBottomLabel("Summaries, drafts & chats")
        .setWrapText(true)
    )
    .addWidget(
      CardService.newSelectionInput()
        .setType(CardService.SelectionInputType.DROPDOWN)
        .setFieldName("llm_provider")
        .setTitle("LLM Provider")
        .addItem("✨  Manotr  (Default)", "manotr",
                 llmProv === "manotr" || llmProv === "inbuilt" || !llmProv)
        .addItem("🌐  OpenAI  (GPT-4o, GPT-3.5)", "openai",    llmProv === "openai")
        .addItem("🤖  Anthropic  (Claude 3.5)",    "anthropic", llmProv === "anthropic")
        .addItem("⚡  Groq  (Llama, Mixtral — fast & free)", "groq", llmProv === "groq")
        .addItem("🖥️  Ollama  (Local · Remote · Cloud)", "ollama", llmProv === "ollama")
        .setOnChangeAction(CardService.newAction().setFunctionName("handleSettingsLLMProviderChange"))
    );

  // Cloud provider: API key + "Validate API & Fetch Models"
  if (isLlmCloud) {
    llmSection
      .addWidget(
        CardService.newTextInput()
          .setFieldName("llm_api_key")
          .setTitle("🔑  API Key")
          .setValue(currentSettings.llm_api_key || "")
          .setHint(llmProv === "openai"    ? "sk-... (OpenAI key)" :
                   llmProv === "anthropic" ? "sk-ant-... (Anthropic key)" :
                                             "gsk_... (Groq key)")
      )
      .addWidget(
        CardService.newTextButton()
          .setText("✅  Validate API & Fetch Models")
          .setOnClickAction(CardService.newAction().setFunctionName("handleFetchLLMModels"))
      );
    if (llmMsg) {
      llmSection.addWidget(
        CardService.newTextParagraph().setText(llmOk ? "✅  " + llmMsg : "❌  " + llmMsg)
      );
    }
    // Base URL override (external mode only)
    if (mode === "external") {
      llmSection.addWidget(
        CardService.newTextInput()
          .setFieldName("llm_base_url")
          .setTitle("🔗  Base URL Override (optional)")
          .setValue(currentSettings.llm_base_url || "")
          .setHint("Leave empty to use the provider's default endpoint")
      );
    }
  }

  // Ollama: URL + optional token + 3-mode explanation + "Connect & Fetch"
  if (isLlmOllama) {
    llmSection
      .addWidget(
        CardService.newTextParagraph()
          .setText(
            "ℹ️  Ollama works in 3 ways:\n" +
            "  1️⃣  Local — http://localhost:11434  (no auth needed)\n" +
            "  2️⃣  Remote public — your server URL via PageKite / ngrok\n" +
            "  3️⃣  Remote secured — public URL + Bearer token"
          )
      )
      .addWidget(
        CardService.newTextInput()
          .setFieldName("llm_base_url")
          .setTitle("🔗  Ollama URL")
          .setValue(currentSettings.llm_base_url || "http://localhost:11434")
          .setHint("Local: http://localhost:11434  ·  Remote: https://your-ollama.com")
      )
      .addWidget(
        CardService.newTextInput()
          .setFieldName("llm_ollama_api_key")
          .setTitle("🔑  Bearer Token (optional)")
          .setValue(currentSettings.llm_ollama_api_key || "")
          .setHint("Only needed if your Ollama server requires authentication")
      )
      .addWidget(
        CardService.newTextButton()
          .setText("✅  Connect & Fetch Ollama Models")
          .setOnClickAction(CardService.newAction().setFunctionName("handleFetchLLMOllamaModels"))
      );
    if (llmMsg) {
      llmSection.addWidget(
        CardService.newTextParagraph().setText(llmOk ? "✅  " + llmMsg : "❌  " + llmMsg)
      );
    }
  }

  // Model dropdown: live fetched → static catalogue → text input fallback
  if (llmProv !== "manotr") {
    var llmModelList = (llmModels.length > 0) ? llmModels : (STATIC_LLM[llmProv] || []);
    if (llmModelList.length > 0) {
      var llmModelSel = CardService.newSelectionInput()
        .setType(CardService.SelectionInputType.DROPDOWN)
        .setFieldName("llm_model")
        .setTitle("📦  Model" +
          (llmModels.length > 0 ? " (live — fetched from API)" : " (curated list — click Validate to refresh)"));
      for (var li = 0; li < llmModelList.length; li++) {
        var lm = llmModelList[li];
        llmModelSel.addItem(lm, lm, lm === llmModel);
      }
      // Keep saved model in list even if not in fetched results
      if (llmModel && llmModelList.indexOf(llmModel) === -1) {
        llmModelSel.addItem("📌 " + llmModel + " (saved)", llmModel, true);
      }
      llmSection.addWidget(llmModelSel);
    } else {
      llmSection.addWidget(
        CardService.newTextInput()
          .setFieldName("llm_model")
          .setTitle("📦  Model Name")
          .setValue(llmModel)
          .setHint("Click 'Validate & Fetch Models' above to populate this dropdown")
      );
    }
  }
  card.addSection(llmSection);

  // ── Embedding Engine ───────────────────────────────────────────────────
  var embSection = CardService.newCardSection()
    .setHeader("📊  EMBEDDING ENGINE")
    .setCollapsible(true)
    .setNumUncollapsibleWidgets(1)
    .addWidget(
      CardService.newDecoratedText()
        .setTopLabel("CURRENT")
        .setText("<b>" + embedProv.toUpperCase() + "</b>  ·  " + embedModel)
        .setBottomLabel("Semantic email search")
        .setWrapText(true)
    )
    .addWidget(
      CardService.newSelectionInput()
        .setType(CardService.SelectionInputType.DROPDOWN)
        .setFieldName("embedding_provider")
        .setTitle("Embedding Provider")
        .addItem("✨  Manotr  (Default)", "manotr",
                 embedProv === "manotr" || embedProv === "inbuilt" || !embedProv)
        .addItem("🌐  OpenAI Embeddings", "openai", embedProv === "openai")
        .addItem("🖥️  Ollama  (Local · Remote · Cloud)", "ollama", embedProv === "ollama")
        .setOnChangeAction(CardService.newAction().setFunctionName("handleSettingsEmbProviderChange"))
    );

  if (isEmbCloud) {
    embSection
      .addWidget(
        CardService.newTextInput()
          .setFieldName("embedding_api_key")
          .setTitle("🔑  API Key")
          .setValue(currentSettings.embedding_api_key || "")
          .setHint("sk-... (OpenAI key)")
      )
      .addWidget(
        CardService.newTextButton()
          .setText("✅  Validate API & Fetch Models")
          .setOnClickAction(CardService.newAction().setFunctionName("handleFetchEmbeddingModels"))
      );
    if (embMsg) {
      embSection.addWidget(
        CardService.newTextParagraph().setText(embOk ? "✅  " + embMsg : "❌  " + embMsg)
      );
    }
  }

  if (isEmbOllama) {
    embSection
      .addWidget(
        CardService.newTextParagraph()
          .setText(
            "ℹ️  Ollama works in 3 ways:\n" +
            "  1️⃣  Local — http://localhost:11434  (no auth needed)\n" +
            "  2️⃣  Remote public — your server URL via PageKite / ngrok\n" +
            "  3️⃣  Remote secured — public URL + Bearer token"
          )
      )
      .addWidget(
        CardService.newTextInput()
          .setFieldName("embedding_base_url")
          .setTitle("🔗  Ollama URL")
          .setValue(currentSettings.embedding_base_url || "http://localhost:11434")
          .setHint("Local: http://localhost:11434  ·  Remote: https://your-ollama.com")
      )
      .addWidget(
        CardService.newTextInput()
          .setFieldName("embedding_ollama_api_key")
          .setTitle("🔑  Bearer Token (optional)")
          .setValue(currentSettings.embedding_ollama_api_key || "")
          .setHint("Only needed if your Ollama server requires authentication")
      )
      .addWidget(
        CardService.newTextButton()
          .setText("✅  Connect & Fetch Ollama Models")
          .setOnClickAction(CardService.newAction().setFunctionName("handleFetchEmbeddingOllamaModels"))
      );
    if (embMsg) {
      embSection.addWidget(
        CardService.newTextParagraph().setText(embOk ? "✅  " + embMsg : "❌  " + embMsg)
      );
    }
  }

  if (embedProv !== "manotr") {
    var embModelList = (embModels.length > 0) ? embModels : (STATIC_EMB[embedProv] || []);
    if (embModelList.length > 0) {
      var embModelSel = CardService.newSelectionInput()
        .setType(CardService.SelectionInputType.DROPDOWN)
        .setFieldName("embedding_model")
        .setTitle("📦  Model" +
          (embModels.length > 0 ? " (live — fetched from API)" : " (curated list — click Validate to refresh)"));
      for (var ei = 0; ei < embModelList.length; ei++) {
        var em = embModelList[ei];
        embModelSel.addItem(em, em, em === embedModel);
      }
      if (embedModel && embModelList.indexOf(embedModel) === -1) {
        embModelSel.addItem("📌 " + embedModel + " (saved)", embedModel, true);
      }
      embSection.addWidget(embModelSel);
    } else {
      embSection.addWidget(
        CardService.newTextInput()
          .setFieldName("embedding_model")
          .setTitle("📦  Embedding Model")
          .setValue(embedModel)
          .setHint("Click 'Validate & Fetch Models' above to populate this dropdown")
      );
    }
  }
  card.addSection(embSection);

  // ── Vector Database ────────────────────────────────────────────────────
  card.addSection(
    CardService.newCardSection()
      .setHeader("🗄️  VECTOR DATABASE")
      .setCollapsible(true)
      .setNumUncollapsibleWidgets(1)
      .addWidget(
        CardService.newDecoratedText()
          .setTopLabel("CURRENT PROVIDER")
          .setText("<b>" + vectorProv.toUpperCase() + "</b>")
          .setBottomLabel("AI knowledge vectors")
          .setWrapText(true)
      )
      .addWidget(
        CardService.newSelectionInput()
          .setType(CardService.SelectionInputType.DROPDOWN)
          .setFieldName("vector_provider")
          .setTitle("Provider")
          .addItem("✨  Manotr  (Default)", "manotr",
                   vectorProv === "manotr" || vectorProv === "inbuilt" || !vectorProv)
          .addItem("📁  Local  (ChromaDB on server)", "local",
                   vectorProv === "local" || vectorProv === "chroma")
          .addItem("🌲  Pinecone  (Cloud)", "pinecone", vectorProv === "pinecone")
          .addItem("🎯  Qdrant  (Cloud / Self-hosted)", "qdrant",
                   vectorProv === "qdrant" || vectorProv === "weaviate")
      )
      .addWidget(
        CardService.newTextInput()
          .setFieldName("vector_url")
          .setTitle("🔗  Server URL")
          .setValue(currentSettings.vector_url || "")
          .setHint("https://your-index.pinecone.io  ·  https://your-qdrant.com")
      )
      .addWidget(
        CardService.newTextInput()
          .setFieldName("vector_api_key")
          .setTitle("🔑  API Key")
          .setValue(currentSettings.vector_api_key || "")
          .setHint("Leave empty for Manotr or Local ChromaDB")
      )
  );

  // ── Your Profile ───────────────────────────────────────────────────────
  card.addSection(
    CardService.newCardSection()
      .setHeader("👤  YOUR PROFILE")
      .setCollapsible(true)
      .setNumUncollapsibleWidgets(1)
      .addWidget(
        CardService.newDecoratedText()
          .setTopLabel("DRAFT PERSONALIZATION")
          .setText("<b>" + userName + "</b>  ·  " + userPos)
          .setBottomLabel("Personalizes drafts")
          .setWrapText(true)
      )
      .addWidget(
        CardService.newTextInput()
          .setFieldName("user_name")
          .setTitle("👤  Full Name")
          .setValue(currentSettings.user_name || "")
          .setHint("e.g., Alex Johnson")
      )
      .addWidget(
        CardService.newTextInput()
          .setFieldName("user_position")
          .setTitle("💼  Job Title / Role")
          .setValue(currentSettings.user_position || "")
          .setHint("e.g., Product Manager · Senior Developer · CEO")
      )
      .addWidget(
        CardService.newSelectionInput()
          .setType(CardService.SelectionInputType.DROPDOWN)
          .setFieldName("user_tone")
          .setTitle("✍️  Writing Tone")
          .addItem("🎯  Professional  (Default)", "professional",
                   currentSettings.user_tone === "professional" || !currentSettings.user_tone)
          .addItem("😊  Friendly & Warm",    "friendly", currentSettings.user_tone === "friendly")
          .addItem("📋  Formal & Structured", "formal",   currentSettings.user_tone === "formal")
          .addItem("💬  Concise",             "concise",
                   currentSettings.user_tone === "concise" || currentSettings.user_tone === "casual")
      )
      .addWidget(
        CardService.newTextInput()
          .setFieldName("system_prompt")
          .setTitle("🧠  Custom AI Instruction")
          .setValue(currentSettings.system_prompt || "")
          .setHint("AI instructions for drafts & summaries")
          .setMultiline(true)
      )
  );

  // ── Advanced Settings Entry ────────────────────────────────────────────
  card.addSection(
    CardService.newCardSection()
      .addWidget(CardService.newDivider())
      .addWidget(
        CardService.newDecoratedText()
          .setTopLabel("BACKGROUND MONITOR  ·  PRIVACY FILTERS")
          .setText("<b>🔒  Advanced Settings</b>")
          .setBottomLabel("Automation & privacy filters")
          .setWrapText(true)
          .setButton(
            CardService.newTextButton()
              .setText("Open →")
              .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
              .setBackgroundColor("#5F6368")
              .setOnClickAction(CardService.newAction().setFunctionName("showAdvancedSettingsCard"))
          )
      )
  );

  // ── Historical Email Processing ────────────────────────────────────────
  var isJobRunning = !!PropertiesService.getScriptProperties().getProperty("bulk_job_state");
  var savedMonthsForSettings = PropertiesService.getScriptProperties().getProperty("process_last_n_months") || "3";

  var historicalSection = CardService.newCardSection()
    .setHeader("📅  HISTORICAL EMAIL PROCESSING");

  historicalSection.addWidget(
    CardService.newDecoratedText()
      .setTopLabel("SAVED TIME WINDOW")
      .setText("<b>" + (savedMonthsForSettings === "10d" ? "10 days" : savedMonthsForSettings + " month" + (savedMonthsForSettings !== "1" ? "s" : "")) + " back</b>")
      .setBottomLabel("Index past emails")
      .setWrapText(true)
  );

  if (isJobRunning) {
    historicalSection.addWidget(
      CardService.newDecoratedText()
        .setTopLabel("● JOB IN PROGRESS")
        .setText("<b>A bulk indexing job is currently running</b>")
        .setBottomLabel("Check progress or stop")
        .setWrapText(true)
    );
    historicalSection.addWidget(
      CardService.newButtonSet()
        .addButton(
          CardService.newTextButton()
            .setText("📊  View Job Status")
            .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
            .setBackgroundColor("#1a73e8")
            .setOnClickAction(CardService.newAction().setFunctionName("showBulkJobStatusCard"))
        )
        .addButton(
          CardService.newTextButton()
            .setText("🛑  Stop Job")
            .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
            .setBackgroundColor("#d93025")
            .setOnClickAction(CardService.newAction().setFunctionName("cancelBulkJobFromUI"))
        )
    );
  } else {
    historicalSection.addWidget(
      CardService.newSelectionInput()
        .setType(CardService.SelectionInputType.DROPDOWN)
        .setFieldName("process_last_n_months")
        .setTitle("📆  Time Window")
        .addItem("🗓️  10 days  (Minimal — very fast)",   "10d", savedMonthsForSettings === "10d")
        .addItem("⚡  1 month   (Fast — recent only)",   "1",  savedMonthsForSettings === "1")
        .addItem("📅  2 months",                         "2",  savedMonthsForSettings === "2")
        .addItem("📅  3 months  (Recommended)",          "3",  savedMonthsForSettings === "3")
        .addItem("📁  6 months  (Deep context)",         "6",  savedMonthsForSettings === "6")
        .addItem("🗂️  12 months  (Full year)",           "12", savedMonthsForSettings === "12")
        .addItem("📦  24 months  (Maximum — slow)",      "24", savedMonthsForSettings === "24")
    );
    historicalSection.addWidget(
      CardService.newButtonSet()
        .addButton(
          CardService.newTextButton()
            .setText("💾  Save Selection")
            .setOnClickAction(CardService.newAction().setFunctionName("saveProcessMonthsSetting"))
        )
        .addButton(
          CardService.newTextButton()
            .setText("▶  Run Now")
            .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
            .setBackgroundColor("#1a73e8")
            .setOnClickAction(CardService.newAction().setFunctionName("runProcessLastNMonths"))
        )
    );
  }
  card.addSection(historicalSection);

  // ── Debug & Reset Tools ────────────────────────────────────────────────
  card.addSection(
    CardService.newCardSection()
      .setHeader("🔧  DEBUG & RESET TOOLS")
      .setCollapsible(true)
      .setNumUncollapsibleWidgets(0)
      .addWidget(
        CardService.newDecoratedText()
          .setTopLabel("FORCE RE-RUN")
          .setText("<b>Clear Processed Messages Tracking</b>")
          .setBottomLabel("Re-process all emails")
          .setWrapText(true)
      )
      .addWidget(
        CardService.newTextParagraph()
          .setText(
            "If emails failed to label due to errors, they were marked as 'processed' " +
            "and won't be retried. Click below to clear the tracking and force a re-run."
          )
      )
      .addWidget(
        CardService.newButtonSet()
          .addButton(
            CardService.newTextButton()
              .setText("🔄  Reset Processed Messages")
              .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
              .setBackgroundColor("#EA4335")
              .setOnClickAction(CardService.newAction().setFunctionName("handleClearProcessedMessages"))
          )
          .addButton(
            CardService.newTextButton()
              .setText("📋  View Trigger Status")
              .setOnClickAction(CardService.newAction().setFunctionName("handleViewTriggerStatus"))
          )
      )
  );

  // ── Action Bar ─────────────────────────────────────────────────────────
  card.addSection(
    CardService.newCardSection()
      .addWidget(
        CardService.newTextButton()
          .setText("💾  Save All Settings")
          .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
          .setBackgroundColor("#0F9D58")
          .setOnClickAction(CardService.newAction().setFunctionName("saveSettings"))
      )
      .addWidget(
        CardService.newButtonSet()
          .addButton(
            CardService.newTextButton()
              .setText("🔄 Reset Defaults")
              .setOnClickAction(CardService.newAction().setFunctionName("resetSettings"))
          )
          .addButton(
            CardService.newTextButton()
              .setText("🏠 Home")
              .setOnClickAction(CardService.newAction().setFunctionName("buildAddOn"))
          )
      )
      .addWidget(
        CardService.newTextButton()
          .setText("🧙  Re-run Setup Wizard")
          .setOnClickAction(CardService.newAction().setFunctionName("resetOnboarding"))
      )
  );

  return card.build();
}

// ============================================================================
// SETTINGS — PROVIDER VALIDATION & MODEL FETCH HANDLERS
// ============================================================================

/**
 * Raw HTTP helper — POST to /api/validate-provider on the given agentUrl.
 * Industry-standard: GET /v1/models (cloud) or GET /api/tags (Ollama) — 0 tokens.
 * Used by both Settings and Onboarding handlers.
 * Returns { valid: bool, message: string, models: [] }
 */
function _validateViaEndpoint(agentUrl, providerType, provider, apiKey, baseUrl) {
  var endpoint = (agentUrl || "http://omb.manotr.com").replace(/\/+$/, "") + "/api/validate-provider";
  try {
    var resp = UrlFetchApp.fetch(endpoint, {
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify({
        provider_type: providerType,
        provider:      provider,
        api_key:       (apiKey  || "").trim(),
        base_url:      (baseUrl || "").trim()
      }),
      muteHttpExceptions: true
    });
    var code = resp.getResponseCode();
    if (code === 200) { return JSON.parse(resp.getContentText()); }
    return { valid: false, message: "Agent returned HTTP " + code, models: [] };
  } catch (err) {
    return { valid: false, message: "Cannot reach agent: " + err.message.substring(0, 100), models: [] };
  }
}

/**
 * Call the agent's /api/validate-provider endpoint synchronously.
 * Uses GET /v1/models (OpenAI/Anthropic/Groq) or GET /api/tags (Ollama) — 0 tokens.
 * Returns { valid: bool, message: string, models: [] }
 */
function _validateProviderViaAgent(providerType, provider, apiKey, baseUrl) {
  var settings = loadUserSettings();
  var agentUrl = PropertiesService.getScriptProperties().getProperty("FLASK_SERVER_URL")
                 || settings.agent_url
                 || "http://omb.manotr.com";
  return _validateViaEndpoint(agentUrl, providerType, provider, apiKey, baseUrl);
}

/**
 * Persist current form values to user_settings so they survive the card re-render
 * triggered by a fetch/validate action. Called by every handler before updateCard().
 */
function _saveSettingsFormState(f) {
  var c = loadUserSettings();
  var merged = {
    mode:                     f.mode                     || c.mode,
    agent_url:                (f.agent_url                !== undefined) ? f.agent_url                : c.agent_url,
    llm_provider:             f.llm_provider             || c.llm_provider,
    llm_api_key:              (f.llm_api_key              !== undefined) ? f.llm_api_key              : c.llm_api_key,
    llm_model:                f.llm_model                || c.llm_model,
    llm_base_url:             (f.llm_base_url             !== undefined) ? f.llm_base_url             : c.llm_base_url,
    llm_ollama_api_key:       (f.llm_ollama_api_key       !== undefined) ? f.llm_ollama_api_key       : c.llm_ollama_api_key,
    embedding_provider:       f.embedding_provider       || c.embedding_provider,
    embedding_api_key:        (f.embedding_api_key        !== undefined) ? f.embedding_api_key        : c.embedding_api_key,
    embedding_model:          f.embedding_model          || c.embedding_model,
    embedding_base_url:       (f.embedding_base_url       !== undefined) ? f.embedding_base_url       : c.embedding_base_url,
    embedding_ollama_api_key: (f.embedding_ollama_api_key !== undefined) ? f.embedding_ollama_api_key : c.embedding_ollama_api_key,
    vector_provider:          f.vector_provider          || c.vector_provider,
    vector_url:               (f.vector_url               !== undefined) ? f.vector_url               : c.vector_url,
    vector_api_key:           (f.vector_api_key           !== undefined) ? f.vector_api_key           : c.vector_api_key,
    user_name:                (f.user_name                !== undefined) ? f.user_name                : c.user_name,
    user_position:            (f.user_position            !== undefined) ? f.user_position            : c.user_position,
    user_tone:                f.user_tone                || c.user_tone,
    system_prompt:            (f.system_prompt            !== undefined) ? f.system_prompt            : c.system_prompt
  };
  PropertiesService.getUserProperties().setProperty("user_settings", JSON.stringify(merged));
}

/**
 * "Validate API & Fetch Models" for cloud LLM providers (OpenAI / Anthropic / Groq).
 * Industry-standard: uses GET /v1/models — zero tokens, validates key + returns model list.
 */
function handleFetchLLMModels(e) {
  var f        = (e && e.formInput) ? e.formInput : {};
  _saveSettingsFormState(f);
  var provider = f.llm_provider || "openai";
  var apiKey   = (f.llm_api_key || "").trim();
  var up       = PropertiesService.getUserProperties();
  if (!apiKey) {
    up.setProperty("sett_llm_msg", "Enter your " + provider.toUpperCase() + " API key first.");
    up.setProperty("sett_llm_ok",  "false");
  } else {
    var result = _validateProviderViaAgent("llm", provider, apiKey, "");
    up.setProperty("sett_llm_msg", result.message || "");
    up.setProperty("sett_llm_ok",  result.valid ? "true" : "false");
    if (result.valid && result.models && result.models.length > 0) {
      up.setProperty("sett_llm_models_" + provider, JSON.stringify(result.models));
    }
  }
  return CardService.newActionResponseBuilder()
    .setNavigation(CardService.newNavigation().updateCard(_buildSettingsCard()))
    .build();
}

/**
 * "Connect & Fetch Ollama Models" for LLM.
 * Supports all 3 Ollama deployment cases:
 *   1. Local   — http://localhost:11434 (no auth)
 *   2. Remote  — any public URL via PageKite / ngrok
 *   3. Secured — public URL + Bearer token in api_key field
 */
function handleFetchLLMOllamaModels(e) {
  var f         = (e && e.formInput) ? e.formInput : {};
  _saveSettingsFormState(f);
  var ollamaUrl = (f.llm_base_url       || "http://localhost:11434").trim();
  var apiKey    = (f.llm_ollama_api_key  || "").trim();
  var up        = PropertiesService.getUserProperties();
  var result    = _validateProviderViaAgent("llm", "ollama", apiKey, ollamaUrl);
  up.setProperty("sett_llm_msg", result.message || "");
  up.setProperty("sett_llm_ok",  result.valid ? "true" : "false");
  if (result.valid && result.models && result.models.length > 0) {
    up.setProperty("sett_llm_models_ollama", JSON.stringify(result.models));
  }
  return CardService.newActionResponseBuilder()
    .setNavigation(CardService.newNavigation().updateCard(_buildSettingsCard()))
    .build();
}

/**
 * "Validate API & Fetch Models" for cloud embedding providers (OpenAI).
 * Uses GET /v1/models with embedding filter — zero tokens.
 */
function handleFetchEmbeddingModels(e) {
  var f        = (e && e.formInput) ? e.formInput : {};
  _saveSettingsFormState(f);
  var provider = f.embedding_provider || "openai";
  var apiKey   = (f.embedding_api_key || "").trim();
  var up       = PropertiesService.getUserProperties();
  if (!apiKey) {
    up.setProperty("sett_emb_msg", "Enter your " + provider.toUpperCase() + " API key first.");
    up.setProperty("sett_emb_ok",  "false");
  } else {
    var result = _validateProviderViaAgent("embedding", provider, apiKey, "");
    up.setProperty("sett_emb_msg", result.message || "");
    up.setProperty("sett_emb_ok",  result.valid ? "true" : "false");
    if (result.valid && result.models && result.models.length > 0) {
      up.setProperty("sett_emb_models_" + provider, JSON.stringify(result.models));
    }
  }
  return CardService.newActionResponseBuilder()
    .setNavigation(CardService.newNavigation().updateCard(_buildSettingsCard()))
    .build();
}

/**
 * "Connect & Fetch Ollama Models" for embedding.
 * Same 3-case Ollama support as handleFetchLLMOllamaModels.
 * Agent filters for embed-specific models (nomic, bge, mxbai, etc.).
 */
function handleFetchEmbeddingOllamaModels(e) {
  var f         = (e && e.formInput) ? e.formInput : {};
  _saveSettingsFormState(f);
  var ollamaUrl = (f.embedding_base_url        || "http://localhost:11434").trim();
  var apiKey    = (f.embedding_ollama_api_key   || "").trim();
  var up        = PropertiesService.getUserProperties();
  var result    = _validateProviderViaAgent("embedding", "ollama", apiKey, ollamaUrl);
  up.setProperty("sett_emb_msg", result.message || "");
  up.setProperty("sett_emb_ok",  result.valid ? "true" : "false");
  if (result.valid && result.models && result.models.length > 0) {
    up.setProperty("sett_emb_models_ollama", JSON.stringify(result.models));
  }
  return CardService.newActionResponseBuilder()
    .setNavigation(CardService.newNavigation().updateCard(_buildSettingsCard()))
    .build();
}

/**
 * showSettingsCard — delegates to _buildSettingsCard().
 * All settings card logic lives in _buildSettingsCard() above.
 */
function showSettingsCard(e) {
  return _buildSettingsCard();
}

// ============================================================================
// SETTINGS — PROVIDER DROPDOWN onChange HANDLERS
// Re-render the settings card immediately when the user switches provider,
// so the correct fields (API key / Ollama URL / model dropdown) appear at once.
// ============================================================================

/**
 * Fires when the LLM provider dropdown changes in Settings.
 * Saves the new provider to user_settings so _buildSettingsCard reads it,
 * then re-renders the card with the correct fields for the selected provider.
 */
function handleSettingsLLMProviderChange(e) {
  var f = (e && e.formInput) ? e.formInput : {};
  _saveSettingsFormState(f);
  return CardService.newActionResponseBuilder()
    .setNavigation(CardService.newNavigation().updateCard(_buildSettingsCard()))
    .build();
}

/**
 * Fires when the Embedding provider dropdown changes in Settings.
 */
function handleSettingsEmbProviderChange(e) {
  var f = (e && e.formInput) ? e.formInput : {};
  _saveSettingsFormState(f);
  return CardService.newActionResponseBuilder()
    .setNavigation(CardService.newNavigation().updateCard(_buildSettingsCard()))
    .build();
}

// ============================================================================
// ONBOARDING — PROVIDER DROPDOWN onChange HANDLERS
// Same pattern — re-render Step 1 card when provider changes.
// ============================================================================

/**
 * Fires when the LLM provider dropdown changes during Onboarding Step 1.
 */
function handleOBLLMProviderChange(e) {
  var f = (e && e.formInput) ? e.formInput : {};
  _saveOBFormState(f);
  return CardService.newActionResponseBuilder()
    .setNavigation(CardService.newNavigation().updateCard(_buildOnboardingStep1Card()))
    .build();
}

/**
 * Fires when the Embedding provider dropdown changes during Onboarding Step 1.
 */
function handleOBEmbProviderChange(e) {
  var f = (e && e.formInput) ? e.formInput : {};
  _saveOBFormState(f);
  return CardService.newActionResponseBuilder()
    .setNavigation(CardService.newNavigation().updateCard(_buildOnboardingStep1Card()))
    .build();
}



/**
 * Load user settings from UserProperties
 * Returns object with all settings fields
 */
function loadUserSettings() {
  var userProps = PropertiesService.getUserProperties();
  var settingsJson = userProps.getProperty("user_settings");
  
  if (settingsJson) {
    try {
      return JSON.parse(settingsJson);
    } catch (e) {
      Logger.log("Failed to parse settings: " + e.message);
    }
  }
  
  // Default settings
  return {
    mode: "manotr",
    agent_url: "http://omb.manotr.com",
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
}

/**
 * Save settings to UserProperties AND sync to backend
 */
function saveSettings(e) {
  var formInputs = e.formInput;
  // Load existing settings so that dropdown fields the user did NOT interact with
  // (which Apps Script omits from formInputs) keep their previously saved value
  // instead of being silently reset to the default.
  var current = loadUserSettings();
  
  var imapPassword = formInputs.imap_app_password !== undefined ? formInputs.imap_app_password : (current.imap_app_password || "");
  
  var settings = {
    mode: formInputs.mode || current.mode || "manotr",
    agent_url: formInputs.agent_url !== undefined ? formInputs.agent_url : (current.agent_url || "http://omb.manotr.com"),
    llm_provider: formInputs.llm_provider || current.llm_provider || "manotr",
    llm_api_key: formInputs.llm_api_key !== undefined ? formInputs.llm_api_key : (current.llm_api_key || ""),
    llm_model: formInputs.llm_model || current.llm_model || "gpt-4o-mini",
    llm_base_url: formInputs.llm_base_url !== undefined ? formInputs.llm_base_url : (current.llm_base_url || ""),
    llm_ollama_api_key: formInputs.llm_ollama_api_key !== undefined ? formInputs.llm_ollama_api_key : (current.llm_ollama_api_key || ""),
    embedding_provider: formInputs.embedding_provider || current.embedding_provider || "manotr",
    embedding_api_key: formInputs.embedding_api_key !== undefined ? formInputs.embedding_api_key : (current.embedding_api_key || ""),
    embedding_model: formInputs.embedding_model || current.embedding_model || "text-embedding-3-small",
    embedding_base_url: formInputs.embedding_base_url !== undefined ? formInputs.embedding_base_url : (current.embedding_base_url || ""),
    embedding_ollama_api_key: formInputs.embedding_ollama_api_key !== undefined ? formInputs.embedding_ollama_api_key : (current.embedding_ollama_api_key || ""),
    vector_provider: formInputs.vector_provider || current.vector_provider || "manotr",
    vector_url: formInputs.vector_url !== undefined ? formInputs.vector_url : (current.vector_url || ""),
    vector_api_key: formInputs.vector_api_key !== undefined ? formInputs.vector_api_key : (current.vector_api_key || ""),
    user_name: formInputs.user_name !== undefined ? formInputs.user_name : (current.user_name || ""),
    user_position: formInputs.user_position !== undefined ? formInputs.user_position : (current.user_position || ""),
    imap_app_password: imapPassword,
    run_imap_server: (imapPassword && imapPassword.trim() !== "") ? true : false,
    imap_email: Session.getEffectiveUser().getEmail(),
    user_tone: formInputs.user_tone || current.user_tone || "professional",
    system_prompt: formInputs.system_prompt !== undefined ? formInputs.system_prompt : (current.system_prompt || "")
  };

  // Normalise legacy mode values
  if (settings.mode === "inbuilt") settings.mode = "manotr";
  if (settings.mode === "custom")  settings.mode = "external";

  // Normalise legacy provider values
  var normProv = function(v) { return (v === "inbuilt") ? "manotr" : (v || "manotr"); };
  settings.llm_provider       = normProv(settings.llm_provider);
  settings.embedding_provider = normProv(settings.embedding_provider);
  settings.vector_provider    = normProv(settings.vector_provider);
  
  // Save to local UserProperties
  var userProps = PropertiesService.getUserProperties();
  userProps.setProperty("user_settings", JSON.stringify(settings));

  // Persist agent URL to Script Properties so all UrlFetchApp calls use it
  if (settings.agent_url) {
    PropertiesService.getScriptProperties().setProperty("FLASK_SERVER_URL", settings.agent_url);
  }

  // Sync to backend (best effort)
  try {
    syncSettingsToBackend(settings);
  } catch (syncErr) {
    Logger.log("Settings sync to backend failed: " + syncErr.message);
    // Continue - local save was successful
  }

  // Create/verify labels whenever settings are saved (ensures labels exist)
  Logger.log("🏷️  Creating/verifying OpenMailBot labels...");
  try {
    createOpenMailBotLabels();
    Logger.log("✅ Labels verified during settings save");
  } catch (labelErr) {
    Logger.log("⚠️  Label creation failed (non-fatal): " + labelErr.message);
  }

  // ── Activate email monitor trigger immediately on every save ──────────
  // Ensure both guard flags are set so monitorEmails() doesn't skip the cycle
  PropertiesService.getUserProperties().setProperty("onboarding_complete", "true");
  PropertiesService.getScriptProperties().setProperty("background_monitor_enabled", "true");
  var monitorStatus = "";
  try {
    setupEmailMonitor();  // force-deletes stale triggers + creates fresh 1-min trigger
    monitorStatus = "✅  Email monitor ACTIVE (every 1 min)";
    Logger.log("✅ Monitor trigger activated on settings save");
  } catch (monErr) {
    monitorStatus = "⚠️  Monitor trigger: " + monErr.message.substring(0, 80);
    Logger.log("⚠️ Monitor trigger error on save: " + monErr.message);
  }

  // Validate active providers — industry-standard: GET /v1/models or GET /api/tags — 0 tokens
  var validationLines = [];
  if (settings.llm_provider !== "manotr") {
    try {
      var llmApiKey  = (settings.llm_provider === "ollama") ? (settings.llm_ollama_api_key || "") : (settings.llm_api_key || "");
      var llmBaseUrl = (settings.llm_provider === "ollama") ? (settings.llm_base_url || "http://localhost:11434") : "";
      var llmCheck   = _validateProviderViaAgent("llm", settings.llm_provider, llmApiKey, llmBaseUrl);
      validationLines.push("🤖 " + settings.llm_provider.toUpperCase() + ": " +
        (llmCheck.valid ? "✅ " + llmCheck.message : "❌ " + llmCheck.message));
    } catch (ve) {
      validationLines.push("🤖 " + settings.llm_provider.toUpperCase() + ": ⚠️ " + ve.message.substring(0, 80));
    }
  }
  if (settings.embedding_provider !== "manotr") {
    try {
      var embApiKey  = (settings.embedding_provider === "ollama") ? (settings.embedding_ollama_api_key || "") : (settings.embedding_api_key || "");
      var embBaseUrl = (settings.embedding_provider === "ollama") ? (settings.embedding_base_url || "http://localhost:11434") : "";
      var embCheck   = _validateProviderViaAgent("embedding", settings.embedding_provider, embApiKey, embBaseUrl);
      validationLines.push("📊 " + settings.embedding_provider.toUpperCase() + " Embed: " +
        (embCheck.valid ? "✅ " + embCheck.message : "❌ " + embCheck.message));
    } catch (ve) {
      validationLines.push("📊 " + settings.embedding_provider.toUpperCase() + " Embed: ⚠️ " + ve.message.substring(0, 80));
    }
  }
  var validationText = validationLines.length > 0
    ? validationLines.join("\n")
    : "✨ Manotr mode — hosted service, no API key needed.";

  // Return confirmation card
  var savedLLM    = (settings.llm_provider       || "manotr").toUpperCase();
  var savedEmbed  = (settings.embedding_provider || "manotr").toUpperCase();
  var savedVector = (settings.vector_provider    || "manotr").toUpperCase();
  var savedMode   = (settings.mode               || "manotr").toUpperCase();

  return CardService.newCardBuilder()
    .setHeader(
      CardService.newCardHeader()
        .setTitle("✅  Settings Saved")
        .setSubtitle("Configuration is now active")
    )
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newDecoratedText()
            .setTopLabel("● SAVE COMPLETE")
            .setText("<b>Settings stored & providers verified</b>")
            .setBottomLabel(
              "Mode: " + savedMode +
              "  ·  🤖 " + savedLLM +
              "  ·  📊 " + savedEmbed +
              "  ·  🗄️ " + savedVector
            )
            .setWrapText(true)
        )
        .addWidget(
          CardService.newTextParagraph()
            .setText(validationText)
        )
    )
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newDecoratedText()
            .setTopLabel("● BACKGROUND MONITOR")
            .setText("<b>" + monitorStatus + "</b>")
            .setBottomLabel("Trigger installed — hourly sync")
            .setWrapText(true)
        )
    )
    .addSection(
      CardService.newCardSection()
        .setHeader("📚  EMAIL HISTORY INDEXING  (optional)")
        .addWidget(
          CardService.newTextParagraph()
            .setText(
              "Index past emails so the AI learns your projects, contacts, and style.\n\n" +
              "<b>This is optional</b> — the email monitor is already active for new emails. " +
              "You can skip now and start indexing later from Settings."
            )
        )
        .addWidget(
          CardService.newSelectionInput()
            .setType(CardService.SelectionInputType.RADIO_BUTTON)
            .setFieldName("index_months")
            .setTitle("How much history to index?")
            .addItem("🗓️  10 days  (fastest ~ 2-5 min)", "10d", false)
            .addItem("⚡  1 month  (quick ~ 5-10 min)", "1", false)
            .addItem("📅  3 months  (recommended ~ 20-40 min)", "3", true)
            .addItem("📁  6 months  (rich context ~ 45-90 min)", "6", false)
            .addItem("🗂️  12 months  (full year)", "12", false)
        )
        .addWidget(
          CardService.newButtonSet()
            .addButton(
              CardService.newTextButton()
                .setText("📚  Start Historical Indexing")
                .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
                .setBackgroundColor("#4285F4")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("startHistoricalIndexingFromSettings")
                )
            )
            .addButton(
              CardService.newTextButton()
                .setText("⏭️  Skip — Monitor Only")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("skipHistoricalIndexing")
                )
            )
        )
    )
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newButtonSet()
            .addButton(
              CardService.newTextButton()
                .setText("⚙️  Back to Settings")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("showSettingsCard")
                )
            )
            .addButton(
              CardService.newTextButton()
                .setText("🏠 Home")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("buildAddOn")
                )
            )
        )
    )
    .build();
}

/**
 * Launch historical email indexing from the settings save / activation flow
 */
function startHistoricalIndexingFromSettings(e) {
  var formInputs = e.formInput || {};
  var months = formInputs.index_months || "3";
  try {
    _launchBulkJobAsync(months);
    Logger.log("✅ Historical indexing launched: " + months);
  } catch (err) {
    Logger.log("❌ Historical indexing launch failed: " + err.message);
  }
  return CardService.newCardBuilder()
    .setHeader(
      CardService.newCardHeader()
        .setTitle("📚  Indexing Started")
        .setSubtitle("Processing email history in the background")
    )
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newDecoratedText()
            .setTopLabel("● INDEXING RUNNING")
            .setText("<b>Historical email processing has started!</b>")
            .setBottomLabel(
              "Indexing last " + (months === "10d" ? "10 days" : months + " months") + " of email history"
            )
            .setWrapText(true)
        )
        .addWidget(
          CardService.newTextParagraph()
            .setText(
              "⏱️  Processing runs securely in the background — you can use Gmail normally.\n\n" +
              "✅  All features work right now. AI accuracy improves as indexing completes.\n\n" +
              "📊  Check progress via Settings → Index Email History."
            )
        )
    )
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newButtonSet()
            .addButton(
              CardService.newTextButton()
                .setText("📊  View Progress")
                .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
                .setBackgroundColor("#4285F4")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("showBulkJobStatusCard")
                )
            )
            .addButton(
              CardService.newTextButton()
                .setText("🏠 Home")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("buildAddOn")
                )
            )
        )
    )
    .build();
}

/**
 * Skip historical indexing — monitor is already active, just confirm and go
 */
function skipHistoricalIndexing(e) {
  return CardService.newCardBuilder()
    .setHeader(
      CardService.newCardHeader()
        .setTitle("✅  Monitor Active")
        .setSubtitle("OpenMailBot is watching for new emails")
    )
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newDecoratedText()
            .setTopLabel("● ALL DONE")
            .setText("<b>Email monitor is running — skipping historical indexing.</b>")
            .setBottomLabel("Auto-process active")
            .setWrapText(true)
        )
        .addWidget(
          CardService.newTextParagraph()
            .setText(
              "You can start historical indexing anytime from:\n" +
              "⚙️  Settings → Index Email History\n\n" +
              "All features are active right now:\n" +
              "  • 📝  Summarize any email thread\n" +
              "  • 💬  Chat with your emails\n" +
              "  • 📎  Generate AI-powered draft replies"
            )
        )
    )
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newButtonSet()
            .addButton(
              CardService.newTextButton()
                .setText("🏠  Go to Home")
                .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
                .setBackgroundColor("#4285F4")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("buildAddOn")
                )
            )
            .addButton(
              CardService.newTextButton()
                .setText("⚙️  Settings")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("showSettingsCard")
                )
            )
        )
    )
    .build();
}

/**
 * Sync settings to the backend server
 * Backend is the authoritative source - local is a cache
 */
function syncSettingsToBackend(settings) {
  var flaskUrl = PropertiesService.getScriptProperties().getProperty("FLASK_SERVER_URL");
  if (!flaskUrl) {
    throw new Error("FLASK_SERVER_URL not configured in Script Properties");
  }
  
  var userId = Session.getEffectiveUser().getEmail();
  var baseUrl = flaskUrl.replace(/\/$/, '').replace(/\/api$/, '');
  var endpoint = baseUrl + '/api/settings';
  
  // ADD DEBUG LOGGING
  Logger.log("🔍 Syncing settings to: " + endpoint);
  Logger.log("🔍 User ID: " + userId);
  Logger.log("🔍 Settings: " + JSON.stringify(settings));
  
  var payload = {
    user_id: userId,
    settings: settings
  };
  
  var options = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };
  
  var resp = UrlFetchApp.fetch(endpoint, options);
  var code = resp.getResponseCode();
  
  // ADD DEBUG LOGGING
  Logger.log("🔍 Response code: " + code);
  Logger.log("🔍 Response body: " + resp.getContentText());
  
  if (code >= 400) {
    throw new Error("Backend returned error: " + code + " - " + resp.getContentText());
  }
  
  return JSON.parse(resp.getContentText());
}

/**
 * Fetch settings from backend (authoritative source)
 * Called on add-on load to ensure local cache is in sync
 */
function fetchSettingsFromBackend() {
  var backendUrl = PropertiesService.getScriptProperties().getProperty("BACKEND_URL");
  if (!backendUrl) {
    return null; // No backend configured, use local settings
  }
  
  var userId = Session.getEffectiveUser().getEmail();
  var endpoint = backendUrl.replace(/\/$/, '') + '/api/settings?user_id=' + encodeURIComponent(userId);
  
  try {
    var resp = UrlFetchApp.fetch(endpoint, {
      method: "get",
      muteHttpExceptions: true
    });
    
    var code = resp.getResponseCode();
    if (code === 200) {
      var data = JSON.parse(resp.getContentText());
      if (data.settings) {
        // Update local cache
        var userProps = PropertiesService.getUserProperties();
        userProps.setProperty("user_settings", JSON.stringify(data.settings));
        return data.settings;
      }
    }
  } catch (e) {
    Logger.log("Failed to fetch settings from backend: " + e.message);
  }
  
  return null;
}

/**
 * Reset settings to defaults
 */
/**
 * Re-run the onboarding wizard from scratch.
 * Clears onboarding_complete so buildAddOn will show step 1 again.
 * Also clears any lingering prefill/status state from a previous run.
 */
function resetOnboarding(e) {
  var userProps = PropertiesService.getUserProperties();
  userProps.deleteProperty("onboarding_complete");
  userProps.deleteProperty("onboarding_page1_done");
  userProps.deleteProperty("ob_prefill");
  userProps.deleteProperty("ob_status_msg");
  userProps.deleteProperty("ob_status_error");
  userProps.deleteProperty("ob_connect_msg");
  userProps.deleteProperty("ob_connect_ok");
  return _buildOnboardingStep1Card();
}

function resetSettings(e) {
  var userProps = PropertiesService.getUserProperties();
  userProps.deleteProperty("user_settings");

  return CardService.newCardBuilder()
    .setHeader(
      CardService.newCardHeader()
        .setTitle("🔄  Settings Reset")
        .setSubtitle("Defaults have been restored")
    )
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newDecoratedText()
            .setTopLabel("● RESET COMPLETE")
            .setText("<b>All settings cleared — Manotr Mode restored</b>")
            .setBottomLabel("Using default hosted services")
            .setWrapText(true)
        )
    )
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newButtonSet()
            .addButton(
              CardService.newTextButton()
                .setText("⚙️  Open Settings")
                .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
                .setBackgroundColor("#0F9D58")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("showSettingsCard")
                )
            )
            .addButton(
              CardService.newTextButton()
                .setText("🏠 Home")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("buildAddOn")
                )
            )
        )
    )
    .build();
}

/**
 * Get effective settings for API calls
 * Merges user settings with defaults, handles inbuilt mode
 */
function getEffectiveSettings() {
  // Try to sync from backend first
  var backendSettings = fetchSettingsFromBackend();
  
  // Load local settings (will use backend if sync was successful)
  var settings = loadUserSettings();
  
  // If mode is manotr (or legacy "inbuilt"), use hosted service defaults
  if (settings.mode === "manotr" || settings.mode === "inbuilt") {
    return {
      mode: "manotr",
      agent_url: settings.agent_url || "http://omb.manotr.com",
      llm_provider: "manotr",
      embedding_provider: "manotr",
      vector_provider: "manotr",
      user_name: settings.user_name,
      user_position: settings.user_position,
      user_tone: settings.user_tone,
      system_prompt: settings.system_prompt
    };
  }
  
  return settings;
}



/**
 * Get current domain and email filters from Script Properties
 * NOTE: These filters are ONLY applied in the background monitor script
 * Supports both full email addresses and domain names
 */
function getDomainFilters() {
  var scriptProps = PropertiesService.getScriptProperties();
  var filtersJson = scriptProps.getProperty("domain_filters");
  
  if (!filtersJson) {
    return [];
  }
  
  try {
    return JSON.parse(filtersJson);
  } catch (e) {
    Logger.log("Failed to parse domain filters: " + e.message);
    return [];
  }
}

/**
 * Save domain and email filters to Script Properties
 */
function saveDomainFilters(filters) {
  var scriptProps = PropertiesService.getScriptProperties();
  scriptProps.setProperty("domain_filters", JSON.stringify(filters));
}

/**
 * Check if an email address should be filtered
 * Returns true if the email should be EXCLUDED from background monitoring
 * @param {string} emailAddress - Full email address to check (e.g., "user@example.com")
 * @returns {boolean} - true if should be filtered out
 */
function shouldFilterEmail(emailAddress) {
  if (!emailAddress) return false;
  
  var filters = getDomainFilters();
  if (!filters || filters.length === 0) return false;
  
  emailAddress = emailAddress.toLowerCase().trim();
  
  // Extract email from "Name <email@domain.com>" format
  var emailMatch = emailAddress.match(/<(.+?)>/);
  if (emailMatch) {
    emailAddress = emailMatch[1].toLowerCase().trim();
  }
  
  // Check each filter
  for (var i = 0; i < filters.length; i++) {
    var filter = filters[i].toLowerCase().trim();
    
    if (!filter) continue;
    
    // Check if filter is a full email address (contains @)
    if (filter.indexOf('@') !== -1) {
      // Exact email match
      if (emailAddress === filter) {
        Logger.log("Email filtered (exact match): " + emailAddress + " matches " + filter);
        return true;
      }
    } else {
      // Domain-only filter - check if email ends with this domain
      var emailDomain = emailAddress.split('@')[1];
      if (emailDomain && emailDomain === filter) {
        Logger.log("Email filtered (domain match): " + emailAddress + " matches domain " + filter);
        return true;
      }
    }
  }
  
  return false;
}

/**
 * Check if any participant in a message should be filtered
 * Checks From, To, CC, BCC fields
 * @param {GmailMessage} message - Gmail message object
 * @returns {boolean} - true if message should be filtered out
 */
function shouldFilterMessage(message) {
  // Check From address
  if (shouldFilterEmail(message.getFrom())) {
    return true;
  }
  
  // Check To addresses
  var toAddresses = message.getTo().split(',');
  for (var i = 0; i < toAddresses.length; i++) {
    if (shouldFilterEmail(toAddresses[i])) {
      return true;
    }
  }
  
  // Check CC addresses
  var ccAddresses = message.getCc().split(',');
  for (var i = 0; i < ccAddresses.length; i++) {
    if (shouldFilterEmail(ccAddresses[i])) {
      return true;
    }
  }
  
  return false;
}
/**
 * Show Advanced Settings Card
 * - Background monitoring toggle (enable / disable)
 * - Email & Domain Filters section
 * NOTE: Historical email processing has been moved to showSettingsCard
 */
function showAdvancedSettingsCard(e) {
  var filters = JSON.parse(
    PropertiesService.getScriptProperties().getProperty("domain_filters") || "[]"
  );
  var filtersText  = filters.join('\n');
  var filterStatus = filters.length > 0
    ? filters.length + " active filter" + (filters.length !== 1 ? "s" : "")
    : "No filters configured";

  var bgEnabled = PropertiesService.getScriptProperties().getProperty("background_monitor_enabled") !== "false";
  var bgLabel   = bgEnabled ? "✅  Enabled" : "⏸️  Paused";

  var card = CardService.newCardBuilder()
    .setHeader(
      CardService.newCardHeader()
        .setTitle("🔒  Advanced Settings")
        .setSubtitle("Automation · Privacy Filters")
    );

  // ── Status Banner ──────────────────────────────────────────────────────
  card.addSection(
    CardService.newCardSection()
      .addWidget(
        CardService.newDecoratedText()
          .setTopLabel("● SYSTEM STATUS")
          .setText("<b>Background Monitor: " + bgLabel + "</b>")
          .setBottomLabel("🛡️ Privacy filters: " + filterStatus)
          .setWrapText(true)
      )
  );

  // ── Background Monitoring Toggle ───────────────────────────────────────
  card.addSection(
    CardService.newCardSection()
      .setHeader("🔄  BACKGROUND EMAIL MONITORING")
      .addWidget(
        CardService.newTextParagraph()
          .setText(
            "When <b>enabled</b>, OpenMailBot checks your inbox every hour to label and index new emails automatically.\n\n" +
            "When <b>disabled</b>, the monitor is paused. Manual Summarize / Chat / Draft still work normally."
          )
      )
      .addWidget(
        CardService.newDecoratedText()
          .setTopLabel("CURRENT STATUS")
          .setText("<b>" + bgLabel + "</b>")
          .setBottomLabel(bgEnabled
            ? "Monitor is active and processing new emails every hour"
            : "Monitor is paused — new emails are not being auto-indexed")
          .setWrapText(true)
      )
      .addWidget(
        CardService.newButtonSet()
          .addButton(
            CardService.newTextButton()
              .setText("✅  Enable Monitor")
              .setTextButtonStyle(bgEnabled ? CardService.TextButtonStyle.OUTLINED : CardService.TextButtonStyle.FILLED)
              .setBackgroundColor("#0F9D58")
              .setOnClickAction(
                CardService.newAction().setFunctionName("enableBackgroundMonitor")
              )
          )
          .addButton(
            CardService.newTextButton()
              .setText("⏸️  Pause Monitor")
              .setTextButtonStyle(bgEnabled ? CardService.TextButtonStyle.FILLED : CardService.TextButtonStyle.OUTLINED)
              .setBackgroundColor("#d93025")
              .setOnClickAction(
                CardService.newAction().setFunctionName("disableBackgroundMonitor")
              )
          )
      )
  );

  // ── Privacy Filters ────────────────────────────────────────────────────
  card.addSection(
    CardService.newCardSection()
      .setHeader("🛡️  EMAIL PRIVACY FILTERS")
      .addWidget(
        CardService.newDecoratedText()
          .setTopLabel("BACKGROUND MONITOR ONLY")
          .setText("<b>" + filterStatus + "</b>")
          .setBottomLabel("Filtered emails stay local")
          .setWrapText(true)
      )
      .addWidget(
        CardService.newTextParagraph()
          .setText(
            "<b>Supported formats:</b>\n" +
            "• Full address:  <b>user@example.com</b>\n" +
            "• Domain only:  <b>example.com</b>\n\n" +
            "⚠️ Saving <b>replaces</b> the entire filter list.\n" +
            "✅ Manual Summarize / Chat / Draft always bypass filters."
          )
      )
      .addWidget(
        CardService.newTextInput()
          .setFieldName("domain_filters")
          .setTitle("🚫  Emails & Domains to Block")
          .setValue(filtersText)
          .setMultiline(true)
          .setHint("One entry per line  ·  e.g.  no-reply@amazon.com  or  newsletter.com")
      )
  );

  // ── Active Filters List (collapsible) ─────────────────────────────────
  if (filters.length > 0) {
    card.addSection(
      CardService.newCardSection()
        .setHeader("📋  ACTIVE FILTERS  (" + filters.length + ")")
        .setCollapsible(true)
        .setNumUncollapsibleWidgets(0)
        .addWidget(
          CardService.newTextParagraph()
            .setText(filters.map(function(f) { return "🚫  " + f; }).join('\n'))
        )
    );
  } else {
    card.addSection(
      CardService.newCardSection()
        .setHeader("📋  ACTIVE FILTERS")
        .addWidget(
          CardService.newTextParagraph()
            .setText("<i>No filters configured. Add entries above and tap Save Filters.</i>")
        )
    );
  }

  // ── Action Bar ────────────────────────────────────────────────────────
  card.addSection(
    CardService.newCardSection()
      .addWidget(
        CardService.newTextButton()
          .setText("💾  Save Filters")
          .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
          .setBackgroundColor("#0F9D58")
          .setOnClickAction(
            CardService.newAction().setFunctionName("saveDomainFiltersFromUI")
          )
      )
      .addWidget(
        CardService.newButtonSet()
          .addButton(
            CardService.newTextButton()
              .setText("🧪 Test Filters")
              .setOnClickAction(
                CardService.newAction().setFunctionName("testDomainFilters")
              )
          )
          .addButton(
            CardService.newTextButton()
              .setText("◀  Settings")
              .setOnClickAction(
                CardService.newAction().setFunctionName("showSettingsCard")
              )
          )
          .addButton(
            CardService.newTextButton()
              .setText("🏠 Home")
              .setOnClickAction(
                CardService.newAction().setFunctionName("buildAddOn")
              )
          )
      )
  );

  return card.build();
}

/**
 * Enable background email monitoring
 */
function enableBackgroundMonitor(e) {
  PropertiesService.getScriptProperties().setProperty("background_monitor_enabled", "true");
  try { ensureMonitorRunning(); } catch (err) { Logger.log("enableBackgroundMonitor: " + err.message); }

  return CardService.newCardBuilder()
    .setHeader(
      CardService.newCardHeader()
        .setTitle("✅  Monitor Enabled")
        .setSubtitle("Background processing is now active")
    )
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newDecoratedText()
            .setTopLabel("● ACTIVE")
            .setText("<b>Background monitor is now running</b>")
            .setBottomLabel("Hourly indexing enabled")
            .setWrapText(true)
        )
    )
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newButtonSet()
            .addButton(
              CardService.newTextButton()
                .setText("◀  Advanced Settings")
                .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
                .setBackgroundColor("#5F6368")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("showAdvancedSettingsCard")
                )
            )
            .addButton(
              CardService.newTextButton()
                .setText("🏠 Home")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("buildAddOn")
                )
            )
        )
    )
    .build();
}

/**
 * Disable background email monitoring
 */
function disableBackgroundMonitor(e) {
  PropertiesService.getScriptProperties().setProperty("background_monitor_enabled", "false");

  return CardService.newCardBuilder()
    .setHeader(
      CardService.newCardHeader()
        .setTitle("⏸️  Monitor Paused")
        .setSubtitle("Background processing is now disabled")
    )
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newDecoratedText()
            .setTopLabel("● PAUSED")
            .setText("<b>Background monitor is now paused</b>")
            .setBottomLabel("Auto-indexing disabled")
            .setWrapText(true)
        )
    )
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newButtonSet()
            .addButton(
              CardService.newTextButton()
                .setText("◀  Advanced Settings")
                .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
                .setBackgroundColor("#5F6368")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("showAdvancedSettingsCard")
                )
            )
            .addButton(
              CardService.newTextButton()
                .setText("🏠 Home")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("buildAddOn")
                )
            )
        )
    )
    .build();
}


/**
 * Save the "process last N months" selection to ScriptProperties ONLY.
 * Does NOT trigger processing — user must tap Run Now separately.
 */
function saveProcessMonthsSetting(e) {
  var months = (e.formInput && e.formInput.process_last_n_months) || "3";
  var periodLabel = months === "10d" ? "10 days" : months + " month" + (months !== "1" ? "s" : "");

  // Save to ScriptProperties
  PropertiesService.getScriptProperties()
    .setProperty("process_last_n_months", months);

  return CardService.newCardBuilder()
    .setHeader(
      CardService.newCardHeader()
        .setTitle("💾  Selection Saved")
        .setSubtitle("Time window updated")
    )
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newDecoratedText()
            .setTopLabel("● SAVED")
            .setText("<b>Process window set to " + periodLabel + " back</b>")
            .setBottomLabel("Use Run Now to index")
            .setWrapText(true)
        )
    )
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newButtonSet()
            .addButton(
              CardService.newTextButton()
                .setText("▶  Run Now")
                .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
                .setBackgroundColor("#1a73e8")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("runProcessLastNMonths")
                )
            )
            .addButton(
              CardService.newTextButton()
                .setText("◀  Advanced")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("showAdvancedSettingsCard")
                )
            )
        )
    )
    .build();
}


/**
 * Run Now handler — launches processing ASYNCHRONOUSLY via a background trigger.
 * Returns a confirmation card immediately so the user can keep using the add-on.
 */
function runProcessLastNMonths(e) {
  // Guard: if a job is already running, redirect to status card
  if (PropertiesService.getScriptProperties().getProperty("bulk_job_state")) {
    return showBulkJobStatusCard(e);
  }

  // Prefer live dropdown value, fall back to last saved, then default to "3"
  var months = (e && e.formInput && e.formInput.process_last_n_months)
    || PropertiesService.getScriptProperties().getProperty("process_last_n_months")
    || "3";

  // Ensure the background trigger is active (needed for continuation)
  try { ensureMonitorRunning(); } catch (err) { Logger.log("runProcessLastNMonths: " + err.message); }

  // Launch entirely in the background — does NOT block the UI
  var state = _launchBulkJobAsync(months);
  var periodLabel = months === "10d" ? "10 days" : months + " month" + (months !== "1" ? "s" : "");

  // Return a confirmation card immediately
  return CardService.newCardBuilder()
    .setHeader(
      CardService.newCardHeader()
        .setTitle("🚀  Processing Started")
        .setSubtitle("Running in background — you can keep using the add-on")
    )
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newDecoratedText()
            .setTopLabel("● JOB LAUNCHED")
            .setText("<b>Last " + periodLabel + " of emails</b>")
            .setBottomLabel("Period: " + state.afterStr + "  →  " + state.beforeStr)
            .setWrapText(true)
        )
        .addWidget(
          CardService.newTextParagraph()
            .setText(
              "⏱️  First batch starts in <b>~1 hour</b>.\n" +
              "📦  Large inboxes continue automatically batch-by-batch.\n" +
              "✅  You can chat, summarise or draft emails right now — processing runs independently.\n\n" +
              "🛑  To stop early, tap <b>Cancel Job</b> below."
            )
        )
    )
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newButtonSet()
            .addButton(
              CardService.newTextButton()
                .setText("📊  Check Progress")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("showBulkJobStatusCard")
                )
            )
            .addButton(
              CardService.newTextButton()
                .setText("🛑  Stop Job")
                .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
                .setBackgroundColor("#d93025")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("cancelBulkJobFromUI")
                )
            )
            .addButton(
              CardService.newTextButton()
                .setText("⚙️  Settings")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("showSettingsCard")
                )
            )
        )
    )
    .build();
}

/**
 * Card showing live bulk-job progress — user can refresh or stop.
 */
function showBulkJobStatusCard(e) {
  var scriptProps = PropertiesService.getScriptProperties();
  var stateJson   = scriptProps.getProperty("bulk_job_state");
  var aborted     = scriptProps.getProperty("bulk_job_abort") === "true";
  var refreshedAt = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "HH:mm:ss");

  var card = CardService.newCardBuilder()
    .setHeader(
      CardService.newCardHeader()
        .setTitle("📊  Processing Status")
        .setSubtitle("Historical email indexing · Last refreshed: " + refreshedAt)
    );

  if (!stateJson) {
    card.addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newDecoratedText()
            .setTopLabel(aborted ? "● STOPPED" : "● NO JOB RUNNING")
            .setText(aborted
              ? "<b>Job was stopped by you</b>"
              : "<b>No indexing job is currently running</b>")
            .setBottomLabel(aborted
              ? "You can start a new job from Settings"
              : "Start a new job from Settings → Historical Email Processing")
            .setWrapText(true)
        )
    );
  } else {
    var state = JSON.parse(stateJson);
    var pct = state.stats.messagesFound > 0
      ? Math.round((state.stats.labeled + state.stats.skipped + state.stats.filtered) / state.stats.messagesFound * 100)
      : 0;

    card.addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newDecoratedText()
            .setTopLabel("● " + (state.status || "RUNNING").toUpperCase())
            .setText("<b>Last " + (state.nLabel || state.n + " months") + "</b>  ·  " + state.afterStr + " → " + state.beforeStr)
            .setBottomLabel(
              "Threads scanned: " + state.stats.threadsScanned +
              "  ·  Messages found: " + state.stats.messagesFound +
              "  ·  Offset: " + state.offset
            )
            .setWrapText(true)
        )
        .addWidget(
          CardService.newTextParagraph()
            .setText(
              "✅  Labeled   : " + state.stats.labeled + "\n" +
              "⊘   Skipped   : " + state.stats.skipped + "\n" +
              "🚫  Filtered  : " + state.stats.filtered + "\n" +
              "❌  Errors    : " + state.stats.errors + "\n\n" +
              "⏳  Processing continues in background — batches run every ~1 hour."
            )
        )
    );
  }

  card.addSection(
    CardService.newCardSection()
      .addWidget(
        CardService.newButtonSet()
          .addButton(
            CardService.newTextButton()
              .setText("🔄  Refresh")
              .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
              .setBackgroundColor("#1a73e8")
              .setOnClickAction(
                CardService.newAction().setFunctionName("showBulkJobStatusCard")
              )
          )
          .addButton(
            CardService.newTextButton()
              .setText("🛑  Stop Job")
              .setOnClickAction(
                CardService.newAction().setFunctionName("cancelBulkJobFromUI")
              )
          )
          .addButton(
            CardService.newTextButton()
              .setText("◀  Settings")
              .setOnClickAction(
                CardService.newAction().setFunctionName("showSettingsCard")
              )
          )
      )
  );

  return card.build();
}

/**
 * Show a confirmation card before actually stopping the job.
 */
function cancelBulkJobFromUI(e) {
  var stateJson = PropertiesService.getScriptProperties().getProperty("bulk_job_state");

  if (!stateJson) {
    // Nothing running — go straight to status card
    return showBulkJobStatusCard(e);
  }

  var state = JSON.parse(stateJson);

  return CardService.newCardBuilder()
    .setHeader(
      CardService.newCardHeader()
        .setTitle("⚠️  Stop Indexing Job?")
        .setSubtitle("Confirm before stopping")
    )
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newDecoratedText()
            .setTopLabel("● CONFIRMATION REQUIRED")
            .setText("<b>Are you sure you want to stop the running job?</b>")
            .setBottomLabel(
              "Job: last " + state.n + " months  ·  " +
              "Labeled so far: " + state.stats.labeled +
              "  ·  Offset: " + state.offset
            )
            .setWrapText(true)
        )
        .addWidget(
          CardService.newTextParagraph()
            .setText(
              "ℹ️  Emails already indexed will remain available.\n" +
              "You can re-run indexing anytime from Settings."
            )
        )
    )
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newButtonSet()
            .addButton(
              CardService.newTextButton()
                .setText("🛑  Yes, Stop Job")
                .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
                .setBackgroundColor("#d93025")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("confirmStopBulkJob")
                )
            )
            .addButton(
              CardService.newTextButton()
                .setText("← Keep Running")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("showBulkJobStatusCard")
                )
            )
        )
    )
    .build();
}

/**
 * Actually stop the bulk job after user confirms.
 */
function confirmStopBulkJob(e) {
  cancelBulkJob(); // defined in BackgroundEmailMonitor.gs

  return CardService.newCardBuilder()
    .setHeader(
      CardService.newCardHeader()
        .setTitle("🛑  Job Stopped")
        .setSubtitle("Background indexing has been stopped")
    )
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newDecoratedText()
            .setTopLabel("● STOPPED")
            .setText("<b>The indexing job has been stopped successfully.</b>")
            .setBottomLabel("Indexed emails stay available")
            .setWrapText(true)
        )
        .addWidget(
          CardService.newTextParagraph()
            .setText(
              "✅  All previously indexed emails are still fully searchable.\n" +
              "📅  To index more emails, go to Settings → Historical Email Processing."
            )
        )
    )
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newButtonSet()
            .addButton(
              CardService.newTextButton()
                .setText("⚙️  Settings")
                .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
                .setBackgroundColor("#5F6368")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("showSettingsCard")
                )
            )
            .addButton(
              CardService.newTextButton()
                .setText("🏠  Home")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("buildAddOn")
                )
            )
        )
    )
    .build();
}

function saveDomainFiltersFromUI(e) {
  var input = e.formInput.domain_filters || "";

  // Split by line
  var lines = input.split('\n');

  var filters = [];

  for (var i = 0; i < lines.length; i++) {
    var line = lines[i].trim().toLowerCase();

    if (!line) continue; // skip empty lines

    // Normalize
    if (line.indexOf('@') === 0) {
      line = line.substring(1);
    }

    filters.push(line);
  }

  // Remove duplicates
  var uniqueFilters = [];
  for (var i = 0; i < filters.length; i++) {
    if (uniqueFilters.indexOf(filters[i]) === -1) {
      uniqueFilters.push(filters[i]);
    }
  }

  // OVERWRITE (Option A behavior)
  saveDomainFilters(uniqueFilters);

  return CardService.newCardBuilder()
    .setHeader(
      CardService.newCardHeader()
        .setTitle("🛡️  Filters Saved")
        .setSubtitle("Privacy rules updated")
    )
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newDecoratedText()
            .setTopLabel("● SAVED")
            .setText("<b>" + uniqueFilters.length + " filter" + (uniqueFilters.length !== 1 ? "s" : "") + " active</b>")
            .setBottomLabel("Filter enabled")
            .setWrapText(true)
        )
        .addWidget(
          uniqueFilters.length > 0
            ? CardService.newTextParagraph().setText(
                uniqueFilters.map(function(f) { return "🚫  " + f; }).join('\n')
              )
            : CardService.newTextParagraph().setText("<i>No active filters — all emails will be processed</i>")
        )
    )
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newButtonSet()
            .addButton(
              CardService.newTextButton()
                .setText("🧪 Test Filters")
                .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
                .setBackgroundColor("#1a73e8")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("testDomainFilters")
                )
            )
            .addButton(
              CardService.newTextButton()
                .setText("◀  Advanced")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("showAdvancedSettingsCard")
                )
            )
        )
    )
    .build();
}


/**
 * Test domain filters with current inbox
 * Shows which emails would be filtered
 */
function testDomainFilters(e) {
  try {
    var filters = getDomainFilters();
    
    if (!filters || filters.length === 0) {
      return CardService.newCardBuilder()
        .setHeader(
          CardService.newCardHeader()
            .setTitle("🧪  Filter Test")
            .setSubtitle("No filters to test")
        )
        .addSection(
          CardService.newCardSection()
            .addWidget(
              CardService.newDecoratedText()
                .setTopLabel("⚠️ NOTICE")
                .setText("<b>No filters configured yet</b>")
                .setBottomLabel("Configure in Advanced Settings")
                .setWrapText(true)
            )
            .addWidget(
              CardService.newTextButton()
                .setText("◀  Back to Advanced")
                .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
                .setBackgroundColor("#5F6368")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("showAdvancedSettingsCard")
                )
            )
        )
        .build();
    }
    
    // Get recent threads to test
    var threads = GmailApp.getInboxThreads(0, 20);
    var filteredCount = 0;
    var allowedCount = 0;
    var examples = [];
    
    for (var i = 0; i < threads.length; i++) {
      var messages = threads[i].getMessages();
      var threadFiltered = false;
      
      for (var j = 0; j < messages.length; j++) {
        if (shouldFilterMessage(messages[j])) {
          threadFiltered = true;
          if (examples.length < 5) {
            examples.push("🚫 " + messages[j].getSubject().substring(0, 50) + 
                         " (From: " + messages[j].getFrom() + ")");
          }
          break;
        }
      }
      
      if (threadFiltered) {
        filteredCount++;
      } else {
        allowedCount++;
      }
    }
    
    var resultText;
    if (examples.length > 0) {
      resultText = "<b>Example blocked emails:</b>\n" + examples.join('\n');
    } else {
      resultText = "No emails in the last 20 inbox threads matched your filters.";
    }
    
    return CardService.newCardBuilder()
      .setHeader(
        CardService.newCardHeader()
          .setTitle("🧪  Filter Test Results")
          .setSubtitle("Checked " + threads.length + " recent inbox threads")
      )
      .addSection(
        CardService.newCardSection()
          .addWidget(
            CardService.newDecoratedText()
              .setTopLabel("● TEST COMPLETE")
              .setText(
                "<b>✅ Allowed: " + allowedCount + "   🚫 Blocked: " + filteredCount + "</b>"
              )
              .setBottomLabel(
                "Filters active: " + filters.length +
                "  ·  Threads scanned: " + threads.length
              )
              .setWrapText(true)
          )
          .addWidget(
            CardService.newTextParagraph().setText(resultText)
          )
      )
      .addSection(
        CardService.newCardSection()
          .addWidget(
            CardService.newButtonSet()
              .addButton(
                CardService.newTextButton()
                  .setText("🛡️  Edit Filters")
                  .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
                  .setBackgroundColor("#0F9D58")
                  .setOnClickAction(
                    CardService.newAction().setFunctionName("showAdvancedSettingsCard")
                  )
              )
              .addButton(
                CardService.newTextButton()
                  .setText("🏠 Home")
                  .setOnClickAction(
                    CardService.newAction().setFunctionName("buildAddOn")
                  )
              )
          )
      )
      .build();

  } catch (error) {
    return CardService.newCardBuilder()
      .setHeader(
        CardService.newCardHeader()
          .setTitle("❌  Test Failed")
          .setSubtitle("An error occurred")
      )
      .addSection(
        CardService.newCardSection()
          .addWidget(
            CardService.newDecoratedText()
              .setTopLabel("ERROR")
              .setText("<b>Could not complete filter test</b>")
              .setBottomLabel(error.message)
              .setWrapText(true)
          )
          .addWidget(
            CardService.newTextButton()
              .setText("◀  Back to Advanced")
              .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
              .setBackgroundColor("#5F6368")
              .setOnClickAction(
                CardService.newAction().setFunctionName("showAdvancedSettingsCard")
              )
          )
      )
      .build();
  }
}

// ============================================================================
// DEBUG & RESET HANDLERS
// ============================================================================

/**
 * Clear all processed message tracking to force re-run of background monitor.
 * Useful when previous runs failed or when you want to reprocess all emails.
 */
function handleClearProcessedMessages(e) {
  try {
    var scriptProps = PropertiesService.getScriptProperties();
    
    // Clear processed messages tracking
    scriptProps.deleteProperty("processed_message_ids");
    scriptProps.deleteProperty("last_email_check_time");
    
    Logger.log("✅ Cleared all processed message tracking");
    
    return CardService.newCardBuilder()
      .setHeader(
        CardService.newCardHeader()
          .setTitle("✅  Reset Complete")
          .setSubtitle("Processed messages tracking cleared")
      )
      .addSection(
        CardService.newCardSection()
          .addWidget(
            CardService.newDecoratedText()
              .setTopLabel("● SUCCESS")
              .setText("<b>All processed message tracking has been cleared</b>")
              .setBottomLabel("Will re-process on next run")
              .setWrapText(true)
          )
          .addWidget(
            CardService.newTextParagraph()
              .setText(
                "✅  Processed messages list: <b>CLEARED</b>\n" +
                "✅  Last check timestamp: <b>RESET</b>\n\n" +
                "ℹ️  The next monitor run (every hour) will process all emails again."
              )
          )
      )
      .addSection(
        CardService.newCardSection()
          .addWidget(
            CardService.newButtonSet()
              .addButton(
                CardService.newTextButton()
                  .setText("⚙️  Back to Settings")
                  .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
                  .setBackgroundColor("#5F6368")
                  .setOnClickAction(
                    CardService.newAction().setFunctionName("showSettingsCard")
                  )
              )
              .addButton(
                CardService.newTextButton()
                  .setText("🏠  Home")
                  .setOnClickAction(
                    CardService.newAction().setFunctionName("buildAddOn")
                  )
              )
          )
      )
      .build();
      
  } catch (error) {
    Logger.log("❌ Error clearing processed messages: " + error.message);
    return showError("Failed to clear processed messages:\n\n" + error.message);
  }
}

/**
 * Show current trigger status and debug information
 */
function handleViewTriggerStatus(e) {
  try {
    var triggers = ScriptApp.getProjectTriggers();
    var monitorTrigger = null;
    var allTriggers = [];
    
    for (var i = 0; i < triggers.length; i++) {
      var t = triggers[i];
      allTriggers.push({
        func: t.getHandlerFunction(),
        type: t.getTriggerSource().toString(),
        id: t.getUniqueId()
      });
      
      if (t.getHandlerFunction() === 'monitorEmails') {
        monitorTrigger = t;
      }
    }
    
    var scriptProps = PropertiesService.getScriptProperties();
    var userProps = PropertiesService.getUserProperties();
    
    var lastCheck = scriptProps.getProperty("last_email_check_time") || "Never";
    var bgEnabled = scriptProps.getProperty("background_monitor_enabled");
    var onboardingComplete = userProps.getProperty("onboarding_complete") === "true";
    var processedCount = 0;
    
    try {
      var processedJson = scriptProps.getProperty("processed_message_ids");
      if (processedJson) {
        processedCount = JSON.parse(processedJson).length;
      }
    } catch (pe) {}
    
    var statusText = "";
    statusText += "🔧  <b>Trigger Status</b>\n\n";
    
    if (monitorTrigger) {
      statusText += "✅  <b>Monitor trigger: ACTIVE</b>\n";
      statusText += "    Function: monitorEmails\n";
      statusText += "    ID: " + monitorTrigger.getUniqueId().substring(0, 20) + "...\n\n";
    } else {
      statusText += "❌  <b>Monitor trigger: NOT FOUND</b>\n";
      statusText += "    The background monitor trigger is not installed.\n\n";
    }
    
    statusText += "📊  <b>Status Details</b>\n";
    statusText += "    Onboarding complete: " + (onboardingComplete ? "✅ Yes" : "❌ No") + "\n";
    statusText += "    Background enabled: " + (bgEnabled === "false" ? "❌ Disabled" : "✅ Enabled") + "\n";
    statusText += "    Last check: " + (lastCheck === "Never" ? "Never" : new Date(lastCheck).toLocaleString()) + "\n";
    statusText += "    Processed messages: " + processedCount + "\n\n";
    
    statusText += "🔍  <b>All Triggers (" + allTriggers.length + ")</b>\n";
    for (var i = 0; i < allTriggers.length && i < 5; i++) {
      statusText += "    • " + allTriggers[i].func + " (" + allTriggers[i].type + ")\n";
    }
    if (allTriggers.length > 5) {
      statusText += "    ... and " + (allTriggers.length - 5) + " more\n";
    }
    
    var card = CardService.newCardBuilder()
      .setHeader(
        CardService.newCardHeader()
          .setTitle("🔍  Trigger Status")
          .setSubtitle("Background monitor debug info")
      )
      .addSection(
        CardService.newCardSection()
          .addWidget(
            CardService.newTextParagraph().setText(statusText)
          )
      );
    
    // Add action button based on status
    if (!monitorTrigger && onboardingComplete) {
      card.addSection(
        CardService.newCardSection()
          .addWidget(
            CardService.newTextButton()
              .setText("🔧  Install Monitor Trigger")
              .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
              .setBackgroundColor("#EA4335")
              .setOnClickAction(
                CardService.newAction().setFunctionName("handleInstallMonitorTrigger")
              )
          )
      );
    }
    
    card.addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newButtonSet()
            .addButton(
              CardService.newTextButton()
                .setText("🔄  Refresh")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("handleViewTriggerStatus")
                )
            )
            .addButton(
              CardService.newTextButton()
                .setText("◀  Back")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("showSettingsCard")
                )
            )
        )
    );
    
    return card.build();
    
  } catch (error) {
    Logger.log("❌ Error viewing trigger status: " + error.message);
    return showError("Failed to view trigger status:\n\n" + error.message);
  }
}

/**
 * Manually install the monitor trigger (if missing)
 */
function handleInstallMonitorTrigger(e) {
  try {
    // Use setupEmailMonitor() (force-reinstall) not ensureMonitorRunning() (skips if exists)
    setupEmailMonitor();
    
    return CardService.newCardBuilder()
      .setHeader(
        CardService.newCardHeader()
          .setTitle("✅  Trigger Installed")
          .setSubtitle("Background monitor is now active")
      )
      .addSection(
        CardService.newCardSection()
          .addWidget(
            CardService.newDecoratedText()
              .setTopLabel("● SUCCESS")
              .setText("<b>The monitor trigger has been installed successfully</b>")
              .setBottomLabel("Hourly processing enabled")
              .setWrapText(true)
          )
      )
      .addSection(
        CardService.newCardSection()
          .addWidget(
            CardService.newButtonSet()
              .addButton(
                CardService.newTextButton()
                  .setText("📋  View Status")
                  .setOnClickAction(
                    CardService.newAction().setFunctionName("handleViewTriggerStatus")
                  )
              )
              .addButton(
                CardService.newTextButton()
                  .setText("⚙️  Settings")
                  .setOnClickAction(
                    CardService.newAction().setFunctionName("showSettingsCard")
                  )
              )
          )
      )
      .build();
      
  } catch (error) {
    Logger.log("❌ Error installing trigger: " + error.message);
    return showError("Failed to install monitor trigger:\n\n" + error.message);
  }
}

// ============================================================================
// SELF-CHAINING EXECUTION MODEL — 5-minute repeating triggers
// ============================================================================

/**
 * Main function to process emails and manage its own schedule.
 * 
 * This implements a "self-chaining" execution model that:
 * 1. Tracks last check timestamp to process only new emails
 * 2. Prevents duplicate processing by tracking message IDs
 * 3. Monitors execution time to avoid hitting Google's 6-minute limit
 * 4. Self-destructs the old trigger and re-creates a new one for 5 minutes later
 * 
 * On first run: Initializes tracking without processing existing emails.
 * On subsequent runs: Only processes emails that arrived after the last check.
 * 
 * This bypasses the "1 hour" trigger limitation and ensures execution every 5 minutes
 * without timeout issues.
 * 
 * To start: Run this function manually once. After that, it will trigger itself
 * automatically every 5 minutes indefinitely.
 */
function processEmailsAndSchedule() {
  var START_TIME = new Date().getTime();
  var MAX_EXECUTION_TIME = 5 * 60 * 1000;
  var CURRENT_TIMESTAMP = new Date();
  
  Logger.log("[START] processEmailsAndSchedule started at " + CURRENT_TIMESTAMP.toISOString());
  
  deleteExistingTriggers('processEmailsAndSchedule');
  Logger.log("[CLEAN] Old triggers cleaned up");

  var userProps = PropertiesService.getUserProperties();
  var lastCheckTimestampStr = userProps.getProperty("last_email_check_timestamp");
  var isFirstRun = !lastCheckTimestampStr;
  
  var lastCheckTimestamp = new Date(0);
  if (lastCheckTimestampStr) {
    lastCheckTimestamp = new Date(lastCheckTimestampStr);
    Logger.log("[TIME] Last check was at: " + lastCheckTimestamp.toISOString());
  } else {
    Logger.log("[INFO] First run - initializing timestamp");
  }

  if (!isFirstRun) {
    var processedMessageIds = getProcessedMessageIds();
    var lastCheckMs = lastCheckTimestamp.getTime();
    var currentMs = CURRENT_TIMESTAMP.getTime();
    var timeDiffSeconds = Math.floor((currentMs - lastCheckMs) / 1000);
    
    var searchQuery = 'is:unread';
    if (timeDiffSeconds > 0) {
      var daysDiff = Math.ceil(timeDiffSeconds / 86400);
      if (daysDiff > 0) {
        searchQuery += ' newer_than:' + daysDiff + 'd';
        Logger.log("[SEARCH] Query: " + searchQuery);
      }
    }

    var newEmailsFound = 0;
    var duplicatesSkipped = 0;
    
    try {
      var threads = GmailApp.search(searchQuery);
      Logger.log("[EMAIL] Found " + threads.length + " threads");
      
      for (var i = 0; i < threads.length; i++) {
        var currentTime = new Date().getTime();
        var elapsed = currentTime - START_TIME;
        
        if (elapsed > MAX_EXECUTION_TIME) {
          Logger.warn("[TIMEOUT] Time limit reached. Stopping.");
          break; 
        }

        var messages = threads[i].getMessages();
        var latestMessage = messages[messages.length - 1];
        var messageId = latestMessage.getId();
        var messageDate = latestMessage.getDate();
        
        if (processedMessageIds.indexOf(messageId) > -1) {
          Logger.log("[SKIP] Duplicate: " + messageId);
          duplicatesSkipped++;
          continue;
        }
        
        if (messageDate.getTime() <= lastCheckMs) {
          Logger.log("[SKIP] Old message: " + latestMessage.getSubject());
          continue;
        }
        
        Logger.log("[NEW] Email: " + latestMessage.getSubject());
        labelNewEmail(latestMessage, threads[i]);
        
        addProcessedMessageId(messageId);
        newEmailsFound++;
        
        threads[i].markRead();
      }
      
      Logger.log("[SUMMARY] Processed: " + newEmailsFound + ", Skipped: " + duplicatesSkipped);
      
    } catch (error) {
      Logger.error("[ERROR] Processing failed: " + error.message);
    }
  } else {
    Logger.log("[SKIP] First run - no processing");
  }

  try {
    userProps.setProperty("last_email_check_timestamp", CURRENT_TIMESTAMP.toISOString());
    Logger.log("[OK] Timestamp updated");
  } catch (error) {
    Logger.error("[ERROR] Timestamp update failed: " + error.message);
  }

  try {
    ScriptApp.newTrigger('processEmailsAndSchedule')
      .timeBased()
      .after(5 * 60 * 1000) 
      .create();
    
    Logger.log("[OK] Next trigger scheduled");
  } catch (triggerError) {
    Logger.error("[ERROR] Trigger scheduling failed: " + triggerError.message);
  }
}

/**
 * Background trigger - runs automatically every 1 minute.
 * Sends the LATEST email to the server without requiring any user interaction.
 * This is the main auto-sync function that works WITHOUT clicking the add-on.
 */
function autoSyncLatestEmailToServer() {
  console.log("[AUTO-SYNC-BG] ========== Background Auto-Sync START ==========");
  Logger.log("[AUTO-SYNC-BG] Background Auto-Sync started at: " + new Date().toISOString());
  
  try {
    // Check if onboarding is complete
    if (PropertiesService.getUserProperties().getProperty("onboarding_complete") !== "true") {
      Logger.log("[AUTO-SYNC-BG] Onboarding not complete - skipping");
      return;
    }
    
    var userProps = PropertiesService.getUserProperties();
    var lastSyncStr = userProps.getProperty("last_auto_sync_timestamp");
    var now = new Date().getTime();
    
    Logger.log("[AUTO-SYNC-BG] Last background sync: " + (lastSyncStr || "never"));
    
    // Only sync if > 1 minute has passed (to avoid duplicate sends if trigger fires rapidly)
    if (lastSyncStr) {
      var timeSinceLastSync = now - new Date(lastSyncStr).getTime();
      if (timeSinceLastSync < 60 * 1000) { // Less than 1 minute
        Logger.log("[AUTO-SYNC-BG] Skipped - too soon since last sync (" + Math.floor(timeSinceLastSync / 1000) + "s ago)");
        return;
      }
    }
    
    // Send the LATEST 1 email to the server
    Logger.log("[AUTO-SYNC-BG] Calling syncLatestEmailsToBackend(1)...");
    var result = syncLatestEmailsToBackend(1);
    
    Logger.log("[AUTO-SYNC-BG] Result: " + JSON.stringify(result));
    console.log("[AUTO-SYNC-BG] Result: " + JSON.stringify(result));
    
    // Update last sync timestamp
    userProps.setProperty("last_auto_sync_timestamp", new Date(now).toISOString());
    
    Logger.log("[AUTO-SYNC-BG] ========== Background Auto-Sync END ==========");
    
  } catch (error) {
    console.error("[AUTO-SYNC-BG] ❌ Error: " + error.message);
    console.error("[AUTO-SYNC-BG] Stack: " + error.stack);
    Logger.log("[AUTO-SYNC-BG] ❌ Error: " + error.message);
    Logger.log("[AUTO-SYNC-BG] Stack: " + error.stack);
  }
}

/**
 * Ensure the auto-sync background trigger is installed.
 * This trigger runs every 1 minute and sends the latest email to the server.
 * No user interaction required - works completely in the background.
 */
function ensureAutoSyncTriggerRunning() {
  Logger.log("🔍 ensureAutoSyncTriggerRunning: checking trigger setup...");
  
  // Do not start the trigger before onboarding is complete
  if (PropertiesService.getUserProperties().getProperty("onboarding_complete") !== "true") {
    Logger.log("⏸️  ensureAutoSyncTriggerRunning: onboarding not complete — trigger installation skipped.");
    return;
  }

  var triggers = ScriptApp.getProjectTriggers();
  
  for (var i = 0; i < triggers.length; i++) {
    if (triggers[i].getHandlerFunction() === 'autoSyncLatestEmailToServer') {
      Logger.log("✅ autoSyncLatestEmailToServer trigger already exists — skipping creation");
      return; // already installed
    }
  }
  
  // Not found — create it
  Logger.log("🔧 Creating autoSyncLatestEmailToServer trigger (every 1 minute)...");
  try {
    ScriptApp.newTrigger('autoSyncLatestEmailToServer')
      .timeBased()
      .everyMinutes(1)
      .create();
    Logger.log("✅ autoSyncLatestEmailToServer trigger installed successfully!");
  } catch (triggerErr) {
    Logger.log("❌ Failed to create auto-sync trigger: " + triggerErr.message);
    throw triggerErr;
  }
}

/**
 * Gets the backend/agent server URL from properties (multiple sources).
 * Checks in order: ScriptProperties.FLASK_SERVER_URL, user_settings.agent_url, agent_server_url
 * @returns {string|null} The backend URL or null if not configured
 */
function getBackendUrl() {
  // 1. Check ScriptProperties (set by onboarding)
  var scriptUrl = PropertiesService.getScriptProperties().getProperty("FLASK_SERVER_URL");
  if (scriptUrl && scriptUrl.trim() !== "") {
    return scriptUrl.trim();
  }
  
  // 2. Check user_settings JSON (fallback)
  var userSettingsJson = PropertiesService.getUserProperties().getProperty("user_settings");
  if (userSettingsJson) {
    try {
      var userSettings = JSON.parse(userSettingsJson);
      if (userSettings.agent_url && userSettings.agent_url.trim() !== "") {
        return userSettings.agent_url.trim();
      }
    } catch (parseErr) {
      Logger.log("[WARN] Failed to parse user_settings: " + parseErr.message);
    }
  }
  
  // 3. Check legacy agent_server_url (fallback)
  var legacyUrl = PropertiesService.getUserProperties().getProperty("agent_server_url");
  if (legacyUrl && legacyUrl.trim() !== "") {
    return legacyUrl.trim();
  }
  
  return null;
}

/**
 * Sends email data to your backend endpoint.
 * 
 * This function extracts key metadata from a Gmail message and sends it
 * to your configured backend API endpoint.
 * 
 * @param {GmailMessage} message - The Gmail message to send
 */
function sendToBackend(message) {
  try {
    var backendUrl = getBackendUrl();
    
    if (!backendUrl) {
      Logger.warn("[WARN] Backend URL not configured");
      return;
    }

    var payload = {
      subject: message.getSubject(),
      body: message.getPlainBody(),
      from: message.getFrom(),
      to: message.getTo(),
      date: message.getDate(),
      threadId: message.getThread().getId(),
      messageId: message.getId()
    };
    
    var options = {
      method: 'post',
      contentType: 'application/json',
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    };
    
    var response = UrlFetchApp.fetch(backendUrl, options);
    var responseCode = response.getResponseCode();
    
    if (responseCode >= 200 && responseCode < 300) {
      Logger.log("[OK] Backend response: " + responseCode);
    } else {
      Logger.warn("[WARN] Backend returned status " + responseCode);
    }
    
  } catch (error) {
    Logger.error("ERROR sending to backend: " + error.message);
  }
}

/**
 * Labels a new email found by the scheduler.
 * 
 * This function is called when a new email is detected after the last check timestamp.
 * It sends the email to your backend for labeling via the async API endpoint.
 * 
 * @param {GmailMessage} message - The new Gmail message
 * @param {GmailThread} thread - The Gmail thread containing the message
 */
function labelNewEmail(message, thread) {
  try {
    Logger.log("[LABEL] Labeling: " + message.getSubject());
    
    var backendUrl = getBackendUrl();
    if (!backendUrl) {
      Logger.warn("[WARN] Backend URL not configured");
      return;
    }
    
    var userEmail = Session.getActiveUser().getEmail();
    var accessToken = ScriptApp.getOAuthToken();
    var gmailThreadId = thread.getId();
    
    var allMessages = thread.getMessages();
    var formattedMessages = [];
    
    for (var i = 0; i < allMessages.length; i++) {
      var msg = allMessages[i];
      formattedMessages.push({
        message_id: msg.getId(),
        from_address: msg.getFrom(),
        to: msg.getTo().split(','),
        subject: msg.getSubject(),
        timestamp: msg.getDate().toISOString(),
        body: msg.getPlainBody()
      });
    }
    
    var payload = {
      user_id: userEmail,
      thread_id: gmailThreadId,
      gmail_thread_id: gmailThreadId,
      messages: formattedMessages,
      access_token: accessToken
    };
    
    var endpoint = backendUrl.replace(/\/$/, '') + '/api/label-email-async';
    Logger.log("[API] Calling: " + endpoint);
    Logger.log("[API] User: " + userEmail);
    Logger.log("[API] Thread: " + gmailThreadId);
    Logger.log("[API] Messages: " + formattedMessages.length);
    
    var options = {
      method: 'post',
      contentType: 'application/json',
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    };
    
    var response = UrlFetchApp.fetch(endpoint, options);
    var responseCode = response.getResponseCode();
    var responseBody = response.getContentText();
    
    if (responseCode === 202) {
      Logger.log("[OK] Label job queued (202 Accepted)");
      try {
        var result = JSON.parse(responseBody);
        Logger.log("[OK] Job ID: " + result.job_id);
      } catch (e) {
        Logger.log("[OK] Response: " + responseBody);
      }
    } else if (responseCode >= 200 && responseCode < 300) {
      Logger.log("[OK] Sent to backend: " + responseCode);
    } else {
      Logger.warn("[WARN] Backend returned: " + responseCode);
      Logger.warn("[WARN] Response: " + responseBody.substring(0, 200));
    }
    
    var label = GmailApp.createLabel("OpenMailBot/NewEmails");
    thread.addLabel(label);
    Logger.log("[OK] Label applied");
    
  } catch (error) {
    Logger.error("ERROR labeling: " + error.message);
  }
}

/**
 * Button click handler for manual email sync.
 * Shows a notification with the sync result.
 * Sends 10 emails when manually triggered (vs 1 email on auto-sync).
 */
function handleSyncEmailsButton() {
  Logger.log("[UI] Sync button clicked");
  
  // Manual sync sends 10 emails (for testing)
  var result = syncLatestEmailsToBackend(10);
  
  var notificationText;
  if (result.success) {
    if (result.synced !== undefined) {
      notificationText = "✅ Synced " + result.synced + "/" + result.total + " emails";
      if (result.errors && result.errors.length > 0) {
        notificationText += " (with " + result.errors.length + " errors)";
      }
    } else {
      notificationText = result.message || "✅ Sync completed";
    }
  } else {
    notificationText = "❌ Sync failed: " + (result.message || "Unknown error");
  }
  
  return CardService.newActionResponseBuilder()
    .setNotification(
      CardService.newNotification()
        .setText(notificationText)
    )
    .build();
}

/**
 * Checks for new emails in background when Gmail opens.
 * Sends only the LATEST (1) email to the backend automatically.
 */
function checkForNewEmailsInBackground() {
  console.log("[AUTO-SYNC] ========== START ==========");
  Logger.log("[AUTO-SYNC] ========== START ==========");
  
  try {
    var userProps = PropertiesService.getUserProperties();
    var lastSyncStr = userProps.getProperty("last_manual_sync_timestamp");
    var now = new Date().getTime();
    
    console.log("[AUTO-SYNC] Last sync: " + (lastSyncStr || "never"));
    Logger.log("[AUTO-SYNC] Last sync: " + (lastSyncStr || "never"));
    
    // Send only the LATEST 1 email when Gmail opens automatically
    console.log("[AUTO-SYNC] Calling syncLatestEmailsToBackend(1) - latest email only...");
    Logger.log("[AUTO-SYNC] Calling syncLatestEmailsToBackend(1) - latest email only...");
    
    var result = syncLatestEmailsToBackend(1); // Only send 1 latest email
    
    console.log("[AUTO-SYNC] Result: " + JSON.stringify(result));
    Logger.log("[AUTO-SYNC] Result: " + JSON.stringify(result));
    
    userProps.setProperty("last_manual_sync_timestamp", new Date(now).toISOString());
    
  } catch (error) {
    console.error("[AUTO-SYNC] Error: " + error.message);
    console.error("[AUTO-SYNC] Stack: " + error.stack);
    Logger.log("[AUTO-SYNC] Error: " + error.message);
    Logger.log("[AUTO-SYNC] Stack: " + error.stack);
  }
  
  console.log("[AUTO-SYNC] ========== END ==========");
  Logger.log("[AUTO-SYNC] ========== END ==========");
}

/**
 * Syncs the latest 10 inbox emails to the backend for testing.
 * 
 * This function fetches the most recent 10 inbox threads and sends them
 * to the backend /log-email endpoint for testing purposes.
 * Can be called manually or triggered when Gmail opens.
 * 
 * @param {number} count - Number of emails to sync (default: 10)
 */
function syncLatestEmailsToBackend(count) {
  // Default to 10 if not specified (for manual button clicks)
  if (count === undefined || count === null) {
    count = 10;
  }
  
  console.log("[SYNC] ===== syncLatestEmailsToBackend START (count: " + count + ") =====");
  Logger.log("[SYNC] Starting sync of latest " + count + " inbox email(s)...");
  
  try {
    var backendUrl = getBackendUrl();
    
    console.log("[SYNC] Backend URL: " + (backendUrl || "NOT SET"));
    Logger.log("[SYNC] Backend URL: " + (backendUrl || "NOT SET"));
    
    if (!backendUrl) {
      console.warn("[SYNC] ❌ Backend URL not configured - cannot sync");
      Logger.log("[WARN] Backend URL not configured - cannot sync");
      return {
        success: false,
        message: "Backend URL not configured. Please complete onboarding or configure settings."
      };
    }
    
    var userEmail = Session.getActiveUser().getEmail();
    var accessToken = ScriptApp.getOAuthToken();
    
    console.log("[SYNC] User: " + userEmail);
    Logger.log("[SYNC] User: " + userEmail);
    
    // Get latest N inbox threads
    var threads = GmailApp.getInboxThreads(0, count);
    console.log("[SYNC] Found " + threads.length + " inbox thread(s)");
    Logger.log("[SYNC] Found " + threads.length + " inbox thread(s)");
    
    if (threads.length === 0) {
      console.log("[SYNC] No inbox threads found");
      Logger.log("[SYNC] No inbox threads found");
      return {
        success: true,
        message: "No emails to sync"
      };
    }
    
    var syncedCount = 0;
    var errors = [];
    
    // Process each thread
    for (var i = 0; i < threads.length; i++) {
      try {
        var thread = threads[i];
        var allMessages = thread.getMessages();
        var formattedMessages = [];
        
        // Format all messages in the thread
        for (var j = 0; j < allMessages.length; j++) {
          var msg = allMessages[j];
          formattedMessages.push({
            message_id: msg.getId(),
            from_address: msg.getFrom(),
            to: msg.getTo().split(','),
            subject: msg.getSubject(),
            timestamp: msg.getDate().toISOString(),
            body: msg.getPlainBody().substring(0, 1000), // Limit body size for logging
            is_unread: msg.isUnread(),
            has_attachments: msg.getAttachments().length > 0
          });
        }
        
        var payload = {
          user_id: userEmail,
          thread_id: thread.getId(),
          gmail_thread_id: thread.getId(),
          messages: formattedMessages,
          access_token: accessToken,
          sync_type: "manual_sync",
          timestamp: new Date().toISOString()
        };
        
        var endpoint = backendUrl.replace(/\/$/, '') + '/log-email';
        
        var options = {
          method: 'post',
          contentType: 'application/json',
          payload: JSON.stringify(payload),
          muteHttpExceptions: true
        };
        
        var threadSubject = formattedMessages[formattedMessages.length - 1].subject;
        console.log("[SYNC] Sending thread " + (i + 1) + "/" + threads.length + ": " + threadSubject);
        Logger.log("[SYNC] Sending thread " + (i + 1) + "/" + threads.length + ": " + threadSubject);
        
        var response = UrlFetchApp.fetch(endpoint, options);
        var responseCode = response.getResponseCode();
        var responseBody = response.getContentText();
        
        console.log("[SYNC] Response code: " + responseCode);
        
        if (responseCode >= 200 && responseCode < 300) {
          console.log("[SYNC] ✅ Thread synced successfully (" + responseCode + ")");
          Logger.log("[OK] Thread synced successfully (" + responseCode + ")");
          syncedCount++;
        } else {
          var errorMsg = "Thread " + thread.getId() + " failed: " + responseCode;
          console.warn("[SYNC] ⚠️ " + errorMsg);
          console.warn("[SYNC] Response: " + responseBody.substring(0, 200));
          Logger.warn("[WARN] " + errorMsg);
          Logger.warn("[WARN] Response: " + responseBody.substring(0, 200));
          errors.push(errorMsg);
        }
        
        // Add small delay to avoid rate limiting
        Utilities.sleep(100);
        
      } catch (threadError) {
        var threadErrorMsg = "Thread " + i + " error: " + threadError.message;
        console.error("[SYNC] ❌ " + threadErrorMsg);
        Logger.error("[ERROR] " + threadErrorMsg);
        errors.push(threadErrorMsg);
      }
    }
    
    console.log("[SYNC] Complete - Synced: " + syncedCount + "/" + threads.length);
    Logger.log("[SYNC] Complete - Synced: " + syncedCount + "/" + threads.length);
    
    if (errors.length > 0) {
      console.log("[SYNC] Errors: " + errors.length);
      Logger.log("[SYNC] Errors: " + errors.length);
      errors.forEach(function(err) { 
        console.log("  - " + err);
        Logger.log("  - " + err);
      });
    }
    
    console.log("[SYNC] ===== syncLatestEmailsToBackend END =====");
    
    return {
      success: true,
      synced: syncedCount,
      total: threads.length,
      errors: errors
    };
    
  } catch (error) {
    console.error("[SYNC] ❌❌❌ FATAL ERROR: " + error.message);
    console.error("[SYNC] Stack: " + error.stack);
    Logger.error("[ERROR] syncLatestEmailsToBackend failed: " + error.message);
    Logger.error("[ERROR] Stack: " + error.stack);
    return {
      success: false,
      message: error.message
    };
  }
}

/**
 * Retrieves the list of processed message IDs.
 * 
 * Returns an array of Gmail message IDs that have already been processed
 * to prevent duplicate processing on subsequent runs.
 * 
 * @returns {string[]} Array of processed message IDs
 */
function getProcessedMessageIds() {
  try {
    var userProps = PropertiesService.getUserProperties();
    var processedIdsJson = userProps.getProperty("processed_message_ids") || "[]";
    var processedIds = JSON.parse(processedIdsJson);
    
    Logger.log("[LIST] Retrieved " + processedIds.length + " processed message IDs");
    return processedIds;
  } catch (error) {
    Logger.error("ERROR retrieving processed message IDs: " + error.message);
    return [];
  }
}

/**
 * Adds a message ID to the processed list.
 * 
 * Tracks that this message has been processed to prevent reprocessing
 * on the next cycle. Automatically prunes old entries (keeps last 1000).
 * 
 * @param {string} messageId - The Gmail message ID to track
 */
function addProcessedMessageId(messageId) {
  try {
    var userProps = PropertiesService.getUserProperties();
    var processedIdsJson = userProps.getProperty("processed_message_ids") || "[]";
    var processedIds = JSON.parse(processedIdsJson);
    
    if (processedIds.indexOf(messageId) === -1) {
      processedIds.push(messageId);
      
      if (processedIds.length > 1000) {
        processedIds = processedIds.slice(-1000);
        Logger.log("[PRUNE] Pruned list - kept last 1000");
      }
      
      userProps.setProperty("processed_message_ids", JSON.stringify(processedIds));
      Logger.log("[OK] Added message ID to list: " + messageId);
    }
  } catch (error) {
    Logger.error("[ERROR] Adding message ID failed: " + error.message);
  }
}

/**
 * Clears the processed message IDs list.
 * 
 * Use this to reset tracking if needed (e.g., to reprocess all emails).
 * Call manually from the Apps Script editor if you want to start fresh.
 */
function clearProcessedMessageIds() {
  try {
    PropertiesService.getUserProperties().deleteProperty("processed_message_ids");
    Logger.log("[OK] Cleared processed message IDs list");
  } catch (error) {
    Logger.error("ERROR clearing processed message IDs: " + error.message);
  }
}

/**
 * Clears the last check timestamp.
 * 
 * Use this to reset the time tracking if needed (e.g., to reprocess all emails).
 * Call manually from the Apps Script editor if you want to start fresh.
 */
function clearLastCheckTimestamp() {
  try {
    PropertiesService.getUserProperties().deleteProperty("last_email_check_timestamp");
    Logger.log("[OK] Cleared last check timestamp");
  } catch (error) {
    Logger.error("ERROR clearing timestamp: " + error.message);
  }
}

/**
 * Helper function to prevent trigger accumulation.
 * 
 * Deletes all existing triggers for the specified function name.
 * This prevents multiple triggers from piling up and running in parallel.
 * 
 * @param {string} functionName - The name of the function to clean triggers for
 */
function deleteExistingTriggers(functionName) {
  try {
    var triggers = ScriptApp.getProjectTriggers();
    var deletedCount = 0;
    
    for (var i = 0; i < triggers.length; i++) {
      if (triggers[i].getHandlerFunction() === functionName) {
        ScriptApp.deleteTrigger(triggers[i]);
        deletedCount++;
        Logger.log("[DELETE] Deleted trigger");
      }
    }
    
    if (deletedCount === 0) {
      Logger.log("[INFO] No triggers found");
    }
  } catch (error) {
    Logger.error("[ERROR] Trigger deletion failed: " + error.message);
  }
}