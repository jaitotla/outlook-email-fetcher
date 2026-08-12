/*
 * Copyright (c) Microsoft Corporation. All rights reserved. Licensed under the MIT license.
 * See LICENSE in the project root for license information.
 */

/* global document, Office */

import { PublicClientApplication } from "@azure/msal-browser";

const BACKEND_URL = "https://lsdiedb39c.pagekite.me";

const msalConfig = {
  auth: {
    clientId: "708b6c48-376c-4d05-8529-f256785836d9",
    authority: "https://login.microsoftonline.com/consumers",
    redirectUri: "https://outlook-email-fetcher.vercel.app/taskpane.html",
  },
  cache: {
    cacheLocation: "localStorage",
  },
};

const msalInstance = new PublicClientApplication(msalConfig);
const loginRequest = { scopes: ["Mail.ReadWrite", "MailboxSettings.ReadWrite", "User.Read"] };

const CATEGORY_DEFINITIONS = [
  { displayName: "Response", color: "preset0" },
  { displayName: "Finance", color: "preset5" },
  { displayName: "Recruitment", color: "preset9" },
];

let currentAccessToken = null;
let currentUserId = null;
let _settingsSynced = false;

Office.onReady(async (info) => {
  if (info.host === Office.HostType.Outlook) {
    document.getElementById("sideload-msg").style.display = "none";
    document.getElementById("app-body").style.display = "flex";

    document.getElementById("btn-summarize").onclick = handleSummarizeClick;
    document.getElementById("btn-back").onclick = () => {
      document.getElementById("summary-panel").style.display = "none";
      document.getElementById("button-stack").style.display = "flex";
    };

    document.getElementById("btn-settings").onclick = openSettingsPanel;
    document.getElementById("btn-advanced").onclick = openAdvancedSettingsPanel;
    document.getElementById("s-back").onclick = closeSettingsPanel;
    document.getElementById("as-back").onclick = closeAdvancedSettingsPanel;
    document.getElementById("s-save").onclick = saveSettingsFromForm;
    document.getElementById("s-fill-from-server").onclick = loadSettingsFromServer;
    document.getElementById("s-mode").onchange = onModeChange;

    document.getElementById("btn-chat").onclick = openChatPanel;
    document.getElementById("chat-back").onclick = closeChatPanel;
    document.getElementById("chat-clear").onclick = () => {
      document.getElementById("chat-question").value = "";
      document.getElementById("chat-answer").textContent = "";
    };
    document.getElementById("chat-send").onclick = handleChatSend;

    document.getElementById("btn-generate-draft").onclick = handleGenerateDraftClick;
    document.getElementById("draft-back").onclick = closeDraftPanel;
    document.getElementById("draft-open-compose").onclick = openDraftInCompose;

    document.getElementById("btn-draft-attach").onclick = handleDraftWithAttachmentsClick;

    document.getElementById("btn-index").onclick = openIndexPanel;
    document.getElementById("index-back").onclick = closeIndexPanel;
    document.getElementById("index-start").onclick = handleIndexStart;
    document.getElementById("index-status").onclick = handleIndexStatus;

    await msalInstance.initialize();

    const response = await msalInstance.handleRedirectPromise();
    if (response) {
      await fetchEmails(response.accessToken);
      return;
    }

    const accounts = msalInstance.getAllAccounts();
    if (accounts.length > 0) {
      msalInstance.setActiveAccount(accounts[0]);
      try {
        const tokenResponse = await msalInstance.acquireTokenSilent({
          ...loginRequest,
          account: accounts[0],
        });
        await fetchEmails(tokenResponse.accessToken);
      } catch (e) {
        signInAutomatically();
      }
    } else {
      signInAutomatically();
    }
  }
});

function signInAutomatically() {
  Office.context.ui.displayDialogAsync(
    "https://localhost:3000/auth.html",
    { height: 60, width: 30 },
    (result) => {
      const dialog = result.value;
      dialog.addEventHandler(Office.EventType.DialogMessageReceived, async (arg) => {
        const message = JSON.parse(arg.message);
        dialog.close();
        if (message.status === "success") {
          await fetchEmails(message.token);
        } else {
          console.error("Sign-in failed");
        }
      });
    }
  );
}

async function getAccessToken() {
  if (currentAccessToken) {
    return currentAccessToken;
  }
  throw new Error("Not signed in — please reopen the add-in");
}

async function fetchCurrentUserEmail(accessToken) {
  const response = await fetch(
    "https://graph.microsoft.com/v1.0/me?$select=mail,userPrincipalName",
    { headers: { Authorization: `Bearer ${accessToken}` } }
  );
  if (!response.ok) return null;
  const data = await response.json();
  return data.mail || data.userPrincipalName || null;
}

async function fetchEmails(accessToken) {
  currentAccessToken = accessToken;
  currentUserId = await fetchCurrentUserEmail(accessToken);

  try {
    const graphResponse = await fetch(
      "https://graph.microsoft.com/v1.0/me/messages?$top=10&$select=id,subject,from,toRecipients,body,bodyPreview,receivedDateTime,internetMessageId,conversationId,internetMessageHeaders,hasAttachments",
      {
        headers: { Authorization: `Bearer ${accessToken}` },
      }
    );

    if (!graphResponse.ok) {
      throw new Error(`Graph API error: ${graphResponse.status}`);
    }

    const data = await graphResponse.json();
    await pushToBackendByThread(data.value);
    await fetchAndPushAttachments(data.value, accessToken);
    await ensureCategoriesExist(accessToken);
    await autoClassifyAndTag(data.value, accessToken);
  } catch (error) {
    console.error("fetchEmails error:", error);
  }
}

async function pushToBackendByThread(messages) {
  const threadGroups = {};

  for (const msg of messages) {
    const threadId = msg.conversationId || "unknown";
    if (!threadGroups[threadId]) threadGroups[threadId] = [];

    threadGroups[threadId].push({
      message_id: msg.id,
      from_address: msg.from?.emailAddress?.address || "",
      to: (msg.toRecipients || []).map((r) => r.emailAddress?.address).filter(Boolean),
      subject: msg.subject || "",
      timestamp: msg.receivedDateTime || "",
      body: msg.body?.content || "",
    });
  }

  for (const [threadId, msgs] of Object.entries(threadGroups)) {
    try {
      const response = await fetch(`${BACKEND_URL}/api/log-email`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: currentUserId, thread_id: threadId, messages: msgs }),
      });
      const result = await response.json();
      console.log(`Thread ${threadId} storage result:`, result);
    } catch (error) {
      console.error(`Failed to push thread ${threadId} to backend:`, error);
    }
  }
}

async function fetchAndPushAttachments(messages, accessToken) {
  for (const msg of messages) {
    if (!msg.hasAttachments) continue;

    try {
      const attResponse = await fetch(
        `https://graph.microsoft.com/v1.0/me/messages/${msg.id}/attachments`,
        {
          headers: { Authorization: `Bearer ${accessToken}` },
        }
      );

      if (!attResponse.ok) continue;

      const attData = await attResponse.json();

      const attachments = attData.value
        .filter((a) => a["@odata.type"] === "#microsoft.graph.fileAttachment" && a.contentBytes)
        .map((a) => ({
          filename: a.name,
          content: a.contentBytes,
          mime_type: a.contentType || null,
        }));

      if (attachments.length === 0) continue;

      const response = await fetch(`${BACKEND_URL}/api/store-attachments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: currentUserId,
          thread_id: msg.conversationId || "unknown",
          message_id: msg.id,
          attachments,
        }),
      });
      const result = await response.json();
      console.log(`Attachments for ${msg.id} storage result:`, result);
    } catch (error) {
      console.error(`Failed to push attachments for ${msg.id}:`, error);
    }
  }
}

async function ensureCategoriesExist(accessToken) {
  try {
    const listResponse = await fetch(
      "https://graph.microsoft.com/v1.0/me/outlook/masterCategories",
      { headers: { Authorization: `Bearer ${accessToken}` } }
    );

    if (!listResponse.ok) {
      throw new Error(`Failed to list categories: ${listResponse.status}`);
    }

    const listData = await listResponse.json();
    const existingNames = new Set(listData.value.map((c) => c.displayName));

    for (const def of CATEGORY_DEFINITIONS) {
      if (!existingNames.has(def.displayName)) {
        const createResponse = await fetch(
          "https://graph.microsoft.com/v1.0/me/outlook/masterCategories",
          {
            method: "POST",
            headers: {
              Authorization: `Bearer ${accessToken}`,
              "Content-Type": "application/json",
            },
            body: JSON.stringify(def),
          }
        );
        if (!createResponse.ok) {
          console.error(`Failed to create category ${def.displayName}:`, createResponse.status);
        }
      }
    }
  } catch (error) {
    console.error("Failed to ensure categories exist:", error);
  }
}

function classifyEmailByKeywords(subject, fromAddress, bodyPreview) {
  const text = `${subject} ${fromAddress} ${bodyPreview || ""}`.toLowerCase();

  if (/invoice|payment|refund|salary|finance|bank/.test(text)) return "Finance";
  if (/interview|job|recruit|application|hiring|resume/.test(text)) return "Recruitment";
  if (/^re:|^fwd:|reply/.test(text)) return "Response";

  return null;
}

async function applyCategoryToMessage(messageId, categoryName, accessToken) {
  const response = await fetch(`https://graph.microsoft.com/v1.0/me/messages/${messageId}`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ categories: [categoryName] }),
  });

  if (!response.ok) {
    throw new Error(`Failed to apply category: ${response.status}`);
  }

  return await response.json();
}

async function autoClassifyAndTag(messages, accessToken) {
  for (const msg of messages) {
    const category = classifyEmailByKeywords(
      msg.subject || "",
      msg.from?.emailAddress?.address || "",
      msg.bodyPreview || ""
    );

    if (category) {
      try {
        await applyCategoryToMessage(msg.id, category, accessToken);
        console.log(`Tagged "${msg.subject}" as ${category}`);
      } catch (err) {
        console.error(`Failed to tag message ${msg.id}:`, err);
      }
    }
  }
}

// ─── SETTINGS PANEL ────────────────────────────────────────────────────────

function openSettingsPanel() {
  document.getElementById("button-stack").style.display = "none";
  document.getElementById("settings-panel").style.display = "block";
  document.getElementById("s-account").value = currentUserId || "";
  document.getElementById("s-agent-url").value = BACKEND_URL;
  loadSettingsFromServer();
}

function closeSettingsPanel() {
  document.getElementById("settings-panel").style.display = "none";
  document.getElementById("button-stack").style.display = "flex";
}

function openAdvancedSettingsPanel() {
  document.getElementById("button-stack").style.display = "none";
  document.getElementById("advanced-settings-panel").style.display = "block";
}

function closeAdvancedSettingsPanel() {
  document.getElementById("advanced-settings-panel").style.display = "none";
  document.getElementById("button-stack").style.display = "flex";
}

function onModeChange() {
  const mode = document.getElementById("s-mode").value;
  const agentUrlField = document.getElementById("s-agent-url");
  if (mode === "manotr") {
    agentUrlField.value = BACKEND_URL;
    agentUrlField.disabled = true;
  } else {
    agentUrlField.disabled = false;
  }
}

async function loadSettingsFromServer() {
  if (!currentUserId) return;
  const status = document.getElementById("s-status");
  status.textContent = "Loading...";
  try {
    const resp = await fetch(`${BACKEND_URL}/api/settings?user_id=${encodeURIComponent(currentUserId)}`);
    if (resp.ok) {
      const data = await resp.json();
      const s = data.settings || data;
      document.getElementById("s-mode").value = s.mode || "manotr";
      document.getElementById("s-agent-url").value = s.agent_url || BACKEND_URL;
      document.getElementById("s-llm-provider").value = s.llm_provider || "manotr";
      document.getElementById("s-embedding-provider").value = s.embedding_provider || "manotr";
      document.getElementById("s-vector-provider").value = s.vector_provider || "manotr";
      document.getElementById("s-user-name").value = s.user_name || "";
      document.getElementById("s-user-position").value = s.user_position || "";
      document.getElementById("s-user-tone").value = s.user_tone || "professional";
      document.getElementById("s-system-prompt").value = s.system_prompt || "";
      document.getElementById("s-draft-font").value = s.draft_font || "arial";
      onModeChange();
      status.textContent = "Loaded from server.";
    } else if (resp.status === 404) {
      status.textContent = "No settings on server yet — fill in and save.";
    } else {
      status.textContent = `Load failed: ${resp.status}`;
    }
  } catch (e) {
    status.textContent = `Load error: ${e.message}`;
  }
}

async function saveSettingsFromForm() {
  const status = document.getElementById("s-status");
  const name = document.getElementById("s-user-name").value.trim();
  const position = document.getElementById("s-user-position").value.trim();

  if (!name || !position) {
    status.textContent = "Name and Position are required.";
    return;
  }

  const settings = {
    agent_url: document.getElementById("s-agent-url").value.trim(),
    mode: document.getElementById("s-mode").value,
    llm_provider: document.getElementById("s-llm-provider").value,
    llm_api_key: "",
    llm_model: "gpt-4o-mini",
    llm_base_url: "",
    embedding_provider: document.getElementById("s-embedding-provider").value,
    embedding_api_key: "",
    embedding_model: "text-embedding-3-small",
    vector_provider: document.getElementById("s-vector-provider").value,
    vector_url: "",
    vector_api_key: "",
    user_name: name,
    user_position: position,
    user_tone: document.getElementById("s-user-tone").value,
    system_prompt: document.getElementById("s-system-prompt").value,
    draft_font: document.getElementById("s-draft-font").value,
    monitor_inactivity_hours: "12",
  };

  status.textContent = "Saving...";
  try {
    const resp = await fetch(`${BACKEND_URL}/api/settings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: currentUserId, settings }),
    });
    if (resp.ok) {
      _settingsSynced = true;
      status.textContent = "✅ Settings saved.";
    } else {
      status.textContent = `Save failed: ${resp.status}`;
    }
  } catch (e) {
    status.textContent = `Save error: ${e.message}`;
  }
}

// ─── SUMMARIZE THREAD ──────────────────────────────────────────────────────

async function handleSummarizeClick() {
  const summaryPanel = document.getElementById("summary-panel");
  const summaryContent = document.getElementById("summary-content");
  const buttonStack = document.getElementById("button-stack");

  buttonStack.style.display = "none";
  summaryPanel.style.display = "block";
  summaryContent.innerHTML = "Loading thread...";

  try {
    const accessToken = await getAccessToken();
    const currentItem = Office.context.mailbox.item;

    if (!currentItem) {
      summaryContent.innerHTML = "No email is currently open.";
      return;
    }

    const currentMessageResponse = await fetch(
      `https://graph.microsoft.com/v1.0/me/messages/${currentItem.itemId}?$select=conversationId,subject`,
      { headers: { Authorization: `Bearer ${accessToken}` } }
    );

    if (!currentMessageResponse.ok) {
      throw new Error(`Failed to load current message: ${currentMessageResponse.status}`);
    }

    const currentMessage = await currentMessageResponse.json();
    const conversationId = currentMessage.conversationId;

    const filterQuery = encodeURIComponent(`conversationId eq '${conversationId}'`);
    const threadResponse = await fetch(
      `https://graph.microsoft.com/v1.0/me/messages?$filter=${filterQuery}&$select=id,subject,from,toRecipients,body,receivedDateTime`,
      { headers: { Authorization: `Bearer ${accessToken}` } }
    );

    if (!threadResponse.ok) {
      throw new Error(`Failed to load thread: ${threadResponse.status}`);
    }

    const threadData = await threadResponse.json();
    threadData.value.sort((a, b) => new Date(a.receivedDateTime) - new Date(b.receivedDateTime));

    const messagesForBackend = threadData.value.map((msg) => ({
      message_id: msg.id,
      from_address: msg.from?.emailAddress?.address || "",
      to: (msg.toRecipients || []).map((r) => r.emailAddress?.address).filter(Boolean),
      subject: msg.subject || "",
      timestamp: msg.receivedDateTime || "",
      body: msg.body?.content || "",
    }));

    await fetch(`${BACKEND_URL}/api/log-email`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: currentUserId,
        thread_id: conversationId,
        messages: messagesForBackend,
      }),
    });

    summaryContent.innerHTML = "Summarizing...";

    const summarizeResponse = await fetch(`${BACKEND_URL}/api/summarize-thread`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: currentUserId, thread_id: conversationId }),
    });

    if (!summarizeResponse.ok) {
      throw new Error(`Failed to start summarization: ${summarizeResponse.status}`);
    }

    const { job_id } = await summarizeResponse.json();

    const result = await pollJobStatus(job_id);
    summaryContent.innerHTML = `<div style="white-space: pre-wrap;">${result.summary}</div>`;
  } catch (error) {
    console.error(error);
    summaryContent.innerHTML = `<p style="color:red;">Error: ${error.message}</p>`;
  }
}

async function pollJobStatus(jobId, maxAttempts = 40, intervalMs = 2000) {
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise((resolve) => setTimeout(resolve, intervalMs));

    const statusResponse = await fetch(`${BACKEND_URL}/api/job-status/${jobId}`);
    if (!statusResponse.ok) {
      throw new Error(`Job status check failed: ${statusResponse.status}`);
    }

    const statusData = await statusResponse.json();

    if (statusData.status === "done") {
      return statusData.result;
    }
    if (statusData.status === "error") {
      throw new Error(statusData.error || "Job failed");
    }
  }
  throw new Error("Request timed out — the backend may still be processing. Try again in a moment.");
}

// ─── CHAT WITH THREAD ──────────────────────────────────────────────────────

function openChatPanel() {
  document.getElementById("button-stack").style.display = "none";
  document.getElementById("chat-panel").style.display = "block";
}

function closeChatPanel() {
  document.getElementById("chat-panel").style.display = "none";
  document.getElementById("button-stack").style.display = "flex";
}

async function handleChatSend() {
  const answerDiv = document.getElementById("chat-answer");
  const question = document.getElementById("chat-question").value.trim();

  if (!question) {
    answerDiv.textContent = "Please enter a question.";
    return;
  }

  answerDiv.textContent = "Thinking...";

  try {
    const accessToken = await getAccessToken();
    const currentItem = Office.context.mailbox.item;

    if (!currentItem) {
      answerDiv.textContent = "No email is currently open.";
      return;
    }

    const currentMessageResponse = await fetch(
      `https://graph.microsoft.com/v1.0/me/messages/${currentItem.itemId}?$select=conversationId`,
      { headers: { Authorization: `Bearer ${accessToken}` } }
    );
    if (!currentMessageResponse.ok) {
      throw new Error(`Failed to load current message: ${currentMessageResponse.status}`);
    }
    const currentMessage = await currentMessageResponse.json();
    const conversationId = currentMessage.conversationId;

    const chatResponse = await fetch(`${BACKEND_URL}/api/chat-with-thread`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: currentUserId, thread_id: conversationId, question }),
    });

    if (!chatResponse.ok) {
      throw new Error(`Chat request failed: ${chatResponse.status}`);
    }

    const initial = await chatResponse.json();
    const result = initial.job_id ? await pollJobStatus(initial.job_id) : initial;

    answerDiv.textContent = result.answer || result.response || "No answer received.";
  } catch (error) {
    console.error(error);
    answerDiv.textContent = `Error: ${error.message}`;
  }
}

// ─── INDEX EMAIL HISTORY ───────────────────────────────────────────────────

function openIndexPanel() {
  document.getElementById("button-stack").style.display = "none";
  document.getElementById("index-panel").style.display = "block";
  document.getElementById("index-account").value = currentUserId || "";
}

function closeIndexPanel() {
  document.getElementById("index-panel").style.display = "none";
  document.getElementById("button-stack").style.display = "flex";
}

function rangeToDateFilter(range) {
  const now = new Date();
  const after = new Date();

  if (range === "10days") {
    after.setDate(now.getDate() - 10);
  } else {
    after.setMonth(now.getMonth() - parseInt(range, 10));
  }

  return after.toISOString();
}

async function handleIndexStart() {
  const statusText = document.getElementById("index-status-text");
  const startBtn = document.getElementById("index-start");
  const range = document.getElementById("index-range").value;

  if (!currentUserId || !currentAccessToken) {
    statusText.textContent = "Not signed in.";
    return;
  }

  startBtn.disabled = true;
  statusText.textContent = "Fetching emails to index...";

  try {
    const afterDate = rangeToDateFilter(range);
    const filterQuery = encodeURIComponent(`receivedDateTime ge ${afterDate}`);

    const graphResponse = await fetch(
      `https://graph.microsoft.com/v1.0/me/messages?$filter=${filterQuery}&$select=id,subject,from,toRecipients,body,receivedDateTime,conversationId&$top=100`,
      { headers: { Authorization: `Bearer ${currentAccessToken}` } }
    );

    if (!graphResponse.ok) {
      throw new Error(`Failed to fetch emails: ${graphResponse.status}`);
    }

    const data = await graphResponse.json();
    const messages = data.value || [];

    const threadGroups = {};
    for (const msg of messages) {
      const threadId = msg.conversationId || "unknown";
      if (!threadGroups[threadId]) threadGroups[threadId] = [];
      threadGroups[threadId].push({
        message_id: msg.id,
        from_address: msg.from?.emailAddress?.address || "",
        to: (msg.toRecipients || []).map((r) => r.emailAddress?.address).filter(Boolean),
        subject: msg.subject || "",
        timestamp: msg.receivedDateTime || "",
        body: msg.body?.content || "",
      });
    }

    const threadIds = Object.keys(threadGroups);

    if (threadIds.length === 0) {
      statusText.textContent = "No emails found in that range.";
      startBtn.disabled = false;
      return;
    }

    let processed = 0;
    let errors = 0;

    for (const threadId of threadIds) {
      statusText.textContent = `Indexing thread ${processed + errors + 1} of ${threadIds.length}...`;
      try {
        await fetch(`${BACKEND_URL}/api/log-email`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: currentUserId,
            thread_id: threadId,
            messages: threadGroups[threadId],
          }),
        });

        const labelResponse = await fetch(`${BACKEND_URL}/api/label-email`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: currentUserId,
            thread_id: threadId,
            messages: threadGroups[threadId],
          }),
        });

        if (!labelResponse.ok) {
          errors++;
        } else {
          processed++;
        }
      } catch (err) {
        console.error(`Failed to index thread ${threadId}:`, err);
        errors++;
      }
    }

    statusText.textContent = `✅ Done. Indexed ${processed} thread(s)${errors > 0 ? `, ${errors} error(s)` : ""}.`;
  } catch (error) {
    console.error(error);
    statusText.textContent = `❌ Error: ${error.message}`;
  } finally {
    startBtn.disabled = false;
  }
}

async function handleIndexStatus() {
  const statusText = document.getElementById("index-status-text");
  statusText.textContent = "Live status polling not available for Outlook — check the message above after Start Indexing completes.";
}

// ─── GENERATE DRAFT ────────────────────────────────────────────────────────

let _lastDraftContent = "";
let _lastDraftRecipient = "";
let _lastDraftSubject = "";

function closeDraftPanel() {
  document.getElementById("draft-panel").style.display = "none";
  document.getElementById("button-stack").style.display = "flex";
}

async function handleGenerateDraftClick() {
  const draftPanel = document.getElementById("draft-panel");
  const draftStatus = document.getElementById("draft-status");
  const draftContentDiv = document.getElementById("draft-content");
  const buttonStack = document.getElementById("button-stack");

  buttonStack.style.display = "none";
  draftPanel.style.display = "block";
  draftStatus.textContent = "Loading thread...";
  draftContentDiv.textContent = "";

  try {
    const accessToken = await getAccessToken();
    const currentItem = Office.context.mailbox.item;

    if (!currentItem) {
      draftStatus.textContent = "No email is currently open.";
      return;
    }

    const currentMessageResponse = await fetch(
      `https://graph.microsoft.com/v1.0/me/messages/${currentItem.itemId}?$select=conversationId,subject`,
      { headers: { Authorization: `Bearer ${accessToken}` } }
    );
    if (!currentMessageResponse.ok) {
      throw new Error(`Failed to load current message: ${currentMessageResponse.status}`);
    }
    const currentMessage = await currentMessageResponse.json();
    const conversationId = currentMessage.conversationId;

    const filterQuery = encodeURIComponent(`conversationId eq '${conversationId}'`);
    const threadResponse = await fetch(
      `https://graph.microsoft.com/v1.0/me/messages?$filter=${filterQuery}&$select=id,subject,from,toRecipients,body,receivedDateTime`,
      { headers: { Authorization: `Bearer ${accessToken}` } }
    );
    if (!threadResponse.ok) {
      throw new Error(`Failed to load thread: ${threadResponse.status}`);
    }
    const threadData = await threadResponse.json();
    threadData.value.sort((a, b) => new Date(a.receivedDateTime) - new Date(b.receivedDateTime));

    const messagesForBackend = threadData.value.map((msg) => ({
      message_id: msg.id,
      from_address: msg.from?.emailAddress?.address || "",
      to: (msg.toRecipients || []).map((r) => r.emailAddress?.address).filter(Boolean),
      subject: msg.subject || "",
      timestamp: msg.receivedDateTime || "",
      body: msg.body?.content || "",
    }));

    // Log the thread so the backend has context to draft against
    await fetch(`${BACKEND_URL}/api/log-email`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: currentUserId,
        thread_id: conversationId,
        messages: messagesForBackend,
      }),
    });

    draftStatus.textContent = "Generating draft...";

    const draftResponse = await fetch(`${BACKEND_URL}/api/draft`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: currentUserId, thread_id: conversationId }),
    });

    if (!draftResponse.ok) {
      throw new Error(`Failed to start draft: ${draftResponse.status}`);
    }

    const initial = await draftResponse.json();
    const result = initial.job_id ? await pollJobStatus(initial.job_id) : initial;

    const draftText = (result.draft_content || result.response || "No draft content received.").replace(/^Subject:.*\n+/i, "");

    // Set up compose target: reply to the most recent sender in the thread
    const lastMsg = threadData.value[threadData.value.length - 1];
    _lastDraftContent = draftText;
    _lastDraftRecipient = lastMsg?.from?.emailAddress?.address || "";
    _lastDraftSubject = /^re:/i.test(lastMsg?.subject || "")
      ? lastMsg.subject
      : `Re: ${lastMsg?.subject || ""}`;

    draftStatus.textContent = "✅ Draft generated.";
    draftContentDiv.textContent = draftText;
  } catch (error) {
    console.error(error);
    draftStatus.textContent = `❌ Error: ${error.message}`;
  }
}

async function handleDraftWithAttachmentsClick() {
  const draftPanel = document.getElementById("draft-panel");
  const draftStatus = document.getElementById("draft-status");
  const draftContentDiv = document.getElementById("draft-content");
  const buttonStack = document.getElementById("button-stack");

  buttonStack.style.display = "none";
  draftPanel.style.display = "block";
  draftStatus.textContent = "Loading thread...";
  draftContentDiv.textContent = "";

  try {
    const accessToken = await getAccessToken();
    const currentItem = Office.context.mailbox.item;

    if (!currentItem) {
      draftStatus.textContent = "No email is currently open.";
      return;
    }

    const currentMessageResponse = await fetch(
      `https://graph.microsoft.com/v1.0/me/messages/${currentItem.itemId}?$select=conversationId,subject`,
      { headers: { Authorization: `Bearer ${accessToken}` } }
    );
    if (!currentMessageResponse.ok) {
      throw new Error(`Failed to load current message: ${currentMessageResponse.status}`);
    }
    const currentMessage = await currentMessageResponse.json();
    const conversationId = currentMessage.conversationId;

    const filterQuery = encodeURIComponent(`conversationId eq '${conversationId}'`);
    const threadResponse = await fetch(
      `https://graph.microsoft.com/v1.0/me/messages?$filter=${filterQuery}&$select=id,subject,from,toRecipients,body,receivedDateTime,hasAttachments`,
      { headers: { Authorization: `Bearer ${accessToken}` } }
    );
    if (!threadResponse.ok) {
      throw new Error(`Failed to load thread: ${threadResponse.status}`);
    }
    const threadData = await threadResponse.json();
    threadData.value.sort((a, b) => new Date(a.receivedDateTime) - new Date(b.receivedDateTime));

    const messagesForBackend = threadData.value.map((msg) => ({
      message_id: msg.id,
      from_address: msg.from?.emailAddress?.address || "",
      to: (msg.toRecipients || []).map((r) => r.emailAddress?.address).filter(Boolean),
      subject: msg.subject || "",
      timestamp: msg.receivedDateTime || "",
      body: msg.body?.content || "",
    }));

    await fetch(`${BACKEND_URL}/api/log-email`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_id: currentUserId,
        thread_id: conversationId,
        messages: messagesForBackend,
      }),
    });

    // Collect and store attachments from every message in the thread
    draftStatus.textContent = "Indexing attachments...";
    let attachmentCount = 0;

    for (const msg of threadData.value) {
      if (!msg.hasAttachments) continue;

      try {
        const attResponse = await fetch(
          `https://graph.microsoft.com/v1.0/me/messages/${msg.id}/attachments`,
          { headers: { Authorization: `Bearer ${accessToken}` } }
        );
        if (!attResponse.ok) continue;

        const attData = await attResponse.json();
        const attachments = attData.value
          .filter((a) => a["@odata.type"] === "#microsoft.graph.fileAttachment" && a.contentBytes)
          .map((a) => ({
            filename: a.name,
            content: a.contentBytes,
            mime_type: a.contentType || null,
          }));

        if (attachments.length === 0) continue;

        await fetch(`${BACKEND_URL}/api/store-attachments`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: currentUserId,
            thread_id: conversationId,
            message_id: msg.id,
            attachments,
          }),
        });

        attachmentCount += attachments.length;
      } catch (err) {
        console.error(`Failed to store attachments for message ${msg.id}:`, err);
      }
    }

    draftStatus.textContent = attachmentCount > 0
      ? `Generating draft (${attachmentCount} attachment(s) indexed)...`
      : "Generating draft (no attachments found)...";

    const draftResponse = await fetch(`${BACKEND_URL}/api/draft-with-attachments`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: currentUserId, thread_id: conversationId }),
    });

    if (!draftResponse.ok) {
      throw new Error(`Failed to start draft: ${draftResponse.status}`);
    }

    const initial = await draftResponse.json();
    const result = initial.job_id ? await pollJobStatus(initial.job_id) : initial;

    let draftText = result.draft_content || result.response || "No draft content received.";
    // Strip a leading "Subject: ..." line if the backend included one in the body
    draftText = draftText.replace(/^Subject:.*\n+/i, "");

    const lastMsg = threadData.value[threadData.value.length - 1];
    _lastDraftContent = draftText;
    _lastDraftRecipient = lastMsg?.from?.emailAddress?.address || "";
    _lastDraftSubject = /^re:/i.test(lastMsg?.subject || "")
      ? lastMsg.subject
      : `Re: ${lastMsg?.subject || ""}`;

    draftStatus.textContent = attachmentCount > 0
      ? `✅ Draft generated (${attachmentCount} attachment(s) used as context).`
      : "✅ Draft generated (no attachments in thread).";
    draftContentDiv.textContent = draftText;
  } catch (error) {
    console.error(error);
    draftStatus.textContent = `❌ Error: ${error.message}`;
  }
}

function openDraftInCompose() {
  if (!_lastDraftContent) return;

  Office.context.mailbox.displayNewMessageForm({
    toRecipients: _lastDraftRecipient ? [_lastDraftRecipient] : [],
    subject: _lastDraftSubject,
    htmlBody: _lastDraftContent.replace(/\n/g, "<br>"),
  });
}