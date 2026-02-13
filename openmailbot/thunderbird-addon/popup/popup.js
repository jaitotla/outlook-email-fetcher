/**
 * Popup script for Email Thread Assistant
 * Handles UI interactions and communication with background script
 */

let currentMessageId = null;
let currentThreadId = null;
let chatHistory = [];

// Initialize popup
document.addEventListener("DOMContentLoaded", async () => {
  try {
    // Get current message
    const tabs = await browser.tabs.query({ active: true, currentWindow: true });
    const messageDisplay = await browser.messageDisplay.getDisplayedMessage(tabs[0].id);
    
    if (messageDisplay) {
      currentMessageId = messageDisplay.id;
      console.log("Current message ID:", currentMessageId);
    } else {
      showError("No email selected. Please select an email to analyze.");
      return;
    }
    
    setupEventListeners();
  } catch (error) {
    console.error("Initialization error:", error);
    showError("Failed to initialize: " + error.message);
  }
});

/**
 * Setup event listeners for buttons
 */
function setupEventListeners() {
  // Main menu
  document.getElementById("summarize-btn").addEventListener("click", handleSummarize);
  document.getElementById("chat-btn").addEventListener("click", handleShowChat);
  document.getElementById("draft-btn").addEventListener("click", handleDraftWithAttachments);
  document.getElementById("settings-btn").addEventListener("click", handleSettings);
  
  // Summary view
  document.getElementById("draft-response-btn").addEventListener("click", handleDraftResponse);
  document.getElementById("back-from-summary-btn").addEventListener("click", showMainMenu);
  
  // Draft view
  document.getElementById("back-from-draft-btn").addEventListener("click", showMainMenu);
  
  // Chat view
  document.getElementById("send-chat-btn").addEventListener("click", handleSendChat);
  document.getElementById("clear-chat-btn").addEventListener("click", handleClearChat);
  document.getElementById("back-from-chat-btn").addEventListener("click", showMainMenu);
  
  // Error view
  document.getElementById("back-from-error-btn").addEventListener("click", showMainMenu);
  
  // Enter key in chat input
  document.getElementById("chat-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && e.ctrlKey) {
      handleSendChat();
    }
  });
}

/**
 * Show/hide views
 */
function showView(viewId) {
  const views = ["main-menu", "loading", "summary-view", "draft-view", "chat-view", "error-view"];
  views.forEach(id => {
    document.getElementById(id).classList.add("hidden");
  });
  document.getElementById(viewId).classList.remove("hidden");
}

function showMainMenu() {
  showView("main-menu");
}

function showLoading(text = "Processing...") {
  document.getElementById("loading-text").textContent = text;
  showView("loading");
}

function showError(message) {
  document.getElementById("error-message").textContent = message;
  showView("error-view");
}

/**
 * Handle summarize thread
 */
async function handleSummarize() {
  try {
    showLoading("Analyzing thread...");
    
    const response = await browser.runtime.sendMessage({
      action: "summarizeThread",
      data: { messageId: currentMessageId }
    });
    
    if (response.error) {
      throw new Error(response.error);
    }
    
    currentThreadId = response.threadId;
    displaySummary(response.summary);
    
  } catch (error) {
    console.error("Summarize error:", error);
    showError("Error generating summary: " + error.message);
  }
}

/**
 * Display summary
 */
function displaySummary(summary) {
  const summaryContent = document.getElementById("summary-content");
  summaryContent.innerHTML = formatMarkdownToHtml(summary);
  showView("summary-view");
}

/**
 * Handle draft response
 */
async function handleDraftResponse() {
  try {
    showLoading("Creating draft...");
    
    const summary = document.getElementById("summary-content").textContent;
    
    // Build draft prompt
    const draftPrompt = `### Draft Response Email (Based on Current State)

I am a professional email user
Draft response from me

Write a professional, neutral email that:
- Acknowledges the current status
- Restates pending actions
- Requests the next expected step
- Does NOT introduce new information

Email format only. No explanations.

Summary:
${summary}`;
    
    // Call background to create draft
    const response = await browser.runtime.sendMessage({
      action: "createDraft",
      data: { 
        messageId: currentMessageId,
        draftPrompt: draftPrompt
      }
    });
    
    if (response.error) {
      throw new Error(response.error);
    }
    
    showMainMenu();
    
  } catch (error) {
    console.error("Draft error:", error);
    showError("Error creating draft: " + error.message);
  }
}

/**
 * Handle draft with attachments
 */
async function handleDraftWithAttachments() {
  try {
    showLoading("Creating draft with attachments...");
    
    const response = await browser.runtime.sendMessage({
      action: "draftWithAttachments",
      data: { messageId: currentMessageId }
    });
    
    if (response.error) {
      throw new Error(response.error);
    }
    
    displayDraftResult(response);
    
  } catch (error) {
    console.error("Draft with attachments error:", error);
    showError("Error creating draft with attachments: " + error.message);
  }
}

/**
 * Display draft result
 */
function displayDraftResult(result) {
  const { draftContent, processingInfo, attachmentCount } = result;
  
  // Set message
  document.getElementById("draft-message").innerHTML = 
    "✅ <strong>A draft has been created and opened in a compose window!</strong>";
  
  // Set processing info
  let processingMsg = "";
  if (attachmentCount > 0) {
    processingMsg = `📊 <strong>Processing Summary:</strong><br>
• Attachments found: ${processingInfo.attachments_found || attachmentCount}<br>
• Newly processed: ${processingInfo.attachments_processed || attachmentCount}<br>
• Already cached: ${processingInfo.attachments_skipped || 0}`;
  } else {
    processingMsg = "ℹ️ No attachments found in this thread.";
  }
  document.getElementById("draft-processing").innerHTML = processingMsg;
  
  // Set preview
  const preview = draftContent.substring(0, 800);
  document.getElementById("draft-preview").textContent = 
    preview + (draftContent.length > 800 ? "\n\n... (draft continues)" : "");
  
  showView("draft-view");
}

/**
 * Handle show chat
 */
async function handleShowChat() {
  try {
    showLoading("Loading chat interface...");
    
    // Get current message to extract thread ID
    const message = await browser.messages.get(currentMessageId);
    currentThreadId = message.headerMessageId || currentMessageId.toString();
    
    // Clear chat history
    chatHistory = [];
    
    // Let background.js handle logging emails and attachments via the chat pipeline
    // No need to call them directly here
    
    displayChat();
  } catch (error) {
    console.error("Show chat error:", error);
    showError("Error opening chat: " + error.message);
  }
}

/**
 * Display chat interface
 */
function displayChat() {
  const chatHistoryEl = document.getElementById("chat-history");
  chatHistoryEl.innerHTML = "";
  
  if (chatHistory.length === 0) {
    document.getElementById("example-questions").classList.remove("hidden");
    document.getElementById("chat-processing").classList.add("hidden");
  } else {
    document.getElementById("example-questions").classList.add("hidden");
    
    chatHistory.forEach(msg => {
      const messageDiv = document.createElement("div");
      messageDiv.className = `chat-message ${msg.role}`;
      
      const label = msg.role === "user" ? "You:" : "AI:";
      const content = msg.role === "assistant" ? formatMarkdownToHtml(msg.content) : escapeHtml(msg.content);
      
      messageDiv.innerHTML = `<strong>${label}</strong>${content}`;
      chatHistoryEl.appendChild(messageDiv);
    });
    
    // Scroll to bottom
    chatHistoryEl.scrollTop = chatHistoryEl.scrollHeight;
  }
  
  document.getElementById("chat-input").value = "";
  showView("chat-view");
}

/**
 * Handle send chat message
 */
async function handleSendChat() {
  const input = document.getElementById("chat-input");
  const question = input.value.trim();
  
  if (!question) {
    return;
  }
  
  try {
    // Add user message to history
    chatHistory.push({ role: "user", content: question });
    input.value = "";
    displayChat();
    
    showLoading("Getting answer...");
    
    const response = await browser.runtime.sendMessage({
      action: "chatWithThread",
      data: {
        messageId: currentMessageId,
        question: question
      }
    });
    
    if (response.error) {
      throw new Error(response.error);
    }
    
    // Add AI response to history
    chatHistory.push({ role: "assistant", content: response.answer });
    
    // Show processing info on first message
    if (chatHistory.length === 2 && response.processingInfo) {
      const info = response.processingInfo;
      let msg = "📊 <strong>Processing Summary:</strong><br>";
      
      if (info.emails) {
        msg += `• Total messages: ${info.emails.total_messages}<br>`;
        msg += `• Already processed: ${info.emails.already_processed}<br>`;
        msg += `• Newly processed: ${info.emails.newly_processed}<br>`;
      }
      
      if (info.attachments && info.attachments.attachments_found > 0) {
        msg += `• Attachments found: ${info.attachments.attachments_found}<br>`;
        msg += `• Attachments processed: ${info.attachments.attachments_processed}<br>`;
        msg += `• Attachments cached: ${info.attachments.attachments_skipped}`;
      }
      
      document.getElementById("chat-processing").innerHTML = msg;
      document.getElementById("chat-processing").classList.remove("hidden");
    }
    
    displayChat();
    
  } catch (error) {
    console.error("Chat error:", error);
    // Remove user message from history on error
    chatHistory.pop();
    showError("Error in chat: " + error.message);
  }
}

/**
 * Handle clear chat
 */
function handleClearChat() {
  chatHistory = [];
  displayChat();
}

/**
 * Handle settings
 */
function handleSettings() {
  browser.runtime.openOptionsPage();
}

/**
 * Format markdown to HTML
 */
function formatMarkdownToHtml(text) {
  if (!text) return "";
  
  // Convert line breaks to HTML breaks
  text = text.replace(/\n/g, '<br>');
  
  // Replace markdown headers
  text = text.replace(/####\s+(.*?)<br>/g, '<br><strong>$1</strong><br>');
  text = text.replace(/###\s+(.*?)<br>/g, '<br><strong>$1</strong><br>');
  
  // Bold text between **
  text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  
  // Horizontal rules
  text = text.replace(/---<br>/g, '━━━━━━━━━━━━━━<br>');
  
  // Bullet points
  text = text.replace(/<br>-\s+(.*?)<br>/g, '<br>  • $1<br>');
  
  // Clean up multiple consecutive breaks
  text = text.replace(/(<br>){3,}/g, '<br><br>');
  
  return text;
}

/**
 * Escape HTML special characters
 */
function escapeHtml(text) {
  if (!text) return "";
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}