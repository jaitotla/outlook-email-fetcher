/**
 * Background script for Email Thread Assistant
 * Handles API communication and message processing
 */

// Default backend URL - can be changed in settings
const DEFAULT_FLASK_SERVER_URL = "http://43.204.98.38:8000";

/**
 * Get the configured backend URL from settings
 * Falls back to default if not set
 */
async function getBackendUrl() {
  try {
    const result = await browser.storage.local.get("backend_url");
    return result.backend_url || DEFAULT_FLASK_SERVER_URL;
  } catch (error) {
    console.error("Error getting backend URL:", error);
    return DEFAULT_FLASK_SERVER_URL;
  }
}

// Initialize extension
browser.runtime.onInstalled.addListener(() => {
  console.log("Email Thread Assistant installed");
});

/**
 * Message listener for communication from popup
 */
browser.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log("Background received message:", message.action);
  
  switch (message.action) {
    case "summarizeThread":
      handleSummarizeThread(message.data)
        .then(sendResponse)
        .catch(error => sendResponse({ error: error.message }));
      return true; // Keep channel open for async response
      
    case "draftWithAttachments":
      handleDraftWithAttachments(message.data)
        .then(sendResponse)
        .catch(error => sendResponse({ error: error.message }));
      return true;
      
    case "chatWithThread":
      handleChatWithThread(message.data)
        .then(sendResponse)
        .catch(error => sendResponse({ error: error.message }));
      return true;
      
    default:
      console.warn("Unknown message action:", message.action);
      sendResponse({ error: "Unknown action: " + message.action });
      return false;
  }
});

/**
 * Get all messages in a thread
 */
async function getThreadMessages(messageId) {
  try {
    const message = await browser.messages.get(messageId);
    const conversationId = message.headerMessageId;
    
    // Get all messages in the folder
    const folder = await browser.messages.get(messageId).then(msg => 
      browser.folders.get(msg.folder)
    );
    
    // Query for messages in the same conversation
    const messageList = await browser.messages.query({
      folder: folder,
      headerMessageId: conversationId
    });
    
    // Get full message details for each
    const messages = await Promise.all(
      messageList.messages.map(msg => browser.messages.getFull(msg.id))
    );
    
    return messages;
  } catch (error) {
    console.error("Error getting thread messages:", error);
    throw error;
  }
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

/**
 * Handle summarize thread request
 */
async function handleSummarizeThread(data) {
  try {
    const { messageId } = data;
    
    // Get all messages in thread
    const fullMessage = await browser.messages.getFull(messageId);
    const message = await browser.messages.get(messageId);
    
    // Extract thread text
    const plainBody = extractPlainText(fullMessage);
    const threadText = `From: ${message.author}\nDate: ${new Date(message.date).toISOString()}\n\n${plainBody}`;
    
    // Get conversation ID for thread grouping
    const conversationId = message.headerMessageId || message.id.toString();
    
    // Log email data to server (best effort)
    try {
      await logEmailData(conversationId, threadText, "summarize");
    } catch (logErr) {
      console.log("logEmailData failed:", logErr.message);
    }
    
    // Get summary from AI
    const summary = await callFlaskAPI(threadText, "summarize");
    
    return { 
      success: true, 
      summary: summary,
      threadId: conversationId
    };
    
  } catch (error) {
    console.error("Error in handleSummarizeThread:", error);
    throw error;
  }
}

/**
 * Handle draft with attachments request
 */
async function handleDraftWithAttachments(data) {
  try {
    const { messageId } = data;
    const message = await browser.messages.get(messageId);
    const fullMessage = await browser.messages.getFull(messageId);
    
    const conversationId = message.headerMessageId || message.id.toString();
    const userId = await getUserId();
    
    // Log email messages
    try {
      console.log("Attempting to log email messages...");
      console.log("userId:", userId);
      console.log("conversationId:", conversationId);
      const messages = [await formatMessageForLogging(message, fullMessage)];
      console.log("Formatted message count:", messages.length);
      console.log("First message:", JSON.stringify(messages[0], null, 2));
      
      const logResult = await logEmailMessages({
        threadId: conversationId,
        messages: messages,
        userId: userId
      });
      console.log("✅ Email logging successful:", logResult);
    } catch (logErr) {
      console.error("❌ Email logging failed:", logErr.message);
      console.error("Full error:", logErr);
      // Don't block draft creation if logging fails
    }
    
    // Upload attachments
    let attachmentCount = 0;
    try {
      const attachments = await getMessageAttachments(messageId);
      if (attachments.length > 0) {
        attachmentCount = attachments.length;
        await storeMessageAttachments({
          threadId: conversationId,
          messageId: messageId,
          userId: userId,
          attachments: attachments
        });
        console.log(`Uploaded ${attachmentCount} attachments`);
      }
    } catch (attErr) {
      console.log("Attachment upload failed:", attErr.message);
    }
    
    // Get user preferences
    const userPreferences = await getUserPreferences();
    
    // Call pipeline API
    const draftResult = await callPipelineAPI({
      user_id: userId,
      thread_id: conversationId,
      message_id: messageId.toString(),
      user_preferences: userPreferences
    });
    
    // Create draft in Thunderbird
    const draftContent = draftResult.draft_content || draftResult.response || "No draft content received";
    const processingInfo = draftResult.processing_info || {};
    
    // Create compose window with draft
    const composeDetails = {
      to: [message.author],
      subject: message.subject.startsWith("Re:") ? message.subject : `Re: ${message.subject}`,
      plainTextBody: draftContent,
      isPlainText: true
    };
    
    await browser.compose.beginNew(composeDetails);
    
    return {
      success: true,
      draftContent: draftContent,
      processingInfo: processingInfo,
      attachmentCount: attachmentCount
    };
    
  } catch (error) {
    console.error("Error in handleDraftWithAttachments:", error);
    throw error;
  }
}

/**
 * Handle chat with thread request
 */
async function handleChatWithThread(data) {
  try {
    const { messageId, question } = data;
    const message = await browser.messages.get(messageId);
    const conversationId = message.headerMessageId || message.id.toString();
    const userId = await getUserId();
    
    // Log email messages (same as draft flow)
    try {
      console.log("Attempting to log email messages for chat...");
      console.log("userId:", userId);
      console.log("conversationId:", conversationId);
      const messages = [await formatMessageForLogging(message, await browser.messages.getFull(messageId))];
      console.log("Formatted message count:", messages.length);
      
      const logResult = await logEmailMessages({
        threadId: conversationId,
        messages: messages,
        userId: userId
      });
      console.log("✅ Email logging successful for chat:", logResult);
    } catch (logErr) {
      console.error("❌ Email logging failed for chat:", logErr.message);
      // Don't block chat if logging fails
    }
    
    // Upload attachments (same as draft flow)
    try {
      const fullMessage = await browser.messages.getFull(messageId);
      const attachments = await getMessageAttachments(messageId);
      if (attachments.length > 0) {
        await storeMessageAttachments({
          threadId: conversationId,
          messageId: messageId,
          userId: userId,
          attachments: attachments
        });
        console.log(`✅ Uploaded ${attachments.length} attachments for chat`);
      } else {
        console.log("No attachments found for this message");
      }
    } catch (attErr) {
      console.error("❌ Attachment upload failed for chat:", attErr.message);
      // Don't block chat if attachment upload fails
    }
    
    // Call chat API
    const backendUrl = await getBackendUrl();
    const apiEndpoint = `${backendUrl}/api/chat-with-thread`;
    
    const payload = {
      user_id: userId,
      thread_id: conversationId,
      question: question
    };
    
    const response = await fetch(apiEndpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });
    
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Server error (${response.status}): ${errorText}`);
    }
    
    const result = await response.json();
    
    if (!result.success) {
      throw new Error(result.error || "Unknown error from server");
    }
    
    return {
      success: true,
      answer: result.answer,
      processingInfo: result.processing_info
    };
    
  } catch (error) {
    console.error("Error in handleChatWithThread:", error);
    throw error;
  }
}

/**
 * Log email messages to server
 */
async function logEmailMessages(data) {
  try {
    const { threadId, messages, userId } = data;
    
    // Validate required fields
    if (!userId) {
      throw new Error("userId is missing or empty");
    }
    if (!threadId) {
      throw new Error("threadId is missing or empty");
    }
    if (!messages || !Array.isArray(messages) || messages.length === 0) {
      throw new Error("messages must be a non-empty array");
    }
    
    const backendUrl = await getBackendUrl();
    const endpoint = `${backendUrl}/api/log-email`;
    
    const payload = {
      user_id: userId,
      thread_id: threadId,
      messages: messages
    };
    
    console.log("Sending email log payload:", JSON.stringify(payload, null, 2));
    
    const response = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error(`Server returned ${response.status}: ${errorText}`);
      throw new Error(`Server returned ${response.status}: ${errorText}`);
    }
    
    console.log("Email messages logged successfully");
    return await response.text();
  } catch (error) {
    console.error("Error in logEmailMessages:", error.message);
    throw error;
  }
}

/**
 * Store message attachments to server
 */
async function storeMessageAttachments(data) {
  try {
    const { threadId, messageId, userId, attachments } = data;
    
    // Validate required fields
    if (!userId) {
      throw new Error("userId is missing");
    }
    if (!threadId) {
      throw new Error("threadId is missing");
    }
    if (!messageId) {
      throw new Error("messageId is missing");
    }
    
    if (!attachments || attachments.length === 0) {
      console.log("No attachments to store");
      return null;
    }
    
    const backendUrl = await getBackendUrl();
    const endpoint = `${backendUrl}/api/store-attachments`;
    
    const payload = {
      user_id: userId,
      thread_id: threadId,
      message_id: messageId.toString(),
      attachments: attachments
    };
    
    console.log(`Uploading ${attachments.length} attachments...`);
    console.log("Attachment payload summary:", {
      user_id: userId,
      thread_id: threadId,
      message_id: messageId.toString(),
      attachment_count: attachments.length
    });
    
    const response = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });
    
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Upload error (${response.status}): ${errorText}`);
    }
    
    console.log("Attachments stored successfully");
    return await response.text();
  } catch (error) {
    console.error("Error in storeMessageAttachments:", error.message);
    throw error;
  }
}

/**
 * Get message attachments
 */
async function getMessageAttachments(messageId) {
  try {
    const attachments = await browser.messages.listAttachments(messageId);
    const attachmentData = [];
    
    for (const att of attachments) {
      try {
        const file = await browser.messages.getAttachmentFile(messageId, att.partName);
        const arrayBuffer = await file.arrayBuffer();
        const base64 = arrayBufferToBase64(arrayBuffer);
        
        attachmentData.push({
          filename: att.name,
          content: base64,
          mime_type: att.contentType
        });
      } catch (err) {
        console.error(`Failed to process attachment ${att.name}:`, err);
      }
    }
    
    return attachmentData;
  } catch (error) {
    console.error("Error getting attachments:", error);
    return [];
  }
}

/**
 * Convert ArrayBuffer to Base64
 */
function arrayBufferToBase64(buffer) {
  let binary = '';
  const bytes = new Uint8Array(buffer);
  const len = bytes.byteLength;
  for (let i = 0; i < len; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

/**
 * Format message for logging
 */
async function formatMessageForLogging(message, fullMessage) {
  return {
    message_id: message.id.toString(),
    from_address: message.author,
    to: message.recipients || [],
    subject: message.subject,
    timestamp: new Date(message.date).toISOString(),
    body: extractPlainText(fullMessage)
  };
}

/**
 * Call Flask API
 */
async function callFlaskAPI(content, action) {
  const backendUrl = await getBackendUrl();
  const apiEndpoint = `${backendUrl}/chat`;
  
  let prompt;
  if (action === "summarize") {
    prompt = `You are an expert enterprise communication analyst.
You will be given a batch of related email threads (20–30 emails) that belong to the same conversation.
Your task is to analyze ALL emails carefully and produce a **chronological, structured summary**.

### Instructions
1. Read every email in full.
2. Identify the **true chronological order** based on timestamps and context.
3. Merge replies and forwards logically (do not repeat content).
4. Ignore greetings, signatures, and disclaimers unless they add meaning.
5. Focus on decisions, requests, approvals, blockers, and commitments.

---

### Output Format (STRICT)

#### 1️⃣ Conversation Overview
- **Topic:** <one-line summary of what this email thread is about>
- **Participants:** <key people and their roles>
- **Time Range:** <first email date → last email date>

---

#### 2️⃣ Chronological Timeline of Events
(List in exact order — earliest to latest)

**Step 1 – <Short Title>**
- What happened: <one concise line>
- Outcome / Decision: <if any>
- Expectation / Ask at this stage: <what was requested or expected next>

**Step 2 – <Short Title>**
- What happened: <one concise line>
- Outcome / Decision: <if any>
- Expectation / Ask at this stage: <what was requested or expected next>

(Repeat for all major events. Use **2 lines only** if the event is large or critical.)

---

#### 3️⃣ Current Status (As of Last Email)
- **Current State:** <e.g., Awaiting approval / In progress / Blocked / Completed>
- **Owner:** <person responsible now>
- **Pending Actions:** <bullet list if multiple>

---

#### 4️⃣ Open Questions / Pending Requests
(List anything that is still unanswered or waiting)
- <Question or request>
- <Who needs to respond>

---

#### 5️⃣ Final Ask / Next Expected Action
(Clearly state what the sender expects next)
- **Action Required:** <clear action>
- **From Whom:** <person/team>
- **Deadline (if mentioned):** <date or "Not specified">

---

### Rules
- Be factual and neutral.
- Do NOT invent information.
- Do NOT summarize per email — summarize per **event**.
- Keep language professional and concise.
- Prefer clarity over verbosity.

Email Thread:
${content}`;
  } else {
    prompt = content;
  }
  
  const payload = {
    prompt: prompt
  };
  
  const response = await fetch(apiEndpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
  
  if (!response.ok) {
    throw new Error(`Flask API error: ${response.status}`);
  }
  
  const data = await response.json();
  
  if (data.error) {
    throw new Error(`Flask API error: ${data.error}`);
  }
  
  if (data.response) {
    return data.response;
  }
  
  throw new Error("Unexpected API response format");
}

/**
 * Call Pipeline API for draft generation
 */
async function callPipelineAPI(requestData) {
  const backendUrl = await getBackendUrl();
  const apiEndpoint = `${backendUrl}/api/draft-with-attachments`;
  
  const response = await fetch(apiEndpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(requestData)
  });
  
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Server error (${response.status}): ${errorText}`);
  }
  
  const contentType = response.headers.get("content-type");
  if (contentType && contentType.includes("text/html")) {
    throw new Error("Server returned HTML instead of JSON. Check if the server is running.");
  }
  
  const data = await response.json();
  
  if (data.error) {
    throw new Error(`Pipeline API error: ${data.error}`);
  }
  
  return data;
}

/**
 * Log email data to server
 */
async function logEmailData(threadId, threadText, action) {
  const backendUrl = await getBackendUrl();
  const endpoint = `${backendUrl}/api/log-email-data`;
  
  const payload = {
    thread_id: threadId,
    content: threadText,
    action: action
  };
  
  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
  
  if (!response.ok) {
    throw new Error(`Failed to log email data: ${response.status}`);
  }
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
 * Get user preferences
 */
async function getUserPreferences() {
  const result = await browser.storage.local.get("user_settings");
  const settings = result.user_settings || {};
  
  return {
    name: settings.user_name || "User",
    position: settings.user_position || "Professional",
    tone: settings.user_tone || "professional",
    custom_instructions: settings.system_prompt || ""
  };
}