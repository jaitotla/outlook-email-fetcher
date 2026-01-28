/**
 * Entry point for Gmail Add-on
 */
function buildAddOn(e) {
  return CardService.newCardBuilder()
    .addSection(
      CardService.newCardSection()
        .setHeader("✨ Email Thread Assistant")
        .addWidget(
          CardService.newTextParagraph()
            .setText("Analyze and interact with your email threads using AI")
        )
    )
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newTextButton()
            .setText("📝 Summarize Thread")
            .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
            .setOnClickAction(
              CardService.newAction().setFunctionName("summarizeThread")
            )
        )
        .addWidget(
          CardService.newTextButton()
            .setText("💬 Chat with Thread")
            .setOnClickAction(
              CardService.newAction().setFunctionName("showChatInterface")
            )
        )
        .addWidget(
          CardService.newTextButton()
            .setText("📎 Draft with Attachments")
            .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
            .setBackgroundColor("#34A853")
            .setOnClickAction(
              CardService.newAction().setFunctionName("draftWithAttachments")
            )
        )
        .addWidget(
          CardService.newTextButton()
            .setText("⚙️ Settings")
            .setOnClickAction(
              CardService.newAction().setFunctionName("showSettingsCard")
            )
        )
    )
    .build();
}

/*
 * COMMENTED OUT: Duplicate function - using the fuller version below (line ~189+)
 * 
 * function draftWithAttachments(e) {
 *   // This was a shorter version that's now superseded by the more complete
 *   // implementation below that includes email logging and better error handling.
 *   // See the active draftWithAttachments function around line 189.
 * }
 */

/**
 * NEW: Draft with Attachments - Main handler
 * Processes attachments and generates AI draft with full context
 */
function draftWithAttachments(e) {
  try {
    var messageId = e.gmail.messageId;
    var thread = GmailApp.getMessageById(messageId).getThread();
    var messages = thread.getMessages();
    var threadId = thread.getId();
    
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
    
    var draftContent = draftResult.response || "No draft content received";
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
      .addSection(
        CardService.newCardSection()
          .setHeader("✅ Draft Created with Attachments")
          .addWidget(
            CardService.newTextParagraph()
              .setText(successMsg)
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
                  .setText("📝 View in Gmail")
                  .setOpenLink(CardService.newOpenLink()
                    .setUrl("https://mail.google.com/mail/u/0/#drafts")
                    .setOpenAs(CardService.OpenAs.FULL_SIZE))
              )
              .addButton(
                CardService.newTextButton()
                  .setText("🔙 Back")
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
 * NEW: Call Pipeline API for draft generation with attachments
 * No longer sends email_data - server will fetch from stored messages
 */
function callPipelineAPI(requestData) {
  var flaskUrl = PropertiesService.getScriptProperties()
    .getProperty("FLASK_SERVER_URL");
  
  if (!flaskUrl) {
    throw new Error("Flask server URL not configured. Please set FLASK_SERVER_URL in Script Properties.");
  }
  
  var apiEndpoint = flaskUrl.replace(/\/$/, '') + '/draft-with-attachments';
  
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
    var messageId = e.gmail.messageId;
    var thread = GmailApp.getMessageById(messageId).getThread();
    var messages = thread.getMessages();
    
    // Show loading state
    var loadingCard = CardService.newCardBuilder()
      .addSection(
        CardService.newCardSection()
          .setHeader("⏳ Analyzing Thread...")
          .addWidget(
            CardService.newTextParagraph()
              .setText("Please wait while we analyze your email thread. This may take a moment...")
          )
      )
      .build();
    
    // Extract thread text
    var threadText = messages.map(function(m) {
      return "From: " + m.getFrom() + "\nDate: " + m.getDate() + "\n\n" + m.getPlainBody();
    }).join("\n\n---\n\n");
    
    // NEW: Log email data to Flask server (best-effort)
    try {
      logEmailData(thread.getId(), threadText, "summarize");
    } catch (logErr) {
      Logger.log("logEmailData failed: " + logErr.message);
    }
    
    // NEW: Store attachments found in messages (best-effort)
    try {
      messages.forEach(function(m) {
        var atts = m.getAttachments ? m.getAttachments() : [];
        if (atts && atts.length > 0) {
          try {
            storeMessageAttachments(thread.getId(), m);
          } catch (attErr) {
            Logger.log("storeMessageAttachments failed for message: " + (m.getId ? m.getId() : "unknown") + " - " + attErr.message);
          }
        }
      });
    } catch (e) {
      Logger.log("Attachment scan failed: " + e.message);
    }
    
    // Get summary from AI
    var summary = callFlaskAPI(threadText, "summarize");
    
    // Format the summary with proper HTML
    var formattedSummary = formatMarkdownToHtml(summary);
    
    // Build card with formatted summary and draft button
    var summarySection = CardService.newCardSection()
      .setHeader("📊 Thread Summary");
    
    // Split summary into smaller paragraphs for better display
    var paragraphs = formattedSummary.split('<br><br>');
    
    paragraphs.forEach(function(para) {
      if (para && para.trim().length > 0) {
        summarySection.addWidget(
          CardService.newTextParagraph().setText(para.trim())
        );
      }
    });
    
    var card = CardService.newCardBuilder()
      .addSection(summarySection);
    
    // Add action buttons
    card.addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newButtonSet()
            .addButton(
              CardService.newTextButton()
                .setText("✉️ Draft Response")
                .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
                .setOnClickAction(
                  CardService.newAction()
                    .setFunctionName("createDraftResponse")
                    .setParameters({summary: summary, threadId: thread.getId()})
                )
            )
            .addButton(
              CardService.newTextButton()
                .setText("🔙 Back")
                .setOnClickAction(
                  CardService.newAction().setFunctionName("buildAddOn")
                )
            )
        )
    );
    
    return card.build();
    
  } catch (error) {
    return showError("Error generating summary: " + error.message);
  }
}

/**
 * Formats markdown-style text to HTML for better display
 */
function formatMarkdownToHtml(text) {
  if (!text) return "";
  
  // Convert line breaks to HTML breaks
  text = text.replace(/\n/g, '<br>');
  
  // Replace markdown headers (must be done before bold)
  text = text.replace(/####\s+(.*?)<br>/g, '<br><b>$1</b><br>');
  text = text.replace(/###\s+(.*?)<br>/g, '<br><b>$1</b><br>');
  
  // Bold text between ** (non-greedy)
  text = text.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>');
  
  // Horizontal rules
  text = text.replace(/---<br>/g, '━━━━━━━━━━━━━━<br>');
  
  // Bullet points (handle at start of line after <br>)
  text = text.replace(/<br>-\s+(.*?)<br>/g, '<br>  • $1<br>');
  
  // Clean up multiple consecutive breaks
  text = text.replace(/(<br>){3,}/g, '<br><br>');
  
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
 * Creates a draft email based on the summary
 */
function createDraftResponse(e) {
  try {
    var summary = e.parameters.summary;
    var threadId = e.parameters.threadId;
    
    // Show loading
    var loadingCard = CardService.newCardBuilder()
      .addSection(
        CardService.newCardSection()
          .setHeader("✍️ Drafting Response...")
          .addWidget(
            CardService.newTextParagraph()
              .setText("Creating your draft email...")
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
      .addSection(
        CardService.newCardSection()
          .setHeader("✅ Draft Created Successfully")
          .addWidget(
            CardService.newTextParagraph()
              .setText(successMsg)
          )
      )
      .addSection(
        CardService.newCardSection()
          .setHeader("📧 Draft Preview")
          .setCollapsible(true)
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
                  .setText("📝 View in Gmail")
                  .setOpenLink(CardService.newOpenLink()
                    .setUrl("https://mail.google.com/mail/u/0/#drafts")
                    .setOpenAs(CardService.OpenAs.FULL_SIZE))
              )
              .addButton(
                CardService.newTextButton()
                  .setText("🔙 Back")
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
    var threadId = thread.getId();
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
  var card = CardService.newCardBuilder();
  
  // Header
  card.addSection(
    CardService.newCardSection()
      .setHeader("💬 Chat with Thread (RAG)")
      .addWidget(
        CardService.newTextParagraph()
          .setText("Ask questions about emails and attachments")
      )
  );
  
  // Show processing info if provided
  if (processingInfo) {
    card.addSection(
      CardService.newCardSection()
        .setHeader("📊 Context Loaded")
        .setCollapsible(true)
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
        .setHeader("💡 Example Questions")
        .addWidget(
          CardService.newTextParagraph()
            .setText("• What are the key points in the attachments?<br>" +
              "• Summarize the decisions made<br>" +
              "• What data is in the Excel file?<br>" +
              "• What does the PDF say about...?<br>" +
              "• Who approved what and when?")
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
        .setHint("Ask about emails or attachments...")
        .setMultiline(true)
    )
    .addWidget(
      CardService.newButtonSet()
        .addButton(
          CardService.newTextButton()
            .setText("Send 📤")
            .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
            .setOnClickAction(
              CardService.newAction()
                .setFunctionName("chatWithThread")
                .setParameters({threadId: threadId})
            )
        )
        .addButton(
          CardService.newTextButton()
            .setText("Clear Chat")
            .setOnClickAction(
              CardService.newAction()
                .setFunctionName("clearChatHistory")
                .setParameters({threadId: threadId})
            )
        )
        .addButton(
          CardService.newTextButton()
            .setText("🔙 Back")
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
    
    var apiEndpoint = flaskUrl.replace(/\/$/, '') + '/chat-with-thread';
    
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
    
    var result = JSON.parse(responseText);
    
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
  
  var apiEndpoint = flaskUrl.replace(/\/$/, '') + '/chat';
  
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
 * Shows error message
 */
function showError(message) {
  return CardService.newCardBuilder()
    .addSection(
      CardService.newCardSection()
        .setHeader("❌ Error")
        .addWidget(
          CardService.newTextParagraph()
            .setText(message)
        )
        .addWidget(
          CardService.newTextButton()
            .setText("🔙 Back")
            .setOnClickAction(
              CardService.newAction().setFunctionName("buildAddOn")
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
  var endpoint = 'https://lsdiedb39c.pagekite.me/log-email';

  // Convert all GmailMessages to array format
  var messageArray = messages.map(function (msg) {
    return {
      message_id: msg.getId(),
      from: msg.getFrom(),
      to: msg.getTo().split(',').map(function (email) {
        return email.trim();
      }),
      subject: msg.getSubject(),
      timestamp: msg.getDate().toISOString(),
      body: msg.getPlainBody()
    };
  });

  // Build payload in required format
  var payload = {
    thread_id: threadId,
    messages: messageArray
  };

  var options = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };

  try {
    var resp = UrlFetchApp.fetch(endpoint, options);
    var responseCode = resp.getResponseCode();

    if (responseCode !== 200) {
      throw new Error("Server returned " + responseCode + ": " + resp.getContentText());
    }

    Logger.log("Logged " + messageArray.length + " messages for thread: " + threadId);
    return resp.getContentText();

  } catch (err) {
    throw new Error("Failed to log email messages: " + err.message);
  }
}


/**
 * NEW: Store attachments of a given GmailMessage to your Flask server /store-attachments
 * Only sends files with allowed extensions: .pdf, .csv, .pptx, .ppt
 */
function storeMessageAttachments(threadId, message) {
  var flaskUrl = PropertiesService.getScriptProperties().getProperty("FLASK_SERVER_URL");
  if (!flaskUrl) {
    throw new Error("FLASK_SERVER_URL not configured.");
  }
  var endpoint = flaskUrl.replace(/\/$/, '') + '/store-attachments';
  
  // Define allowed file extensions
  var allowedExtensions = ['.pdf', '.csv', '.pptx', '.ppt'];
  
  // message may be a GmailMessage; extract id and attachments
  var messageId = (message.getId && message.getId()) || "unknown";
  var blobs = (message.getAttachments && message.getAttachments()) || [];
  if (!blobs || blobs.length === 0) {
    return null;
  }
  
  // Filter attachments by allowed extensions
  var filteredBlobs = blobs.filter(function(b) {
    var filename = b.getName ? b.getName() : "";
    var lowerFilename = filename.toLowerCase();
    return allowedExtensions.some(function(ext) {
      return lowerFilename.endsWith(ext);
    });
  });
  
  // If no valid attachments after filtering, return null
  if (filteredBlobs.length === 0) {
    return null;
  }
  
  var attachments = filteredBlobs.map(function(b) {
    return {
      filename: b.getName ? b.getName() : "attachment",
      content: Utilities.base64Encode(b.getBytes ? b.getBytes() : b.getBytes()),
      mime_type: b.getContentType ? b.getContentType() : "application/octet-stream"
    };
  });
  
  var payload = {
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
  
  try {
    var resp = UrlFetchApp.fetch(endpoint, options);
    return resp.getContentText();
  } catch (err) {
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
function showSettingsCard(e) {
  var userProps = PropertiesService.getUserProperties();
  var currentSettings = loadUserSettings();
  
  var card = CardService.newCardBuilder()
    .setHeader(
      CardService.newCardHeader()
        .setTitle("⚙️ Settings")
        .setSubtitle("Configure your AI providers")
    );
  
  // Mode Selection Section
  var modeSection = CardService.newCardSection()
    .setHeader("🔧 Mode")
    .addWidget(
      CardService.newSelectionInput()
        .setType(CardService.SelectionInputType.DROPDOWN)
        .setFieldName("mode")
        .setTitle("Configuration Mode")
        .addItem("Inbuilt (Zero Configuration)", "inbuilt", currentSettings.mode === "inbuilt")
        .addItem("Custom (Your API Keys)", "custom", currentSettings.mode === "custom")
    )
    .addWidget(
      CardService.newTextParagraph()
        .setText("<i>Inbuilt: Uses central servers, no API keys needed.\nCustom: Use your own API keys for each provider.</i>")
    );
  card.addSection(modeSection);
  
  // LLM Provider Section
  var llmSection = CardService.newCardSection()
    .setHeader("🤖 LLM Provider")
    .addWidget(
      CardService.newSelectionInput()
        .setType(CardService.SelectionInputType.DROPDOWN)
        .setFieldName("llm_provider")
        .setTitle("Provider")
        .addItem("OpenAI", "openai", currentSettings.llm_provider === "openai")
        .addItem("Anthropic (Claude)", "anthropic", currentSettings.llm_provider === "anthropic")
        .addItem("Google Gemini", "gemini", currentSettings.llm_provider === "gemini")
        .addItem("Ollama (Self-hosted)", "ollama", currentSettings.llm_provider === "ollama")
        .addItem("Inbuilt", "inbuilt", currentSettings.llm_provider === "inbuilt" || !currentSettings.llm_provider)
    )
    .addWidget(
      CardService.newTextInput()
        .setFieldName("llm_api_key")
        .setTitle("API Key (for OpenAI/Anthropic/Gemini)")
        .setValue(currentSettings.llm_api_key || "")
        .setHint("Leave empty for Inbuilt/Ollama mode")
    )
    .addWidget(
      CardService.newTextInput()
        .setFieldName("llm_model")
        .setTitle("Model Name")
        .setValue(currentSettings.llm_model || "gpt-4o-mini")
        .setHint("e.g., gpt-4o-mini, claude-3-sonnet, gemini-pro")
    )
    .addWidget(
      CardService.newTextInput()
        .setFieldName("llm_base_url")
        .setTitle("Base URL (for Ollama/Custom)")
        .setValue(currentSettings.llm_base_url || "")
        .setHint("e.g., http://localhost:11434 for Ollama")
    );
  card.addSection(llmSection);
  
  // Embedding Provider Section
  var embeddingSection = CardService.newCardSection()
    .setHeader("📊 Embedding Provider")
    .addWidget(
      CardService.newSelectionInput()
        .setType(CardService.SelectionInputType.DROPDOWN)
        .setFieldName("embedding_provider")
        .setTitle("Provider")
        .addItem("OpenAI", "openai", currentSettings.embedding_provider === "openai")
        .addItem("Nomic", "nomic", currentSettings.embedding_provider === "nomic")
        .addItem("Google Gemini", "gemini", currentSettings.embedding_provider === "gemini")
        .addItem("Sentence Transformers", "sentence-transformers", currentSettings.embedding_provider === "sentence-transformers")
        .addItem("Inbuilt", "inbuilt", currentSettings.embedding_provider === "inbuilt" || !currentSettings.embedding_provider)
    )
    .addWidget(
      CardService.newTextInput()
        .setFieldName("embedding_api_key")
        .setTitle("API Key")
        .setValue(currentSettings.embedding_api_key || "")
        .setHint("Leave empty for Inbuilt mode")
    )
    .addWidget(
      CardService.newTextInput()
        .setFieldName("embedding_model")
        .setTitle("Model Name")
        .setValue(currentSettings.embedding_model || "text-embedding-3-small")
        .setHint("e.g., text-embedding-3-small, nomic-embed-text-v1.5")
    );
  card.addSection(embeddingSection);
  
  // Vector Database Section
  var vectorSection = CardService.newCardSection()
    .setHeader("🗄️ Vector Database")
    .addWidget(
      CardService.newSelectionInput()
        .setType(CardService.SelectionInputType.DROPDOWN)
        .setFieldName("vector_provider")
        .setTitle("Provider")
        .addItem("Pinecone", "pinecone", currentSettings.vector_provider === "pinecone")
        .addItem("ChromaDB", "chroma", currentSettings.vector_provider === "chroma")
        .addItem("Weaviate", "weaviate", currentSettings.vector_provider === "weaviate")
        .addItem("Inbuilt", "inbuilt", currentSettings.vector_provider === "inbuilt" || !currentSettings.vector_provider)
    )
    .addWidget(
      CardService.newTextInput()
        .setFieldName("vector_url")
        .setTitle("Server URL")
        .setValue(currentSettings.vector_url || "")
        .setHint("e.g., https://your-index.pinecone.io")
    )
    .addWidget(
      CardService.newTextInput()
        .setFieldName("vector_api_key")
        .setTitle("API Key")
        .setValue(currentSettings.vector_api_key || "")
        .setHint("Leave empty for Inbuilt mode")
    );
  card.addSection(vectorSection);
  
  // User Info Section (for draft personalization)
  var userInfoSection = CardService.newCardSection()
    .setHeader("👤 User Profile (for drafts)")
    .addWidget(
      CardService.newTextInput()
        .setFieldName("user_name")
        .setTitle("Your Name")
        .setValue(currentSettings.user_name || "")
        .setHint("Used in email signatures")
    )
    .addWidget(
      CardService.newTextInput()
        .setFieldName("user_position")
        .setTitle("Your Position/Title")
        .setValue(currentSettings.user_position || "")
        .setHint("e.g., Product Manager, Developer")
    )
    .addWidget(
      CardService.newSelectionInput()
        .setType(CardService.SelectionInputType.DROPDOWN)
        .setFieldName("user_tone")
        .setTitle("Preferred Tone")
        .addItem("Professional", "professional", currentSettings.user_tone === "professional" || !currentSettings.user_tone)
        .addItem("Friendly", "friendly", currentSettings.user_tone === "friendly")
        .addItem("Formal", "formal", currentSettings.user_tone === "formal")
        .addItem("Casual", "casual", currentSettings.user_tone === "casual")
    )
    .addWidget(
      CardService.newTextInput()
        .setFieldName("system_prompt")
        .setTitle("Custom System Prompt")
        .setValue(currentSettings.system_prompt || "")
        .setHint("Optional: Override default AI behavior")
        .setMultiline(true)
    );
  card.addSection(userInfoSection);
  
  // Save Button Section
  var actionSection = CardService.newCardSection()
    .addWidget(
      CardService.newTextButton()
        .setText("💾 Save Settings")
        .setTextButtonStyle(CardService.TextButtonStyle.FILLED)
        .setBackgroundColor("#1a73e8")
        .setOnClickAction(
          CardService.newAction().setFunctionName("saveSettings")
        )
    )
    .addWidget(
      CardService.newTextButton()
        .setText("🔄 Reset to Defaults")
        .setOnClickAction(
          CardService.newAction().setFunctionName("resetSettings")
        )
    )
    .addWidget(
      CardService.newTextButton()
        .setText("🔙 Back")
        .setOnClickAction(
          CardService.newAction().setFunctionName("buildAddOn")
        )
    );
  card.addSection(actionSection);
  
  return card.build();
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
    mode: "inbuilt",
    llm_provider: "inbuilt",
    llm_api_key: "",
    llm_model: "gpt-4o-mini",
    llm_base_url: "",
    embedding_provider: "inbuilt",
    embedding_api_key: "",
    embedding_model: "text-embedding-3-small",
    vector_provider: "inbuilt",
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
  
  var settings = {
    mode: formInputs.mode || "inbuilt",
    llm_provider: formInputs.llm_provider || "inbuilt",
    llm_api_key: formInputs.llm_api_key || "",
    llm_model: formInputs.llm_model || "gpt-4o-mini",
    llm_base_url: formInputs.llm_base_url || "",
    embedding_provider: formInputs.embedding_provider || "inbuilt",
    embedding_api_key: formInputs.embedding_api_key || "",
    embedding_model: formInputs.embedding_model || "text-embedding-3-small",
    vector_provider: formInputs.vector_provider || "inbuilt",
    vector_url: formInputs.vector_url || "",
    vector_api_key: formInputs.vector_api_key || "",
    user_name: formInputs.user_name || "",
    user_position: formInputs.user_position || "",
    user_tone: formInputs.user_tone || "professional",
    system_prompt: formInputs.system_prompt || ""
  };
  
  // Save to local UserProperties
  var userProps = PropertiesService.getUserProperties();
  userProps.setProperty("user_settings", JSON.stringify(settings));
  
  // Sync to backend (best effort)
  try {
    syncSettingsToBackend(settings);
  } catch (syncErr) {
    Logger.log("Settings sync to backend failed: " + syncErr.message);
    // Continue - local save was successful
  }
  
  // Return notification card
  return CardService.newCardBuilder()
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newTextParagraph()
            .setText("✅ <b>Settings saved successfully!</b>\n\nYour preferences have been stored.")
        )
        .addWidget(
          CardService.newTextButton()
            .setText("🔙 Back to Home")
            .setOnClickAction(
              CardService.newAction().setFunctionName("buildAddOn")
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
  var backendUrl = PropertiesService.getScriptProperties().getProperty("BACKEND_URL");
  if (!backendUrl) {
    throw new Error("BACKEND_URL not configured in Script Properties");
  }
  
  var userId = Session.getEffectiveUser().getEmail();
  var endpoint = backendUrl.replace(/\/$/, '') + '/api/settings';
  
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
function resetSettings(e) {
  var userProps = PropertiesService.getUserProperties();
  userProps.deleteProperty("user_settings");
  
  return CardService.newCardBuilder()
    .addSection(
      CardService.newCardSection()
        .addWidget(
          CardService.newTextParagraph()
            .setText("🔄 <b>Settings reset to defaults!</b>\n\nAll custom settings have been cleared.")
        )
        .addWidget(
          CardService.newTextButton()
            .setText("⚙️ Open Settings")
            .setOnClickAction(
              CardService.newAction().setFunctionName("showSettingsCard")
            )
        )
        .addWidget(
          CardService.newTextButton()
            .setText("🔙 Back to Home")
            .setOnClickAction(
              CardService.newAction().setFunctionName("buildAddOn")
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
  
  // If mode is inbuilt, override provider settings
  if (settings.mode === "inbuilt") {
    return {
      mode: "inbuilt",
      llm_provider: "inbuilt",
      embedding_provider: "inbuilt",
      vector_provider: "inbuilt",
      user_name: settings.user_name,
      user_position: settings.user_position,
      user_tone: settings.user_tone,
      system_prompt: settings.system_prompt
    };
  }
  
  return settings;
}