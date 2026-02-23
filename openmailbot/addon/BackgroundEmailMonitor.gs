/**
 * UNIFIED EMAIL MONITOR - Single Script Solution
 * Runs every 1 minute to capture ALL new emails and attachments
 * 
 * SETUP INSTRUCTIONS:
 * 1. Copy this entire script to your Google Apps Script project
 * 2. Set your FLASK_SERVER_URL in Script Properties
 * 3. Run setupEmailMonitor() ONCE
 * 4. Done! Script will automatically run every minute in the background
 * 
 * FEATURES:
 * - Captures emails in real-time (checks every 1 minute)
 * - Processes allowed attachments: .pdf, .csv, .pptx, .ppt
 * - Tracks processed emails to avoid duplicates
 * - Automatic error recovery
 * - Runs completely in background after setup
 */

// ============================================================================
// CONFIGURATION
// ============================================================================

var CONFIG = {
  // File type filtering
  ALLOWED_EXTENSIONS: ['.pdf', '.csv', '.pptx', '.ppt'],
  
  // How often to check for new emails (in minutes)
  CHECK_INTERVAL_MINUTES: 1,
  
  // Maximum attachments to process per run (safety limit)
  MAX_ATTACHMENTS_PER_RUN: 50,
  
  // Property keys for tracking
  LAST_CHECK_TIME: "last_email_check_time",
  PROCESSED_MESSAGE_IDS: "processed_message_ids",
  
  // Label color mapping - assign colors to specific labels
  // Available colors: red, orange, yellow, green, cyan, blue, purple, gray, lightgray, cocoa, white, darkgray
  LABEL_COLORS: {
    "Response": "blue",
    "Fyi": "cyan",
    "Notification": "lightgray",
    "Meeting": "purple",
    "Awaiting reply": "yellow",
    "Escalation": "red",
    "Hotels": "orange",
    "Airline": "orange",
    "Airlines": "orange",
    "Travel": "orange",
    "Restaurant": "cocoa",
    "Booking": "green",
    "Bank": "blue",
    "Recruitment": "purple"
  }
};
var BULK_JOB_STATE_KEY = "bulk_job_state";
var BULK_JOB_ABORT_KEY = "bulk_job_abort";  // ← poison pill

// ============================================================================
// MAIN MONITORING FUNCTION (Runs every 1 minute)
// ============================================================================

/**
 * UPDATED monitorEmails - Logs appear instantly
 * Replace your entire monitorEmails() function with this
 */
function monitorEmails() {
  var startTime = new Date();
  
  try {
    console.log("=== EMAIL MONITOR START ===");
    console.log("Time: " + startTime.toISOString());
    
    // Check server URL
    var flaskUrl = PropertiesService.getScriptProperties().getProperty("FLASK_SERVER_URL");
    if (!flaskUrl) {
      console.log("❌ ERROR: FLASK_SERVER_URL not configured!");
      return;
    }
    console.log("✓ Server URL: " + flaskUrl.substring(0, 50) + "...");
    
    // Get last check time
    var lastCheckTime = getLastCheckTime();
    var now = new Date();
    console.log("✓ Last check: " + lastCheckTime.toISOString());
    console.log("✓ Current time: " + now.toISOString());
    
    // Get domain filters
    var filters = getDomainFilters();
    console.log("✓ Domain filters: " + filters.length);
    
    // Search for new emails
    console.log("");
    console.log("--- SEARCHING FOR NEW EMAILS ---");
    var newMessages = getNewEmailsSince(lastCheckTime);
    console.log("Found: " + newMessages.length + " new message(s)");
    
    if (newMessages.length === 0) {
      console.log("ℹ️  No new emails");
      updateLastCheckTime(now);
      console.log("=== COMPLETE (no emails) ===");
      return;
    }
    
    // Process stats
    var stats = {
      processed: 0,
      skipped: 0,
      filtered: 0,
      emailsSent: 0,
      attachmentsSent: 0,
      labelsApplied: 0,
      errors: 0
    };
    
    console.log("");
    console.log("--- PROCESSING MESSAGES ---");
    
    // Process each message
    for (var i = 0; i < newMessages.length; i++) {
      var message = newMessages[i];
      
      console.log("");
      console.log("Message " + (i + 1) + "/" + newMessages.length + ":");
      console.log("  Subject: " + message.getSubject());
      console.log("  From: " + message.getFrom());
      
      // Skip if already processed
      if (isMessageProcessed(message.getId())) {
        console.log("  ⊘ SKIPPED (already processed)");
        stats.skipped++;
        continue;
      }
      
      // Apply domain filter
      if (shouldFilterMessage(message)) {
        console.log("  🚫 FILTERED (domain exclusion)");
        stats.filtered++;
        markMessageProcessed(message.getId());
        continue;
      }
      
      // Process this message
      try {
        console.log("  → Processing...");
        
        var threadId = message.getThread().getId();
        
        // Send email to server for labeling
        try {
          var label = sendEmailToServer(threadId, message);
          stats.emailsSent++;
          if (label) {
            stats.labelsApplied++;
            console.log("  ✓ Email labeled: " + label);
          } else {
            console.log("  ✓ Email sent (no label assigned)");
          }
        } catch (emailError) {
          console.log("  ⚠️  Email send failed: " + emailError.message);
        }
        
        // Process attachments
        var attachments = message.getAttachments ? message.getAttachments() : [];
        console.log("  Attachments found: " + attachments.length);
        
        if (attachments.length > 0) {
          var allowedAtts = filterAllowedAttachments(attachments);
          console.log("  Allowed attachments: " + allowedAtts.length);
          
          if (allowedAtts.length > 0) {
            try {
              sendAttachmentsToServer(threadId, message, allowedAtts);
              stats.attachmentsSent += allowedAtts.length;
              console.log("  ✓ Uploaded " + allowedAtts.length + " attachment(s)");
            } catch (attError) {
              console.log("  ❌ Attachment upload failed: " + attError.message);
            }
          }
        }
        
        stats.processed++;
        markMessageProcessed(message.getId());
        console.log("  ✅ SUCCESS");
        
      } catch (msgError) {
        console.log("  ❌ ERROR: " + msgError.message);
        stats.errors++;
      }
    }
    
    // Update last check time
    updateLastCheckTime(now);
    
    // Summary
    var duration = (new Date() - startTime) / 1000;
    console.log("");
    console.log("=== SUMMARY ===");
    console.log("Total found: " + newMessages.length);
    console.log("Processed: " + stats.processed);
    console.log("Skipped: " + stats.skipped);
    console.log("Filtered: " + stats.filtered);
    console.log("Emails sent: " + stats.emailsSent);
    console.log("Labels applied: " + stats.labelsApplied);
    console.log("Attachments sent: " + stats.attachmentsSent);
    console.log("Errors: " + stats.errors);
    console.log("Duration: " + duration + "s");
    console.log("=== COMPLETE ===");;
    
  } catch (error) {
    console.log("");
    console.log("❌❌❌ CRITICAL ERROR ❌❌❌");
    console.log("Error: " + error.message);
    console.log("Stack: " + error.stack);
    
    // Update time to prevent loop
    try {
      updateLastCheckTime(new Date());
    } catch (e) {
      console.log("Failed to update time: " + e.message);
    }
  }
}

// ============================================================================
// UPDATED PROCESS MESSAGE WITH DETAILED LOGGING
// Replace your existing processMessage() function with this
// ============================================================================

/**
 * Process a single email message with detailed logging
 * Returns object with processing results
 */
function processMessageWithLogging(message, executionLog) {
  var messageId = message.getId();
  var thread = message.getThread();
  var threadId = thread.getId();
  
  var result = {
    emailSent: false,
    attachmentsSent: 0
  };
  
  executionLog.push("     Thread ID: " + threadId);
  
  // Step 1: Send email data to server
  try {
    executionLog.push("     → Sending email data to server...");
    sendEmailToServer(threadId, message);
    result.emailSent = true;
    executionLog.push("     ✓ Email data sent successfully");
  } catch (emailError) {
    executionLog.push("     ⚠️  Email send failed: " + emailError.message);
    // Continue to try attachments anyway
  }
  
  // Step 2: Process attachments
  var attachments = message.getAttachments ? message.getAttachments() : [];
  executionLog.push("     → Checking attachments...");
  executionLog.push("     Total blobs found: " + attachments.length);
  
  if (attachments.length === 0) {
    executionLog.push("     ℹ️  No attachments to process");
    return result;
  }
  
  // Filter allowed attachments
  var allowedAttachments = filterAllowedAttachmentsWithLogging(attachments, executionLog);
  
  if (allowedAttachments.length === 0) {
    executionLog.push("     ℹ️  No allowed attachments (all filtered)");
    return result;
  }
  
  executionLog.push("     → Allowed attachments: " + allowedAttachments.length);
  
  // Send attachments to server
  try {
    executionLog.push("     → Uploading attachments to server...");
    sendAttachmentsToServer(threadId, message, allowedAttachments);
    result.attachmentsSent = allowedAttachments.length;
    executionLog.push("     ✓ " + allowedAttachments.length + " attachment(s) uploaded");
  } catch (attError) {
    executionLog.push("     ❌ Attachment upload failed: " + attError.message);
    throw attError; // Re-throw to be caught by caller
  }
  
  return result;
}


// ============================================================================
// MESSAGE PROCESSING
// ============================================================================

/**
 * Process a single email message and its attachments
 * UPDATED: Apply domain filtering BEFORE processing
 * Returns statistics object
 */
function processMessage(message) {
  var messageId = message.getId();
  var thread = message.getThread();
  var threadId = thread.getId();
  
  // ⚠️ APPLY DOMAIN FILTER FIRST (ONLY IN BACKGROUND MONITOR)
  if (shouldFilterMessage(message)) {
    Logger.log("🚫 Message filtered - all participants from excluded domains");
    Logger.log("   Subject: " + message.getSubject());
    Logger.log("   From: " + message.getFrom());
    return { attachmentsSent: 0 }; // Skip this message completely
  }
  
  Logger.log("📧 Processing:");
  Logger.log("   Subject: " + message.getSubject());
  Logger.log("   From: " + message.getFrom());
  Logger.log("   Date: " + message.getDate());
  
  var stats = {
    attachmentsSent: 0,
    label: null
  };
  
  // Step 1: Send email data to server for labeling
  try {
    var label = sendEmailToServer(threadId, message);
    stats.label = label;
    Logger.log("   ✓ Email labeled: " + label);
  } catch (emailError) {
    Logger.log("   ⚠️ Failed to label email: " + emailError.message);
    // Continue to try attachments anyway
  }
  
  // Step 2: Process attachments
  var attachments = message.getAttachments ? message.getAttachments() : [];
  
  if (attachments.length === 0) {
    Logger.log("   No attachments");
    return stats;
  }
  
  Logger.log("   Found " + attachments.length + " attachment(s)");
  
  // Filter allowed attachments
  var allowedAttachments = filterAllowedAttachments(attachments);
  
  if (allowedAttachments.length === 0) {
    Logger.log("   All attachments filtered out");
    return stats;
  }
  
  Logger.log("   " + allowedAttachments.length + " allowed attachment(s)");
  
  // Send attachments to server
  try {
    sendAttachmentsToServer(threadId, message, allowedAttachments);
    stats.attachmentsSent = allowedAttachments.length;
    Logger.log("   ✓ " + allowedAttachments.length + " attachment(s) sent");
  } catch (attError) {
    Logger.log("   ⚠️ Failed to send attachments: " + attError.message);
  }
  
  return stats;
}

/**
 * Apply a label to Gmail thread
 * UPDATED: Removes existing auto-generated labels before applying new one
 */
function applyLabelToThread(threadId, labelName) {
  if (!labelName || labelName.trim().length === 0) {
    return; // Skip empty labels
  }
  
  var thread = GmailApp.getThreadById(threadId);
  if (!thread) {
    Logger.log("⚠️ Thread not found: " + threadId);
    return;
  }
  
  // Get list of labels that are managed by this system
  var managedLabelNames = Object.keys(CONFIG.LABEL_COLORS);
  
  // Remove existing managed labels from this thread
  var currentLabels = thread.getLabels();
  for (var i = 0; i < currentLabels.length; i++) {
    var currentLabelName = currentLabels[i].getName();
    
    // Check if this label is in our managed list (case-insensitive)
    for (var j = 0; j < managedLabelNames.length; j++) {
      if (currentLabelName.toLowerCase() === managedLabelNames[j].toLowerCase()) {
        thread.removeLabel(currentLabels[i]);
        Logger.log("🗑️  Removed old label: " + currentLabelName);
        break;
      }
    }
  }
  
  // Get or create the new label
  var label = getOrCreateLabel(labelName);
  
  if (label) {
    thread.addLabel(label);
    Logger.log("✅ Applied label '" + labelName + "' to thread (replaced previous)");
  }
}

/**
 * UPDATED LABEL_COLORS with more distinct, attractive colors
 */
CONFIG.LABEL_COLORS = {
  "Response": "blue",           // Bright blue
  "Fyi": "cyan",                // Bright cyan/turquoise
  "Notification": "lightgray",  // Light gray
  "Meeting": "purple",          // Bright purple ← CHANGED
  "Awaiting reply": "yellow",   // Bright yellow ← CHANGED
  "Escalation": "red",          // Bright red
  "Hotels": "orange",           // Bright orange
  "Airline": "cocoa",           // Brown
  "Airlines": "cocoa",          // Brown
  "Travel": "green",            // Bright green
  "Restaurant": "orange",       // Orange
  "Booking": "blue",            // Blue
  "Bank": "cyan",               // Cyan
  "Recruitment": "green"        // Green
};

/**
 * Get existing label or create it if it doesn't exist
 * Returns GmailLabel object with color applied
 */
function getOrCreateLabel(labelName) {
  if (!labelName || labelName.trim().length === 0) {
    return null;
  }
  
  // Capitalize first letter (Gmail convention)
  var formattedName = labelName.charAt(0).toUpperCase() + labelName.slice(1).toLowerCase();
  
  try {
    // Try to get existing label
    var labels = GmailApp.getUserLabels();
    for (var i = 0; i < labels.length; i++) {
      if (labels[i].getName().toLowerCase() === formattedName.toLowerCase()) {
        // Apply color if configured for this label
        applyLabelColor(labels[i], formattedName);
        return labels[i];
      }
    }
    
    // Label doesn't exist, create it
    var newLabel = GmailApp.createLabel(formattedName);
    Logger.log("📌 Created new label: " + formattedName);
    
    // Apply color if configured for this label
    applyLabelColor(newLabel, formattedName);
    
    return newLabel;
  } catch (error) {
    Logger.log("⚠️ Error managing label '" + labelName + "': " + error.message);
    return null;
  }
}

/**
 * Apply color to a label based on CONFIG.LABEL_COLORS mapping
 * UPDATED: Forces color refresh and handles errors better
 */
function applyLabelColor(label, labelName) {
  if (!label) return;

  var colorMap = {
    "red":       { textColor:"#ffffff", backgroundColor:"#d93025"},
    "orange":    { textColor:"#000000", backgroundColor:"#f29900"},
    "yellow":    { textColor:"#000000", backgroundColor:"#fbbc04"},
    "green":     { textColor:"#ffffff", backgroundColor:"#34a853"},
    "cyan":      { textColor:"#000000", backgroundColor:"#00acc1"},
    "blue":      { textColor:"#ffffff", backgroundColor:"#1a73e8"},
    "purple":    { textColor:"#ffffff", backgroundColor:"#9334e6"},
    "gray":      { textColor:"#ffffff", backgroundColor:"#5f6368"},
    "lightgray": { textColor:"#000000", backgroundColor:"#e8eaed"},
    "darkgray":  { textColor:"#ffffff", backgroundColor:"#3c4043"},
    "cocoa":     { textColor:"#ffffff", backgroundColor:"#795548"},
    "white":     { textColor:"#000000", backgroundColor:"#ffffff"}
  };

  var colorName = CONFIG.LABEL_COLORS[labelName];
  if (!colorName) return;

  var colorObj = colorMap[colorName.toLowerCase()];
  if (!colorObj) return;

  try {
    // ⭐ FORCE RESET FIRST
    label.setColor({
      textColor:"#000000",
      backgroundColor:"#ffffff"
    });

    Utilities.sleep(100);

    // ⭐ APPLY NEW COLOR
    label.setColor(colorObj);

    Logger.log("🎨 Color forced for " + labelName);
  } catch (e) {
    Logger.log(e.message);
  }
}

/**
 * Filter attachments by allowed file extensions with logging
 */
function filterAllowedAttachmentsWithLogging(attachments, executionLog) {
  var allowed = [];
  
  for (var i = 0; i < attachments.length; i++) {
    var att = attachments[i];
    
    // Skip inline attachments (images in email body)
    if (att.isInline && att.isInline()) {
      executionLog.push("        ⊘ " + (att.getName ? att.getName() : "unnamed") + " (inline, skipped)");
      continue;
    }
    
    var filename = att.getName ? att.getName() : "";
    var lowerName = filename.toLowerCase();
    
    // Check if file has allowed extension
    var isAllowed = false;
    for (var j = 0; j < CONFIG.ALLOWED_EXTENSIONS.length; j++) {
      var ext = CONFIG.ALLOWED_EXTENSIONS[j];
      var extIndex = lowerName.lastIndexOf(ext);
      if (extIndex !== -1 && extIndex === lowerName.length - ext.length) {
        isAllowed = true;
        break;
      }
    }
    
    if (isAllowed) {
      allowed.push(att);
      var sizeKB = Math.round((att.getBytes ? att.getBytes().length : 0) / 1024);
      executionLog.push("        ✓ " + filename + " (" + sizeKB + " KB)");
    } else {
      executionLog.push("        ⊘ " + filename + " (file type not allowed)");
    }
  }
  
  return allowed;
}


/**
 * Display recent monitor execution logs
 * @param {number} count - Number of recent executions to show (default: 5)
 */
function viewRecentLogs(count) {
  count = count || 5;
  
  try {
    var logSheetId = PropertiesService.getScriptProperties().getProperty("LOG_SHEET_ID");
    if (!logSheetId) {
      Logger.log("No logs found. The monitor hasn't created a log sheet yet.");
      return;
    }
    
    var ss = SpreadsheetApp.openById(logSheetId);
    var sheet = ss.getSheetByName("Monitor Logs");
    
    if (!sheet) {
      Logger.log("No log sheet found.");
      return;
    }
    
    var lastRow = sheet.getLastRow();
    if (lastRow <= 1) {
      Logger.log("No execution logs yet.");
      return;
    }
    
    Logger.log("=== RECENT MONITOR EXECUTIONS ===");
    Logger.log("Sheet URL: " + ss.getUrl());
    Logger.log("");
    
    // Get all data
    var data = sheet.getDataRange().getValues();
    
    // Group by timestamp (find execution boundaries)
    var executions = [];
    var currentExecution = [];
    var currentTimestamp = null;
    
    for (var i = data.length - 1; i >= 1; i--) {
      var row = data[i];
      var timestamp = row[0];
      var logEntry = row[1];
      
      if (logEntry.indexOf("=== EMAIL MONITOR EXECUTION START ===") !== -1) {
        if (currentExecution.length > 0) {
          executions.push({
            timestamp: currentTimestamp,
            logs: currentExecution.reverse()
          });
          currentExecution = [];
        }
        currentTimestamp = timestamp;
      }
      
      currentExecution.push(logEntry);
      
      if (executions.length >= count) {
        break;
      }
    }
    
    // Add last execution if exists
    if (currentExecution.length > 0 && executions.length < count) {
      executions.push({
        timestamp: currentTimestamp,
        logs: currentExecution.reverse()
      });
    }
    
    // Display executions
    executions.reverse();
    for (var i = 0; i < executions.length; i++) {
      Logger.log("EXECUTION " + (i + 1) + " - " + executions[i].timestamp);
      Logger.log("─".repeat(60));
      Logger.log(executions[i].logs.join("\n"));
      Logger.log("");
    }
    
  } catch (error) {
    Logger.log("Error viewing logs: " + error.message);
  }
}
// ============================================================================
// SERVER COMMUNICATION
// ============================================================================

/**
 * Send email data to Flask server for labeling
 * Returns the label assigned to the email
 */
function sendEmailToServer(threadId, message) {
  var flaskUrl = PropertiesService.getScriptProperties().getProperty("FLASK_SERVER_URL");
  if (!flaskUrl) {
    throw new Error("FLASK_SERVER_URL not configured in Script Properties");
  }
  
  var baseUrl = flaskUrl.replace(/\/$/, '').replace(/\/api$/, '');
  var endpoint = baseUrl + '/api/label-email';
  
  var userId = Session.getEffectiveUser().getEmail();
  
  var emailData = {
    message_id: message.getId(),
    from_address: message.getFrom(),
    to: message.getTo().split(',').map(function(e) { return e.trim(); }),
    subject: message.getSubject(),
    timestamp: message.getDate().toISOString(),
    body: message.getPlainBody ? message.getPlainBody() : (message.getBody ? message.getBody() : "")
  };
  
  var payload = {
    user_id: userId,
    thread_id: threadId,
    messages: [emailData]
  };
  
  var options = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };
  
  var resp = UrlFetchApp.fetch(endpoint, options);
  var responseCode = resp.getResponseCode();
  
  if (responseCode !== 200) {
    throw new Error("Server returned " + responseCode + ": " + resp.getContentText());
  }
  
  // Parse response and extract label
  var responseData = JSON.parse(resp.getContentText());
  var label = responseData.label;
  
  // Apply label to the thread
  if (label) {
    try {
      applyLabelToThread(threadId, label);
    } catch (labelError) {
      Logger.log("⚠️ Failed to apply label: " + labelError.message);
      // Don't throw - labeling failure shouldn't block the process
    }
  }
  
  return label;
}

/**
 * Send attachments to Flask server
 */
function sendAttachmentsToServer(threadId, message, attachmentBlobs) {
  var flaskUrl = PropertiesService.getScriptProperties().getProperty("FLASK_SERVER_URL");
  if (!flaskUrl) {
    throw new Error("FLASK_SERVER_URL not configured in Script Properties");
  }
  
  var baseUrl = flaskUrl.replace(/\/$/, '').replace(/\/api$/, '');
  var endpoint = baseUrl + '/api/store-attachments';
  
  var messageId = message.getId();
  var userId = Session.getEffectiveUser().getEmail();
  
  // Convert blobs to base64
  var attachments = attachmentBlobs.map(function(blob) {
    return {
      filename: blob.getName ? blob.getName() : "attachment",
      content: Utilities.base64Encode(blob.getBytes ? blob.getBytes() : blob.getBytes()),
      mime_type: blob.getContentType ? blob.getContentType() : "application/octet-stream"
    };
  });
  
  var payload = {
    user_id: userId,
    thread_id: threadId,
    message_id: messageId,
    attachments: attachments
  };
  
  var options = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };
  
  var resp = UrlFetchApp.fetch(endpoint, options);
  var responseCode = resp.getResponseCode();
  
  if (responseCode !== 200) {
    throw new Error("Server returned " + responseCode + ": " + resp.getContentText());
  }
}

// ============================================================================
// EMAIL RETRIEVAL
// ============================================================================

/**
 * Get new emails since last check time
 */
function getNewEmailsSince(lastCheckTime) {
  try {
    // Add 10 second buffer to avoid missing emails due to timing
    var searchTime = new Date(lastCheckTime.getTime() - 10000);
    
    // Format date for Gmail search
    var dateStr = Utilities.formatDate(searchTime, Session.getScriptTimeZone(), "yyyy/MM/dd");
    
    // Search for emails after this date
    var query = "after:" + dateStr;
    
    var threads = GmailApp.search(query, 0, 100); // Max 100 threads
    
    // Get all messages from threads
    var allMessages = [];
    
    for (var i = 0; i < threads.length; i++) {
      var messages = threads[i].getMessages();
      
      // Only include messages newer than lastCheckTime
      for (var j = 0; j < messages.length; j++) {
        var msgDate = messages[j].getDate();
        if (msgDate > lastCheckTime) {
          allMessages.push(messages[j]);
        }
      }
    }
    
    // Sort by date (newest first)
    allMessages.sort(function(a, b) {
      return b.getDate().getTime() - a.getDate().getTime();
    });
    
    return allMessages;
    
  } catch (error) {
    Logger.log("Error searching Gmail: " + error.message);
    return [];
  }
}

// ============================================================================
// TRACKING AND PERSISTENCE
// ============================================================================

/**
 * Get last check time from properties
 */
function getLastCheckTime() {
  var props = PropertiesService.getScriptProperties();
  var timeStr = props.getProperty(CONFIG.LAST_CHECK_TIME);
  
  if (!timeStr) {
    // First run - start from 5 minutes ago
    var defaultTime = new Date(Date.now() - (5 * 60 * 1000));
    return defaultTime;
  }
  
  try {
    return new Date(timeStr);
  } catch (e) {
    Logger.log("Failed to parse last check time: " + e.message);
    return new Date(Date.now() - (5 * 60 * 1000));
  }
}

/**
 * Update last check time
 */
function updateLastCheckTime(time) {
  var props = PropertiesService.getScriptProperties();
  props.setProperty(CONFIG.LAST_CHECK_TIME, time.toISOString());
}

/**
 * Check if message was already processed
 */
function isMessageProcessed(messageId) {
  var processedIds = getProcessedMessageIds();
  return processedIds.indexOf(messageId) !== -1;
}

/**
 * Get list of processed message IDs
 */
function getProcessedMessageIds() {
  var props = PropertiesService.getScriptProperties();
  var processedJson = props.getProperty(CONFIG.PROCESSED_MESSAGE_IDS);
  
  if (!processedJson) {
    return [];
  }
  
  try {
    return JSON.parse(processedJson);
  } catch (e) {
    Logger.log("Failed to parse processed IDs: " + e.message);
    return [];
  }
}

/**
 * Mark message as processed
 */
function markMessageProcessed(messageId) {
  var processedIds = getProcessedMessageIds();
  
  // Add new ID
  processedIds.push(messageId);
  
  // Keep only last 2000 IDs (prevents storage bloat)
  if (processedIds.length > 2000) {
    processedIds = processedIds.slice(-2000);
  }
  
  // Save back to properties
  var props = PropertiesService.getScriptProperties();
  props.setProperty(CONFIG.PROCESSED_MESSAGE_IDS, JSON.stringify(processedIds));
}

/**
 * Clear all processed message tracking (for reset/testing)
 */
function clearProcessedMessages() {
  var props = PropertiesService.getScriptProperties();
  props.deleteProperty(CONFIG.PROCESSED_MESSAGE_IDS);
  props.deleteProperty(CONFIG.LAST_CHECK_TIME);
  Logger.log("✅ Cleared all processed message tracking");
}

// ============================================================================
// SETUP AND TRIGGER MANAGEMENT
// ============================================================================

/**
 * SETUP FUNCTION - RUN THIS ONCE TO START THE MONITOR
 * This creates the trigger that runs every minute automatically
 */
function setupEmailMonitor() {
  Logger.log("=== Setting Up Email Monitor ===");
  
  // First, delete any existing triggers to avoid duplicates
  deleteAllMonitorTriggers();
  
  // Create new trigger that runs every minute
  ScriptApp.newTrigger('monitorEmails')
    .timeBased()
    .everyMinutes(CONFIG.CHECK_INTERVAL_MINUTES)
    .create();
  
  Logger.log("✅ Email monitor trigger created!");
  Logger.log("   Function: monitorEmails()");
  Logger.log("   Interval: Every " + CONFIG.CHECK_INTERVAL_MINUTES + " minute(s)");
  Logger.log("   Allowed files: " + CONFIG.ALLOWED_EXTENSIONS.join(", "));
  
  // Initialize last check time to now
  updateLastCheckTime(new Date());
  
  Logger.log("");
  Logger.log("🎉 Setup complete! Monitor is now active.");
  Logger.log("   The script will automatically check for new emails every minute.");
  Logger.log("   You don't need to do anything else.");
  Logger.log("");
  Logger.log("Running first check now...");
  
  // Run once immediately to test
  monitorEmails();
}

/**
 * Delete all monitor triggers
 */
function deleteAllMonitorTriggers() {
  var triggers = ScriptApp.getProjectTriggers();
  var deleteCount = 0;
  
  for (var i = 0; i < triggers.length; i++) {
    if (triggers[i].getHandlerFunction() === 'monitorEmails') {
      ScriptApp.deleteTrigger(triggers[i]);
      deleteCount++;
    }
  }
  
  if (deleteCount > 0) {
    Logger.log("Deleted " + deleteCount + " existing trigger(s)");
  }
}

/**
 * Stop the email monitor (delete trigger)
 */
function stopEmailMonitor() {
  Logger.log("⚠️ Stopping email monitor...");
  deleteAllMonitorTriggers();
  Logger.log("✅ Email monitor stopped");
  Logger.log("   Run setupEmailMonitor() to start it again");
}

/**
 * Complete reset - stops monitor and clears all tracking
 */
function resetEmailMonitor() {
  Logger.log("⚠️⚠️⚠️ RESETTING EMAIL MONITOR ⚠️⚠️⚠️");
  
  // Stop the monitor
  deleteAllMonitorTriggers();
  
  // Clear all tracking data
  clearProcessedMessages();
  
  Logger.log("✅ Reset complete");
  Logger.log("   Run setupEmailMonitor() to start fresh");
}

// ============================================================================
// UTILITIES AND INFORMATION
// ============================================================================

/**
 * Get current monitor status and statistics
 * UPDATED: Shows active domain filters
 */
function getMonitorStatus() {
  Logger.log("╔════════════════════════════════════════════╗");
  Logger.log("║       EMAIL MONITOR STATUS                 ║");
  Logger.log("╚════════════════════════════════════════════╝");
  Logger.log("");
  
  // Check if monitor is active
  var triggers = ScriptApp.getProjectTriggers();
  var monitorTriggers = triggers.filter(function(t) {
    return t.getHandlerFunction() === 'monitorEmails';
  });
  
  if (monitorTriggers.length === 0) {
    Logger.log("❌ MONITOR IS NOT ACTIVE");
    Logger.log("   Run setupEmailMonitor() to start it");
    Logger.log("");
    return;
  }
  
  Logger.log("✅ MONITOR IS ACTIVE");
  Logger.log("");
  
  // Statistics
  Logger.log("📊 STATISTICS");
  Logger.log("─────────────────────────────────────────");
  var processedIds = getProcessedMessageIds();
  Logger.log("Messages processed: " + processedIds.length);
  
  var lastCheck = getLastCheckTime();
  Logger.log("Last check: " + lastCheck.toISOString());
  
  var nextCheck = new Date(Date.now() + CONFIG.CHECK_INTERVAL_MINUTES * 60000);
  Logger.log("Next check: ~" + nextCheck.toISOString());
  Logger.log("");
  
  // Configuration
  Logger.log("⚙️  CONFIGURATION");
  Logger.log("─────────────────────────────────────────");
  Logger.log("Check interval: Every " + CONFIG.CHECK_INTERVAL_MINUTES + " minute(s)");
  Logger.log("Allowed files: " + CONFIG.ALLOWED_EXTENSIONS.join(", "));
  Logger.log("Max attachments/run: " + CONFIG.MAX_ATTACHMENTS_PER_RUN);
  Logger.log("");
  
  // Domain Filters (NEW)
  Logger.log("🔒 DOMAIN FILTERS");
  Logger.log("─────────────────────────────────────────");
  var filters = getDomainFilters();
  if (filters.length > 0) {
    Logger.log("Active filters: " + filters.length);
    filters.forEach(function(domain) {
      Logger.log("  • " + domain + " (EXCLUDED)");
    });
    Logger.log("");
    Logger.log("ℹ️  Emails where ALL participants are from");
    Logger.log("   these domains will be skipped.");
  } else {
    Logger.log("No filters active");
    Logger.log("All emails will be monitored and sent to server");
  }
  Logger.log("");
  
  // Triggers
  Logger.log("🔧 TRIGGERS");
  Logger.log("─────────────────────────────────────────");
  Logger.log("Active monitor triggers: " + monitorTriggers.length);
  Logger.log("Total project triggers: " + triggers.length);
  Logger.log("");
}

/**
 * Test the monitor manually (doesn't require trigger)
 */
function testMonitor() {
  Logger.log("=== MANUAL TEST RUN ===");
  Logger.log("This will run the monitor once without waiting for the trigger");
  Logger.log("");
  monitorEmails();
}

/**
 * List all active triggers in the project
 */
function listAllTriggers() {
  var triggers = ScriptApp.getProjectTriggers();
  
  Logger.log("=== ALL PROJECT TRIGGERS ===");
  Logger.log("Total: " + triggers.length);
  Logger.log("");
  
  for (var i = 0; i < triggers.length; i++) {
    var trigger = triggers[i];
    Logger.log("Trigger " + (i + 1) + ":");
    Logger.log("  Function: " + trigger.getHandlerFunction());
    Logger.log("  Type: " + trigger.getEventType());
    Logger.log("  ID: " + trigger.getUniqueId());
    Logger.log("");
  }
}

// ============================================================================
// DOMAIN FILTERING (APPLIED ONLY IN BACKGROUND MONITOR)
// ============================================================================

/**
 * Get domain filters from Script Properties
 * Shared with main script but ONLY applied here in background monitor
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

function shouldFilterEmail(emailAddress) {
  if (!emailAddress) return false;

  var filters = getDomainFilters();
  if (!filters || filters.length === 0) return false;

  // Extract raw email from Gmail format
  var match = emailAddress.match(/<(.+?)>/);
  var email = match ? match[1] : emailAddress;

  email = email.toLowerCase().trim();

  var atIndex = email.lastIndexOf('@');
  if (atIndex === -1) return false;

  var domain = email.substring(atIndex + 1);

  for (var i = 0; i < filters.length; i++) {
    var filter = filters[i].toLowerCase().trim();

    if (!filter) continue;

    // FULL EMAIL FILTER
    if (filter.indexOf('@') !== -1) {
      if (email === filter) {
        Logger.log("🚫 Filtered by FULL email: " + email);
        return true;
      }
    } 
    // DOMAIN FILTER
    else {
      if (domain === filter) {
        Logger.log("🚫 Filtered by DOMAIN: " + domain);
        return true;
      }
    }
  }

  return false;
}


function shouldFilterMessage(message) {
  var participants = [];

  // From
  participants.push(message.getFrom());

  // To
  participants = participants.concat(
    message.getTo().split(',')
  );

  // CC (if exists)
  if (message.getCc()) {
    participants = participants.concat(
      message.getCc().split(',')
    );
  }

  // Check each participant
  for (var i = 0; i < participants.length; i++) {
    if (shouldFilterEmail(participants[i])) {
      Logger.log("🚫 Message filtered due to: " + participants[i]);
      return true;
    }
  }

  return false;
}

// ============================================================================
// QUICK START GUIDE
// ============================================================================

/**
 * Display setup instructions
 */
function showSetupInstructions() {
  Logger.log("╔════════════════════════════════════════════════════════════════╗");
  Logger.log("║                EMAIL MONITOR - SETUP GUIDE                     ║");
  Logger.log("╚════════════════════════════════════════════════════════════════╝");
  Logger.log("");
  Logger.log("📋 STEP 1: Configure Server URL");
  Logger.log("   1. Go to Project Settings (gear icon)");
  Logger.log("   2. Click 'Script Properties'");
  Logger.log("   3. Add property:");
  Logger.log("      Property: FLASK_SERVER_URL");
  Logger.log("      Value: Your Flask server URL (e.g., https://your-server.com/api)");
  Logger.log("");
  Logger.log("🚀 STEP 2: Start the Monitor");
  Logger.log("   1. Run this function: setupEmailMonitor()");
  Logger.log("   2. Authorize the script when prompted");
  Logger.log("   3. Done! Monitor will run automatically every minute");
  Logger.log("");
  Logger.log("📊 CHECK STATUS");
  Logger.log("   Run: getMonitorStatus()");
  Logger.log("");
  Logger.log("🛑 STOP MONITOR");
  Logger.log("   Run: stopEmailMonitor()");
  Logger.log("");
  Logger.log("🔄 RESET EVERYTHING");
  Logger.log("   Run: resetEmailMonitor()");
  Logger.log("");
  Logger.log("🧪 TEST MANUALLY");
  Logger.log("   Run: testMonitor()");
  Logger.log("");
}

/**
 * Add or update label color configuration
 * @param {string} labelName - The label name
 * @param {string} color - The color (red, orange, yellow, green, cyan, blue, purple, gray, lightgray, cocoa, white, darkgray)
 */
function setLabelColor(labelName, color) {
  // Validate color
  var validColors = ["red", "orange", "yellow", "green", "cyan", "blue", "purple", "gray", "lightgray", "cocoa", "white", "darkgray"];
  if (validColors.indexOf(color.toLowerCase()) === -1) {
    Logger.log("❌ Invalid color: " + color);
    Logger.log("   Valid colors: " + validColors.join(", "));
    return;
  }
  
  CONFIG.LABEL_COLORS[labelName] = color.toLowerCase();
  Logger.log("✅ Label '" + labelName + "' will now use color: " + color);
  
  // Apply to existing label if it exists
  var labels = GmailApp.getUserLabels();
  for (var i = 0; i < labels.length; i++) {
    if (labels[i].getName().toLowerCase() === labelName.toLowerCase()) {
      try {
        labels[i].setColor(color.toLowerCase());
        Logger.log("✓ Applied color to existing label");
      } catch (error) {
        Logger.log("⚠️ Could not apply color to existing label: " + error.message);
      }
      return;
    }
  }
  
  Logger.log("ℹ️  Label doesn't exist yet - color will be applied when label is created");
}
// ============================================================================
// PROCESS LAST N MONTHS - With timeout-safe continuation support
// ============================================================================

/**
 * ASYNC LAUNCHER — called from the UI (Run Now button).
 * Immediately initialises the job state and schedules a background trigger.
 * Returns within milliseconds so the UI is never blocked.
 * @param {string|number} months - Number of months to process
 * @returns {Object} status - { n, afterStr, beforeStr } for the confirmation card
 */
function _launchBulkJobAsync(months) {
  var scriptProps = PropertiesService.getScriptProperties();

  months = parseInt(months, 10);
  if (isNaN(months) || months < 1) months = 3;

  // Persist months so background trigger knows what to process
  scriptProps.setProperty("process_last_n_months", String(months));

  // Clear any leftover abort flag and old job state
  scriptProps.deleteProperty(BULK_JOB_ABORT_KEY);
  scriptProps.deleteProperty(BULK_JOB_STATE_KEY);
  _deleteAllContinuationTriggers();

  // Initialise fresh job state (writes afterStr / beforeStr etc.)
  _initBulkJob();

  // Read back the state we just wrote so we can show dates to the user
  var state = JSON.parse(scriptProps.getProperty(BULK_JOB_STATE_KEY));

  // Schedule the first real run via a background trigger (~1 minute)
  ScriptApp.newTrigger('_continueBulkJob')
    .timeBased()
    .after(60 * 1000)
    .create();

  console.log("🚀 Async job launched: " + state.afterStr + " → " + state.beforeStr + " (starts in ~1 min)");
  return state;
}

/**
 * ENTRY POINT - called only by background triggers (never directly from UI).
 * Safe to call multiple times - picks up where it left off.
 * @param {Object} e - Optional event object with formInput.process_last_n_months value
 */
function processLastNMonthsEmails(e) {
  var scriptProps = PropertiesService.getScriptProperties();

  // If a months value was passed in, save it and force a completely fresh start
  var forceNew = false;
  if (e && e.formInput && e.formInput.process_last_n_months) {
    scriptProps.setProperty("process_last_n_months", e.formInput.process_last_n_months);
    console.log("📝 Time window set to: " + e.formInput.process_last_n_months + " months");
    forceNew = true;
  }

  // Clear any leftover abort flag before starting
  scriptProps.deleteProperty(BULK_JOB_ABORT_KEY);

  var existingJob = scriptProps.getProperty(BULK_JOB_STATE_KEY);
  if (existingJob && !forceNew) {
    console.log("▶️ Resuming existing job...");
  } else {
    if (forceNew && existingJob) {
      console.log("🔄 New time window selected — clearing old job state and starting fresh...");
      scriptProps.deleteProperty(BULK_JOB_STATE_KEY);
      _deleteAllContinuationTriggers();
    } else {
      console.log("🆕 Starting new job...");
    }
    _initBulkJob();
  }
  _runBulkJob();
}

/**
 * Initialize a new bulk job - saves state to Script Properties
 */
function _initBulkJob() {
  var scriptProps = PropertiesService.getScriptProperties();

  // Read N - with detailed logging
  var savedValue = scriptProps.getProperty("process_last_n_months");
  console.log("🔍 DEBUG: Saved 'process_last_n_months' value: " + savedValue);

  var n = parseInt(savedValue || "24", 10);
  if (isNaN(n) || n < 1) n = 3;

  console.log("✅ DEBUG: Final N value being used: " + n + " months");

  // Calculate date range
  var today     = new Date();
  var startDate = new Date(today);
  startDate.setMonth(startDate.getMonth() - n);

  function pad(num) { return num < 10 ? '0' + num : '' + num; }
  var afterStr = startDate.getFullYear() + "/" + pad(startDate.getMonth() + 1) + "/" + pad(startDate.getDate());
  var beforeStr = today.getFullYear() + "/" + pad(today.getMonth() + 1) + "/" + pad(today.getDate());

  var jobState = {
    n           : n,
    afterStr    : afterStr,
    beforeStr   : beforeStr,
    startDate   : startDate.toISOString(),
    endDate     : today.toISOString(),
    offset      : 0,           // which thread batch we're on
    status      : "running",
    // cumulative stats
    stats: {
      threadsScanned : 0,
      messagesFound  : 0,
      labeled        : 0,
      skipped        : 0,
      filtered       : 0,
      errors         : 0
    }
  };

  scriptProps.setProperty("bulk_job_state", JSON.stringify(jobState));
  console.log("✓ Job initialized: last " + n + " months (" + afterStr + " → " + beforeStr + ")");
}

function _runBulkJob() {
  var SAFE_DURATION_MS = 4.5 * 60 * 1000;
  var BATCH_SIZE       = 50;
  var CALL_GAP_MS      = 2000; // 15 second gap between each API call

  var runStart    = new Date();
  var scriptProps = PropertiesService.getScriptProperties();

  // ✅ ABORT CHECK #1 — before doing anything at all
  if (scriptProps.getProperty(BULK_JOB_ABORT_KEY) === "true") {
    console.log("🛑 Abort flag detected at entry. Cleaning up.");
    _cleanupAfterAbort();
    return;
  }

  var stateJson = scriptProps.getProperty(BULK_JOB_STATE_KEY);
  if (!stateJson) {
    console.log("ℹ️  No job state — job was cancelled.");
    return;
  }

  var state = JSON.parse(stateJson);
  console.log("=== BULK JOB RUN START === offset: " + state.offset);

  var flaskUrl = scriptProps.getProperty("FLASK_SERVER_URL");
  if (!flaskUrl) {
    _markJobFailed("FLASK_SERVER_URL not configured");
    return;
  }

  var baseUrl    = flaskUrl.replace(/\/$/, '').replace(/\/api$/, '');
  var endpoint   = baseUrl + '/api/label-email';
  var userId     = Session.getEffectiveUser().getEmail();
  var startDate  = new Date(state.startDate);
  var endDate    = new Date(state.endDate);
  var gmailQuery = "after:" + state.afterStr + " before:" + state.beforeStr;

  var timedOut = false;
  var aborted  = false;

  outer:
  while (true) {

    // ✅ ABORT CHECK #2 — top of every outer loop iteration
    if (scriptProps.getProperty(BULK_JOB_ABORT_KEY) === "true") {
      console.log("🛑 Abort detected in outer loop. Stopping.");
      aborted = true;
      break outer;
    }

    // ⏱️ TIME CHECK
    if ((new Date()) - runStart >= SAFE_DURATION_MS) {
      console.log("⏱️ Time limit reached. Saving state.");
      timedOut = true;
      break outer;
    }

    var threads;
    try {
      threads = GmailApp.search(gmailQuery, state.offset, BATCH_SIZE);
    } catch (searchErr) {
      console.log("❌ Gmail search error: " + searchErr.message);
      state.stats.errors++;
      break outer;
    }

    if (!threads || threads.length === 0) {
      console.log("✅ All threads processed.");
      break outer;
    }

    state.stats.threadsScanned += threads.length;

    for (var i = 0; i < threads.length; i++) {

      // ✅ ABORT CHECK #3 — per thread
      if (scriptProps.getProperty(BULK_JOB_ABORT_KEY) === "true") {
        console.log("🛑 Abort detected in thread loop. Stopping.");
        aborted = true;
        break outer;
      }

      if ((new Date()) - runStart >= SAFE_DURATION_MS) {
        timedOut = true;
        break outer;
      }

      var thread   = threads[i];
      var threadId = thread.getId();
      var messages = thread.getMessages();

      for (var j = 0; j < messages.length; j++) {

        // ✅ ABORT CHECK #4 — per message
        if (scriptProps.getProperty(BULK_JOB_ABORT_KEY) === "true") {
          console.log("🛑 Abort detected in message loop. Stopping.");
          aborted = true;
          break outer;
        }

        // ⏱️ TIME CHECK — account for the upcoming 15s sleep
        if ((new Date()) - runStart >= SAFE_DURATION_MS - CALL_GAP_MS) {
          console.log("⏱️ Time limit approaching (gap buffer). Saving state.");
          timedOut = true;
          break outer;
        }

        var message   = messages[j];
        var messageId = message.getId();
        var msgDate   = message.getDate();

        if (msgDate < startDate || msgDate > endDate) continue;

        state.stats.messagesFound++;

        if (isMessageProcessed(messageId)) {
          state.stats.skipped++;
          continue;
        }

        if (shouldFilterMessage(message)) {
          state.stats.filtered++;
          markMessageProcessed(messageId);
          continue;
        }

        // Call /api/label-email
        try {
          var resp = UrlFetchApp.fetch(endpoint, {
            method             : "post",
            contentType        : "application/json",
            payload            : JSON.stringify({
              user_id   : userId,
              thread_id : threadId,
              messages  : [{
                message_id   : messageId,
                from_address : message.getFrom(),
                to           : message.getTo().split(',').map(function(e){ return e.trim(); }),
                subject      : message.getSubject(),
                timestamp    : message.getDate().toISOString(),
                body         : message.getPlainBody ? message.getPlainBody() : ""
              }]
            }),
            muteHttpExceptions : true
          });

          if (resp.getResponseCode() !== 200) {
            console.log("  ❌ Server " + resp.getResponseCode() + ": " + message.getSubject().substring(0, 40));
            state.stats.errors++;
          } else {
            var label = JSON.parse(resp.getContentText()).label;
            if (label) {
              try { applyLabelToThread(threadId, label); } catch(le) {}
              console.log("  ✓ [" + label + "] " + message.getSubject().substring(0, 45));
            }
            state.stats.labeled++;
          }

          markMessageProcessed(messageId);

          // ✅ 15-second gap between each API call
          console.log("  ⏳ Waiting 15s before next call...");
          Utilities.sleep(CALL_GAP_MS);

        } catch (msgErr) {
          console.log("  ❌ " + msgErr.message);
          state.stats.errors++;
          // Still wait before next call even on error
          Utilities.sleep(CALL_GAP_MS);
        }

      } // messages
    } // threads

    state.offset += threads.length;
    if (threads.length < BATCH_SIZE) {
      console.log("✅ Reached end of Gmail results.");
      break outer;
    }

  } // outer while

  // ── Post-run ────────────────────────────────────────────────────────────
  var duration = ((new Date()) - runStart) / 1000;
  console.log("Duration: " + duration.toFixed(1) + "s | Labeled: " + state.stats.labeled +
              " | Errors: " + state.stats.errors);

  if (aborted) {
    _cleanupAfterAbort();
    console.log("🛑 Job stopped cleanly after abort.");
  } else if (timedOut) {
    scriptProps.setProperty(BULK_JOB_STATE_KEY, JSON.stringify(state));
    _scheduleContinuation();
    console.log("⏭️  Saved. Continuing in ~1 minute.");
  } else {
    _markJobComplete(state);
  }
}

/**
 * Schedule a one-time trigger to continue the job in 1 minute
 * Removes any existing continuation triggers first to avoid duplicates
 */
function _scheduleContinuation() {
  // Delete existing continuation triggers
  var triggers = ScriptApp.getProjectTriggers();
  for (var i = 0; i < triggers.length; i++) {
    if (triggers[i].getHandlerFunction() === '_continueBulkJob') {
      ScriptApp.deleteTrigger(triggers[i]);
    }
  }

  // Schedule new one-time trigger 1 minute from now
  ScriptApp.newTrigger('_continueBulkJob')
    .timeBased()
    .after(1 * 60 * 1000) // 1 minute in milliseconds
    .create();
}

function _continueBulkJob() {
  _deleteAllContinuationTriggers(); // self-delete first

  var scriptProps = PropertiesService.getScriptProperties();

  // ✅ Check abort flag before doing ANYTHING
  if (scriptProps.getProperty(BULK_JOB_ABORT_KEY) === "true") {
    console.log("🛑 Abort flag found in continuation. Cleaning up, not continuing.");
    _cleanupAfterAbort();
    return;
  }

  // Also check state exists
  if (!scriptProps.getProperty(BULK_JOB_STATE_KEY)) {
    console.log("ℹ️  No job state found. Job was cancelled. Not continuing.");
    return;
  }

  console.log("🔄 Auto-continuing bulk job...");
  _runBulkJob();
}
// ============================================================================
// NEW HELPER — cleanup on abort
// ============================================================================
function _cleanupAfterAbort() {
  var scriptProps = PropertiesService.getScriptProperties();
  scriptProps.deleteProperty(BULK_JOB_STATE_KEY);
  scriptProps.deleteProperty(BULK_JOB_ABORT_KEY);
  _deleteAllContinuationTriggers();
  console.log("✓ Abort cleanup complete.");
}

// ============================================================================
// NEW HELPER — centralized trigger deletion
// ============================================================================
function _deleteAllContinuationTriggers() {
  var triggers = ScriptApp.getProjectTriggers();
  var count = 0;
  for (var i = 0; i < triggers.length; i++) {
    if (triggers[i].getHandlerFunction() === '_continueBulkJob') {
      ScriptApp.deleteTrigger(triggers[i]);
      count++;
    }
  }
  if (count > 0) console.log("✓ Removed " + count + " continuation trigger(s).");
}

/**
 * Mark job as complete, clear state, log final stats
 */
function _markJobComplete(state) {
  var scriptProps = PropertiesService.getScriptProperties();
  scriptProps.deleteProperty(BULK_JOB_STATE_KEY);
  scriptProps.deleteProperty(BULK_JOB_ABORT_KEY);
  _deleteAllContinuationTriggers();
  console.log("🎉 JOB COMPLETE!");
  console.log("Total labeled  : " + state.stats.labeled);
  console.log("Total skipped  : " + state.stats.skipped);
  console.log("Total filtered : " + state.stats.filtered);
  console.log("Total errors   : " + state.stats.errors);
}

/**
 * Mark job as failed, preserve state for inspection
 */
function _markJobFailed(reason) {
  var scriptProps = PropertiesService.getScriptProperties();
  var stateJson   = scriptProps.getProperty("bulk_job_state");
  if (stateJson) {
    var state  = JSON.parse(stateJson);
    state.status = "failed";
    state.failReason = reason;
    scriptProps.setProperty("bulk_job_state", JSON.stringify(state));
  }
  console.log("❌ Job failed: " + reason);
}

/**
 * Check the current status of a running bulk job
 * Call this anytime to see progress
 */
function checkBulkJobStatus() {
  var scriptProps = PropertiesService.getScriptProperties();
  var stateJson   = scriptProps.getProperty("bulk_job_state");

  if (!stateJson) {
    console.log("ℹ️  No bulk job is currently running.");
    return;
  }

  var state = JSON.parse(stateJson);
  console.log("=== BULK JOB STATUS ===");
  console.log("Period  : last " + state.n + " months");
  console.log("Range   : " + state.afterStr + " → " + state.beforeStr);
  console.log("Offset  : " + state.offset + " threads processed so far");
  console.log("Status  : " + state.status);
  console.log("Labeled : " + state.stats.labeled);
  console.log("Skipped : " + state.stats.skipped);
  console.log("Errors  : " + state.stats.errors);
}

/**
 * Cancel a running bulk job and clean up all triggers
 */
function cancelBulkJob() {
  var scriptProps = PropertiesService.getScriptProperties();

  // Step 1: Set poison pill FIRST — running loop sees this within milliseconds
  scriptProps.setProperty(BULK_JOB_ABORT_KEY, "true");

  // Step 2: Wipe job state so no new run can start
  scriptProps.deleteProperty(BULK_JOB_STATE_KEY);

  // Step 3: Kill all continuation triggers
  _deleteAllContinuationTriggers();

  console.log("🛑 CANCELLED.");
  console.log("   Abort flag SET   → running loop stops at next message");
  console.log("   Job state WIPED  → no new runs possible");
  console.log("   Triggers REMOVED → no scheduled continuations");
  console.log("");
  console.log("⚠️  If calls still arrive for ~1-2 seconds, that's the");
  console.log("   current UrlFetchApp.fetch() finishing. It will stop after that.");
}


/**
 * Display available colors with examples
 */
function showAvailableColors() {
  Logger.log("╔════════════════════════════════════════════╗");
  Logger.log("║       AVAILABLE LABEL COLORS               ║");
  Logger.log("╚════════════════════════════════════════════╝");
  Logger.log("");
  Logger.log("Examples:");
  Logger.log("  Run: setLabelColor('Important', 'red')");
  Logger.log("  Run: setLabelColor('Urgent', 'orange')");
  Logger.log("  Run: setLabelColor('Done', 'green')");
  Logger.log("");
  Logger.log("Available colors:");
  Logger.log("  • red          - Bright red");
  Logger.log("  • orange       - Bright orange");
  Logger.log("  • yellow       - Bright yellow");
  Logger.log("  • green        - Bright green");
  Logger.log("  • cyan         - Bright cyan/turquoise");
  Logger.log("  • blue         - Bright blue");
  Logger.log("  • purple       - Bright purple");
  Logger.log("  • gray         - Medium gray");
  Logger.log("  • lightgray    - Light gray");
  Logger.log("  • darkgray     - Dark gray");
  Logger.log("  • cocoa        - Brown/cocoa");
  Logger.log("  • white        - White/default");
  Logger.log("");
  Logger.log("Current label colors:");
  Logger.log("─────────────────────────────────────────");
  for (var label in CONFIG.LABEL_COLORS) {
    Logger.log("  ▪ " + label + " → " + CONFIG.LABEL_COLORS[label]);
  }
}